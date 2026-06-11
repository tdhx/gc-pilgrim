import {
  addDays,
  addMonths,
  dateFromKey,
  eventDateKey,
  eventsInRange,
  liturgicalColour,
  matchesEvent,
  monthGrid,
  monthStart,
  orderedEventTypes,
  presiderGroups,
  startOfSundayWeek,
  validateFeed,
} from "./web/calendar-core.js?v=5";

const FEED_URL = "feeds/v1/calendar.json";
const DEFAULT_EVENT_TYPES = ["mass", "confession"];
const MULTICULTURAL_TYPE = "multicultural";

const state = {
  events: [],
  feed: null,
  selected: {
    eventType: new Set(),
    multiculturalSubtype: new Set(),
    church: new Set(),
    presider: new Set(),
  },
  search: "",
  useDefaultEventTypes: true,
  view: "weekly",
  weekStart: null,
  month: null,
  selectedMonthDate: null,
};

const elements = {
  events: document.querySelector("#events"),
  resultsContext: document.querySelector("#results-context"),
  resultsCount: document.querySelector("#results-count"),
  eventTypeFilters: document.querySelector("#event-type-filters"),
  filters: document.querySelector("#filters"),
  filtersContent: document.querySelector("#filters-content"),
  filtersToggle: document.querySelector("#filters-toggle"),
  churchFilters: document.querySelector("#church-filters"),
  presiderFilters: document.querySelector("#presider-filters"),
  search: document.querySelector("#search"),
  resetFilters: document.querySelector("#reset-filters"),
  clearFilters: document.querySelector("#clear-filters"),
  emptyMessage: document.querySelector("#empty-message"),
  errorMessage: document.querySelector("#error-message"),
  diagnostics: document.querySelector("#diagnostics"),
  diagnosticsSummary: document.querySelector("#diagnostics-summary"),
  diagnosticsBody: document.querySelector("#diagnostics-body"),
  template: document.querySelector("#event-template"),
  viewButtons: [...document.querySelectorAll(".view-button")],
  periodNavigation: document.querySelector("#period-navigation"),
  previousPeriod: document.querySelector("#previous-period"),
  todayPeriod: document.querySelector("#today-period"),
  nextPeriod: document.querySelector("#next-period"),
};

const timeFormatter = new Intl.DateTimeFormat("en-AU", {
  timeZone: "Australia/Brisbane",
  hour: "numeric",
  minute: "2-digit",
});

const dayHeadingFormatter = new Intl.DateTimeFormat("en-AU", {
  timeZone: "UTC",
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

const shortDayFormatter = new Intl.DateTimeFormat("en-AU", {
  timeZone: "UTC",
  weekday: "short",
  day: "numeric",
  month: "short",
});

const weekRangeFormatter = new Intl.DateTimeFormat("en-AU", {
  timeZone: "UTC",
  day: "numeric",
  month: "short",
});

const monthHeadingFormatter = new Intl.DateTimeFormat("en-AU", {
  timeZone: "UTC",
  month: "long",
  year: "numeric",
});

function titleCase(value) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function eventTypeLabel(value) {
  return {
    baptism: "Baptisms",
    confession: "Reconciliation",
    multicultural: "Multicultural Mass",
  }[value] || titleCase(value);
}

function multiculturalSubtype(event) {
  if (event.event_subtype) return event.event_subtype;
  const match = event.title.toLocaleLowerCase().match(/\b(hispanic|maronite|polish|italian)\s+mass\b/);
  return match ? match[1] : null;
}

function subtypeLabel(value) {
  return `${titleCase(value)} Mass`;
}

function displayChurch(church) {
  return church || "Unassigned";
}

function displayPresider(name) {
  const givenName = name.replace(/^Fr\s+/, "");
  return `Fr. ${givenName === "Damian" ? "Damien" : givenName}`;
}

function uniqueValues(getValues) {
  return [...new Set(state.events.flatMap(getValues))].sort((a, b) => a.localeCompare(b));
}

function countFor(group, value) {
  if (group === "eventType") {
    return state.events.filter((event) => event.event_type === value).length;
  }
  if (group === "church") {
    return state.events.filter((event) => displayChurch(event.church) === value).length;
  }
  if (group === "multiculturalSubtype") {
    return state.events.filter((event) => event.event_subtype === value).length;
  }
  return state.events.filter((event) => event.presiders.includes(value)).length;
}

function buildCheckboxes(container, group, values, labelFormatter = (value) => value) {
  container.replaceChildren();

  values.forEach((value) => {
    const label = document.createElement("label");
    label.className = "checkbox-option";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = value;
    input.dataset.group = group;
    input.checked = state.selected[group].has(value);
    input.addEventListener("change", () => {
      const selected = state.selected[group];
      input.checked ? selected.add(value) : selected.delete(value);
      if (group === "eventType") state.useDefaultEventTypes = false;
      renderEvents();
    });

    const text = document.createElement("span");
    text.textContent = labelFormatter(value);

    const count = document.createElement("span");
    count.className = "filter-count";
    count.textContent = countFor(group, value);

    label.append(input, text, count);
    container.append(label);
  });
}

function syncMulticulturalControls() {
  const parent = elements.eventTypeFilters.querySelector(
    `input[data-group="eventType"][value="${MULTICULTURAL_TYPE}"]`,
  );
  if (!parent) return;

  const subtypeInputs = [
    ...elements.eventTypeFilters.querySelectorAll(
      'input[data-group="multiculturalSubtype"]',
    ),
  ];
  const selectedCount = subtypeInputs.filter((input) => (
    state.selected.multiculturalSubtype.has(input.value)
  )).length;

  parent.checked = selectedCount === subtypeInputs.length && selectedCount > 0;
  parent.indeterminate = selectedCount > 0 && selectedCount < subtypeInputs.length;
  subtypeInputs.forEach((input) => {
    input.checked = state.selected.multiculturalSubtype.has(input.value);
  });
}

function buildEventTypeFilters() {
  elements.eventTypeFilters.replaceChildren();
  const eventTypes = orderedEventTypes(uniqueValues((event) => [event.event_type]));

  eventTypes.forEach((value) => {
    const wrapper = document.createElement("div");
    wrapper.className = value === MULTICULTURAL_TYPE ? "filter-family" : "";

    const label = document.createElement("label");
    label.className = "checkbox-option";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = value;
    input.dataset.group = "eventType";
    input.checked = state.selected.eventType.has(value);

    const text = document.createElement("span");
    text.textContent = eventTypeLabel(value);
    const count = document.createElement("span");
    count.className = "filter-count";
    count.textContent = countFor("eventType", value);
    label.append(input, text, count);
    wrapper.append(label);

    if (value === MULTICULTURAL_TYPE) {
      const heading = document.createElement("div");
      heading.className = "filter-family-heading";
      heading.append(label);

      const subtypes = uniqueValues((event) => (
        event.event_type === MULTICULTURAL_TYPE && event.event_subtype
          ? [event.event_subtype]
          : []
      ));
      const children = document.createElement("div");
      children.className = "checkbox-sublist";
      children.id = "multicultural-subtype-filters";

      const toggle = document.createElement("button");
      toggle.className = "filter-family-toggle";
      toggle.type = "button";
      toggle.setAttribute("aria-expanded", "true");
      toggle.setAttribute("aria-controls", children.id);
      toggle.setAttribute("aria-label", "Collapse Multicultural Mass options");

      const toggleIcon = document.createElement("span");
      toggleIcon.className = "filter-toggle-icon";
      toggleIcon.setAttribute("aria-hidden", "true");
      toggle.append(toggleIcon);
      heading.append(toggle);
      wrapper.replaceChildren(heading);

      toggle.addEventListener("click", () => {
        const expanded = toggle.getAttribute("aria-expanded") === "true";
        toggle.setAttribute("aria-expanded", String(!expanded));
        toggle.setAttribute(
          "aria-label",
          `${expanded ? "Expand" : "Collapse"} Multicultural Mass options`,
        );
        children.hidden = expanded;
      });

      subtypes.forEach((subtype) => {
        const childLabel = document.createElement("label");
        childLabel.className = "checkbox-option checkbox-option-child";
        const childInput = document.createElement("input");
        childInput.type = "checkbox";
        childInput.value = subtype;
        childInput.dataset.group = "multiculturalSubtype";

        const childText = document.createElement("span");
        childText.textContent = subtypeLabel(subtype);
        const childCount = document.createElement("span");
        childCount.className = "filter-count";
        childCount.textContent = countFor("multiculturalSubtype", subtype);
        childLabel.append(childInput, childText, childCount);
        children.append(childLabel);

        childInput.addEventListener("change", () => {
          state.useDefaultEventTypes = false;
          childInput.checked
            ? state.selected.multiculturalSubtype.add(subtype)
            : state.selected.multiculturalSubtype.delete(subtype);

          if (state.selected.multiculturalSubtype.size) {
            state.selected.eventType.add(MULTICULTURAL_TYPE);
          } else {
            state.selected.eventType.delete(MULTICULTURAL_TYPE);
          }
          syncMulticulturalControls();
          renderEvents();
        });
      });
      wrapper.append(children);

      input.addEventListener("change", () => {
        state.useDefaultEventTypes = false;
        if (input.checked) {
          state.selected.eventType.add(MULTICULTURAL_TYPE);
          subtypes.forEach((subtype) => state.selected.multiculturalSubtype.add(subtype));
        } else {
          state.selected.eventType.delete(MULTICULTURAL_TYPE);
          state.selected.multiculturalSubtype.clear();
        }
        syncMulticulturalControls();
        renderEvents();
      });
    } else {
      input.addEventListener("change", () => {
        state.useDefaultEventTypes = false;
        input.checked
          ? state.selected.eventType.add(value)
          : state.selected.eventType.delete(value);
        renderEvents();
      });
    }

    elements.eventTypeFilters.append(wrapper);
  });

  syncMulticulturalControls();
}

function buildFilters() {
  buildEventTypeFilters();
  buildCheckboxes(
    elements.churchFilters,
    "church",
    uniqueValues((event) => [displayChurch(event.church)]),
  );
  elements.presiderFilters.replaceChildren();
  presiderGroups(uniqueValues((event) => event.presiders)).forEach((group, index) => {
    if (index) {
      const separator = document.createElement("div");
      separator.className = "filter-group-separator";
      separator.setAttribute("aria-hidden", "true");
      elements.presiderFilters.append(separator);
    }
    const groupContainer = document.createElement("div");
    groupContainer.className = "checkbox-list filter-presider-group";
    buildCheckboxes(groupContainer, "presider", group, displayPresider);
    elements.presiderFilters.append(groupContainer);
  });
}

function matchesFilters(event) {
  return matchesEvent(
    event,
    state.selected,
    state.search,
    state.useDefaultEventTypes ? DEFAULT_EVENT_TYPES : [],
  );
}

function formatEventTime(event) {
  if (event.all_day) return "All day";
  return `${timeFormatter.format(new Date(event.start))}–${timeFormatter.format(new Date(event.end))}`;
}

function currentBrisbaneDate() {
  const parts = new Intl.DateTimeFormat("en-AU", {
    timeZone: "Australia/Brisbane",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function churchClass(church) {
  return {
    "Sacred Heart": "church-sacred-heart",
    "St. Vincent's": "church-st-vincents",
    "Stella Maris": "church-stella-maris",
  }[church] || "church-unassigned";
}

function makeTag(text) {
  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = text;
  return tag;
}

function renderCard(event) {
  const card = elements.template.content.firstElementChild.cloneNode(true);
  card.classList.add(churchClass(event.church));
  card.dataset.eventDate = eventDateKey(event);
  card.dataset.liturgicalColour = liturgicalColour(event);

  card.querySelector(".event-church").textContent = displayChurch(event.church);
  card.querySelector(".event-service").textContent = event.service_name;
  card.querySelector(".event-time").textContent = formatEventTime(event);
  card.querySelector(".event-presider").textContent = event.presiders.length
    ? event.presiders.map(displayPresider).join(", ")
    : "Presider TBA";
  const subtitle = card.querySelector(".event-subtitle");
  const observance = event.liturgical?.observance;
  subtitle.textContent = observance && observance !== event.service_name ? observance : "";
  subtitle.hidden = !subtitle.textContent;

  const tags = card.querySelector(".event-tags");
  if (event.liturgical?.rank && event.liturgical.rank !== "Sunday") {
    tags.append(makeTag(event.liturgical.rank));
  }
  (event.associated_devotions || []).forEach((devotion) => {
    tags.append(makeTag(devotion));
  });
  tags.hidden = !tags.children.length;

  return card;
}

function eventsByDate(events) {
  return events.reduce((groups, event) => {
    const key = eventDateKey(event);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(event);
    return groups;
  }, new Map());
}

function makeDayHeading(dateKeyValue, compact = false) {
  const heading = document.createElement("h3");
  heading.className = compact ? "day-heading day-heading-compact" : "day-heading";
  heading.textContent = (compact ? shortDayFormatter : dayHeadingFormatter)
    .format(dateFromKey(dateKeyValue));
  return heading;
}

function makeEmptyDayMessage() {
  const message = document.createElement("p");
  message.className = "empty-day";
  message.textContent = "No matching events";
  return message;
}

function renderDaily(events) {
  const grouped = eventsByDate(events);
  const sections = [...grouped].map(([date, dateEvents]) => {
    const section = document.createElement("section");
    section.className = "day-section";
    section.dataset.eventDate = date;
    section.append(makeDayHeading(date), ...dateEvents.map(renderCard));
    return section;
  });
  elements.events.className = "calendar-view daily-view";
  elements.events.replaceChildren(...sections);
  elements.resultsContext.textContent = "Daily view";
  elements.resultsCount.textContent =
    `${events.length} event${events.length === 1 ? "" : "s"} across ${sections.length} day${sections.length === 1 ? "" : "s"}`;
  elements.emptyMessage.hidden = events.length !== 0;
}

function weekEnd(start) {
  return addDays(start, 6);
}

function weekIntersectsCoverage(start, coverage) {
  return start <= coverage.end && weekEnd(start) >= coverage.start;
}

function renderWeekly(events) {
  const start = state.weekStart;
  const end = weekEnd(start);
  const visible = eventsInRange(events, start, end);
  const grouped = eventsByDate(visible);
  const sections = Array.from({ length: 7 }, (_, index) => {
    const date = addDays(start, index);
    const dateEvents = grouped.get(date) || [];
    const section = document.createElement("section");
    section.className = "week-day";
    section.dataset.eventDate = date;
    if (date === currentBrisbaneDate()) section.classList.add("is-today");
    section.append(makeDayHeading(date, true));
    if (dateEvents.length) {
      section.append(...dateEvents.map(renderCard));
    } else {
      section.append(makeEmptyDayMessage());
    }
    return section;
  });

  const footerNavigation = document.createElement("nav");
  footerNavigation.className = "week-footer-navigation";
  footerNavigation.setAttribute("aria-label", "Week navigation");
  [
    ["previous", "Previous week"],
    ["next", "Next week"],
  ].forEach(([action, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "period-button";
    button.dataset.periodAction = action;
    button.textContent = label;
    button.addEventListener("click", () => navigatePeriod(action));
    footerNavigation.append(button);
  });

  elements.events.className = "calendar-view weekly-view";
  elements.events.replaceChildren(...sections, footerNavigation);
  elements.resultsContext.textContent = "Weekly view";
  elements.resultsCount.textContent =
    `${weekRangeFormatter.format(dateFromKey(start))} – ${weekRangeFormatter.format(dateFromKey(end))} · `
    + `${visible.length} event${visible.length === 1 ? "" : "s"}`;
  elements.emptyMessage.hidden = true;
}

function compactEventTime(event) {
  return event.all_day ? "All day" : timeFormatter.format(new Date(event.start));
}

function compactService(event) {
  if (event.event_type === "mass") return "Mass";
  return event.service_name;
}

function renderMonthCell(date, grouped) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "month-day";
  button.dataset.date = date;
  button.setAttribute("aria-pressed", String(date === state.selectedMonthDate));
  button.setAttribute("aria-label", dayHeadingFormatter.format(dateFromKey(date)));
  if (date === currentBrisbaneDate()) button.classList.add("is-today");
  if (date === state.selectedMonthDate) button.classList.add("is-selected");

  const number = document.createElement("span");
  number.className = "month-day-number";
  number.textContent = String(Number(date.slice(-2)));
  button.append(number);

  const dateEvents = grouped.get(date) || [];
  dateEvents.slice(0, 3).forEach((event) => {
    const summary = document.createElement("span");
    summary.className = "month-event";
    summary.dataset.liturgicalColour = liturgicalColour(event);
    summary.textContent = `${compactEventTime(event)} ${compactService(event)}`;
    button.append(summary);
  });
  if (dateEvents.length > 3) {
    const more = document.createElement("span");
    more.className = "month-more";
    more.textContent = `+${dateEvents.length - 3} more`;
    button.append(more);
  }

  button.addEventListener("click", () => {
    state.selectedMonthDate = date;
    renderEvents();
    document.querySelector(".month-detail")?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "nearest",
    });
  });
  return button;
}

function renderMonthly(events) {
  const month = state.month;
  const dates = monthGrid(month);
  const monthPrefix = month.slice(0, 7);
  const monthEnd = dates.filter((date) => date.startsWith(monthPrefix)).at(-1);
  const visible = eventsInRange(events, month, monthEnd);
  const grouped = eventsByDate(visible);

  const grid = document.createElement("div");
  grid.className = "month-grid";
  grid.setAttribute("role", "grid");
  ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].forEach((weekday) => {
    const heading = document.createElement("div");
    heading.className = "month-weekday";
    heading.setAttribute("role", "columnheader");
    heading.textContent = weekday;
    grid.append(heading);
  });
  dates.forEach((date) => {
    if (!date.startsWith(monthPrefix)) {
      const blank = document.createElement("div");
      blank.className = "month-day month-day-blank";
      blank.setAttribute("aria-hidden", "true");
      grid.append(blank);
    } else {
      grid.append(renderMonthCell(date, grouped));
    }
  });

  const detail = document.createElement("section");
  detail.className = "month-detail";
  const selectedEvents = grouped.get(state.selectedMonthDate) || [];
  detail.append(makeDayHeading(state.selectedMonthDate));
  if (selectedEvents.length) {
    detail.append(...selectedEvents.map(renderCard));
  } else {
    detail.append(makeEmptyDayMessage());
  }

  elements.events.className = "calendar-view monthly-view";
  elements.events.replaceChildren(grid, detail);
  elements.resultsContext.textContent = "Monthly view";
  elements.resultsCount.textContent =
    `${monthHeadingFormatter.format(dateFromKey(month))} · ${visible.length} event${visible.length === 1 ? "" : "s"}`;
  elements.emptyMessage.hidden = true;
}

function monthLastDay(month) {
  return addDays(addMonths(month, 1), -1);
}

function monthIntersectsCoverage(month, coverage) {
  return month <= coverage.end && monthLastDay(month) >= coverage.start;
}

function updatePeriodNavigation() {
  const isDaily = state.view === "daily";
  elements.periodNavigation.hidden = isDaily;
  if (isDaily || !state.feed) return;

  const today = currentBrisbaneDate();
  if (state.view === "weekly") {
    const previous = addDays(state.weekStart, -7);
    const next = addDays(state.weekStart, 7);
    elements.previousPeriod.disabled = !weekIntersectsCoverage(previous, state.feed.coverage);
    elements.nextPeriod.disabled = !weekIntersectsCoverage(next, state.feed.coverage);
    elements.todayPeriod.disabled = state.weekStart === startOfSundayWeek(today);
    elements.previousPeriod.setAttribute("aria-label", "Show previous week");
    elements.nextPeriod.setAttribute("aria-label", "Show next week");
    const footerPrevious = elements.events.querySelector('[data-period-action="previous"]');
    const footerNext = elements.events.querySelector('[data-period-action="next"]');
    if (footerPrevious) footerPrevious.disabled = elements.previousPeriod.disabled;
    if (footerNext) footerNext.disabled = elements.nextPeriod.disabled;
  } else {
    const previous = addMonths(state.month, -1);
    const next = addMonths(state.month, 1);
    elements.previousPeriod.disabled = !monthIntersectsCoverage(previous, state.feed.coverage);
    elements.nextPeriod.disabled = !monthIntersectsCoverage(next, state.feed.coverage);
    elements.todayPeriod.disabled = state.month === monthStart(today);
    elements.previousPeriod.setAttribute("aria-label", "Show previous month");
    elements.nextPeriod.setAttribute("aria-label", "Show next month");
  }
}

function renderEvents() {
  const filtered = state.events.filter(matchesFilters);
  if (state.view === "weekly") {
    renderWeekly(filtered);
  } else if (state.view === "monthly") {
    renderMonthly(filtered);
  } else {
    renderDaily(filtered);
  }
  updatePeriodNavigation();
}

function selectView(button) {
  state.view = button.dataset.view;
  elements.viewButtons.forEach((candidate) => {
    const selected = candidate === button;
    candidate.setAttribute("aria-selected", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
  });
  elements.events.setAttribute("aria-labelledby", button.id);
  renderEvents();
  if (state.view === "daily") scrollToCurrentDay();
}

function navigatePeriod(action) {
  if (state.view === "weekly") {
    state.weekStart = addDays(state.weekStart, action === "previous" ? -7 : 7);
  } else {
    state.month = addMonths(state.month, action === "previous" ? -1 : 1);
    state.selectedMonthDate = state.month < state.feed.coverage.start
      ? state.feed.coverage.start
      : state.month;
  }
  renderEvents();
}

function scrollToCurrentDay() {
  const today = currentBrisbaneDate();
  const target = elements.events.querySelector(`[data-event-date="${today}"]`);
  if (!target) return;

  requestAnimationFrame(() => {
    const header = document.querySelector(".page-header");
    const headerOffset = (header?.getBoundingClientRect().height || 0) + 16;
    target.style.scrollMarginTop = `${headerOffset}px`;
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start",
    });
  });
}

function renderDiagnostics() {
  const feed = state.feed;
  const generated = new Date(feed.generated_at);
  const ageHours = Math.max(0, (Date.now() - generated.getTime()) / 3_600_000);
  elements.diagnosticsSummary.textContent =
    `Feed diagnostics · ${ageHours.toFixed(1)}h old · schema v${feed.schema_version}`;

  const sourceItems = feed.sources.map((source) => (
    `<li><strong>${source.name}</strong>: ${source.status}</li>`
  )).join("");
  const warningItems = feed.warnings.length
    ? feed.warnings.map((warning) => `<li>${warning}</li>`).join("")
    : "<li>None</li>";
  const sourceIds = feed.events.map((event) => (
    `<li><code>${event.id}</code> · <code>${event.source_id}</code></li>`
  )).join("");

  elements.diagnosticsBody.innerHTML = `
    <dl>
      <dt>Generated</dt><dd>${generated.toLocaleString("en-AU")}</dd>
      <dt>Coverage</dt><dd>${feed.coverage.start} to ${feed.coverage.end}</dd>
      <dt>Timezone</dt><dd>${feed.timezone}</dd>
      <dt>Events</dt><dd>${feed.events.length}</dd>
    </dl>
    <h3>Sources</h3><ul>${sourceItems}</ul>
    <h3>Warnings</h3><ul>${warningItems}</ul>
    <details class="source-identifiers">
      <summary>Source identifiers (${feed.events.length})</summary>
      <ul>${sourceIds}</ul>
    </details>
  `;
  elements.diagnostics.hidden = false;
}

function setFiltersToDefaults() {
  Object.values(state.selected).forEach((selection) => selection.clear());
  state.useDefaultEventTypes = true;
  state.search = "";
  elements.search.value = "";
  document.querySelectorAll('.filters input[type="checkbox"]').forEach((input) => {
    input.checked = state.selected[input.dataset.group].has(input.value);
  });
  syncMulticulturalControls();
  renderEvents();
}

function showAllEvents() {
  Object.values(state.selected).forEach((selection) => selection.clear());
  state.useDefaultEventTypes = false;
  state.search = "";
  elements.search.value = "";
  document.querySelectorAll('.filters input[type="checkbox"]').forEach((input) => {
    input.checked = false;
    input.indeterminate = false;
  });
  renderEvents();
}

function setFiltersExpanded(expanded) {
  elements.filtersToggle.setAttribute("aria-expanded", String(expanded));
  elements.filtersToggle.setAttribute(
    "aria-label",
    `${expanded ? "Collapse" : "Expand"} calendar filters`,
  );
  elements.filtersContent.hidden = !expanded;
  elements.filters.classList.toggle("filters-collapsed", !expanded);
}

function initializeMobileFilters() {
  const mobile = window.matchMedia("(max-width: 800px)");
  setFiltersExpanded(!mobile.matches);
  mobile.addEventListener("change", (event) => setFiltersExpanded(!event.matches));
}

async function loadEvents() {
  try {
    const response = await fetch(FEED_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`Calendar feed returned ${response.status}.`);
    const feed = await response.json();
    validateFeed(feed);
    state.feed = feed;
    state.events = feed.events;
    const today = currentBrisbaneDate();
    const initialDate = today < feed.coverage.start
      ? feed.coverage.start
      : today > feed.coverage.end ? feed.coverage.end : today;
    state.weekStart = startOfSundayWeek(initialDate);
    state.month = monthStart(initialDate);
    state.selectedMonthDate = initialDate;
    buildFilters();
    renderDiagnostics();
    renderEvents();
    scrollToCurrentDay();
  } catch (error) {
    elements.resultsCount.textContent = "Calendar unavailable";
    elements.errorMessage.hidden = false;
    elements.errorMessage.textContent =
      `${error.message} Serve this folder with a local web server so the page can read ${FEED_URL}.`;
  }
}

elements.search.addEventListener("input", (event) => {
  state.search = event.target.value.trim().toLocaleLowerCase();
  renderEvents();
});
document.querySelectorAll(".filter-toggle").forEach((toggle) => {
  toggle.addEventListener("click", () => {
    const content = document.querySelector(`#${toggle.getAttribute("aria-controls")}`);
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    content.hidden = expanded;
  });
});
elements.resetFilters.addEventListener("click", setFiltersToDefaults);
elements.clearFilters.addEventListener("click", showAllEvents);
elements.filtersToggle.addEventListener("click", () => {
  setFiltersExpanded(elements.filtersToggle.getAttribute("aria-expanded") !== "true");
});
elements.viewButtons.forEach((button) => {
  button.addEventListener("click", () => selectView(button));
  button.addEventListener("keydown", (event) => {
    const currentIndex = elements.viewButtons.indexOf(button);
    const nextIndex = {
      ArrowLeft: (currentIndex - 1 + elements.viewButtons.length) % elements.viewButtons.length,
      ArrowRight: (currentIndex + 1) % elements.viewButtons.length,
      Home: 0,
      End: elements.viewButtons.length - 1,
    }[event.key];
    if (nextIndex === undefined) return;
    event.preventDefault();
    const nextButton = elements.viewButtons[nextIndex];
    selectView(nextButton);
    nextButton.focus();
  });
});
elements.previousPeriod.addEventListener("click", () => navigatePeriod("previous"));
elements.nextPeriod.addEventListener("click", () => navigatePeriod("next"));
elements.todayPeriod.addEventListener("click", () => {
  const today = currentBrisbaneDate();
  const target = today < state.feed.coverage.start
    ? state.feed.coverage.start
    : today > state.feed.coverage.end ? state.feed.coverage.end : today;
  state.weekStart = startOfSundayWeek(target);
  state.month = monthStart(target);
  state.selectedMonthDate = target;
  renderEvents();
});

initializeMobileFilters();
loadEvents();
