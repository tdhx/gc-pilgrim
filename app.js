import { matchesEvent, validateFeed } from "./web/calendar-core.js";

const FEED_URL = "feeds/v1/calendar.json";
const DEFAULT_EVENT_TYPES = ["mass", "confession"];
const MULTICULTURAL_TYPE = "multicultural";

const state = {
  events: [],
  feed: null,
  selected: {
    eventType: new Set(DEFAULT_EVENT_TYPES),
    multiculturalSubtype: new Set(),
    church: new Set(),
    presider: new Set(),
  },
  search: "",
};

const elements = {
  events: document.querySelector("#events"),
  resultsCount: document.querySelector("#results-count"),
  eventTypeFilters: document.querySelector("#event-type-filters"),
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
};

const dateFormatter = new Intl.DateTimeFormat("en-AU", {
  timeZone: "Australia/Brisbane",
  weekday: "short",
  day: "numeric",
  month: "short",
});

const timeFormatter = new Intl.DateTimeFormat("en-AU", {
  timeZone: "Australia/Brisbane",
  hour: "numeric",
  minute: "2-digit",
});

function titleCase(value) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function eventTypeLabel(value) {
  return {
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
  const eventTypes = uniqueValues((event) => [event.event_type]);

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
  buildCheckboxes(
    elements.presiderFilters,
    "presider",
    uniqueValues((event) => event.presiders),
  );
}

function matchesFilters(event) {
  return matchesEvent(event, state.selected, state.search);
}

function formatDateParts(event) {
  const value = event.all_day ? new Date(`${event.start}T00:00:00+10:00`) : new Date(event.start);
  const parts = dateFormatter.formatToParts(value);
  return Object.fromEntries(parts.map((part) => [part.type, part.value]));
}

function formatEventTime(event) {
  if (event.all_day) return "All day";
  return `${timeFormatter.format(new Date(event.start))}–${timeFormatter.format(new Date(event.end))}`;
}

function eventDate(event) {
  return event.start.slice(0, 10);
}

function isVigilMass(event) {
  return event.service_name === "Vigil Mass";
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
  const dateParts = formatDateParts(event);
  card.classList.add(churchClass(event.church));

  card.querySelector(".event-day").textContent = dateParts.weekday;
  card.querySelector(".event-number").textContent = dateParts.day;
  card.querySelector(".event-month").textContent = dateParts.month;
  card.querySelector(".event-time").textContent = formatEventTime(event);
  card.querySelector(".event-type").textContent = event.service_name;
  card.querySelector(".event-title").textContent =
    event.liturgical?.observance || event.service_name;

  const tags = card.querySelector(".event-tags");
  tags.append(makeTag(`Church: ${displayChurch(event.church)}`));
  if (event.presiders.length) {
    tags.append(makeTag(`Presider: ${event.presiders.join(", ")}`));
  } else {
    tags.append(makeTag("Presider: TBA"));
  }
  if (isVigilMass(event)) {
    tags.append(makeTag("Vigil"));
  } else if (event.liturgical?.rank) {
    tags.append(makeTag(event.liturgical.rank));
  }
  if (event.liturgical?.season) {
    tags.append(makeTag(event.liturgical.season));
  }
  (event.associated_devotions || []).forEach((devotion) => {
    tags.append(makeTag(devotion));
  });

  return card;
}

function renderEvents() {
  const filtered = state.events.filter(matchesFilters);
  elements.events.replaceChildren(...filtered.map(renderCard));
  elements.resultsCount.textContent = `${filtered.length} event${filtered.length === 1 ? "" : "s"}`;
  elements.emptyMessage.hidden = filtered.length !== 0;
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
  DEFAULT_EVENT_TYPES.forEach((value) => state.selected.eventType.add(value));
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
  state.search = "";
  elements.search.value = "";
  document.querySelectorAll('.filters input[type="checkbox"]').forEach((input) => {
    input.checked = false;
    input.indeterminate = false;
  });
  renderEvents();
}

async function loadEvents() {
  try {
    const response = await fetch(FEED_URL);
    if (!response.ok) throw new Error(`Calendar feed returned ${response.status}.`);
    const feed = await response.json();
    validateFeed(feed);
    state.feed = feed;
    state.events = feed.events;
    buildFilters();
    renderDiagnostics();
    renderEvents();
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

loadEvents();
