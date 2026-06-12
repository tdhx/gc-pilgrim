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
  orderedChurches,
  orderedEventTypes,
  presiderGroups,
  aggregateCalendars,
  assembleCalendar,
  selectedParishId,
  startOfSundayWeek,
  validateRegistry,
} from "./web/calendar-core.js?v=8";
import {
  readPreferences,
  resolvedTheme,
  savePreferences,
  showRichLiturgicalInformation,
} from "./web/theme-preferences.js?v=2";

const FEED_ROOT = "feeds/v1";
const DEFAULT_EVENT_TYPES = ["mass", "confession"];
const MULTICULTURAL_TYPE = "multicultural";
const MULTICULTURAL_PRESIDER_SUBTYPES = new Map([
  ["Fr Fadi", ["maronite"]],
  ["Fr Jerzy", ["polish"]],
  ["Fr Luis", ["hispanic", "italian"]],
]);

const state = {
  events: [],
  feed: null,
  selected: {
    eventType: new Set(),
    multiculturalSubtype: new Set(),
    church: new Set(),
    presider: new Set(),
  },
  useDefaultEventTypes: true,
  view: "weekly",
  pendingView: null,
  filtersScrollY: null,
  weekStart: null,
  month: null,
  selectedMonthDate: null,
  dailyDaysVisible: 7,
  parishName: null,
  isAggregate: false,
  parishTheme: "gc-pilgrim",
  preferences: readPreferences(window.localStorage),
};

const elements = {
  events: document.querySelector("#events"),
  resultsContext: document.querySelector("#results-context"),
  resultsCount: document.querySelector("#results-count"),
  eventTypeFilters: document.querySelector("#event-type-filters"),
  filters: document.querySelector("#filters"),
  filtersContent: document.querySelector("#filters-content"),
  filtersToggle: document.querySelector("#filters-toggle"),
  filtersBackdrop: document.querySelector("#filters-backdrop"),
  filtersClose: document.querySelector("#filters-close"),
  churchFilters: document.querySelector("#church-filters"),
  presiderFilters: document.querySelector("#presider-filters"),
  showAllButtons: [...document.querySelectorAll("[data-show-all]")],
  resultsHeader: document.querySelector(".results-header"),
  resultsToday: document.querySelector("#results-today"),
  emptyMessage: document.querySelector("#empty-message"),
  errorMessage: document.querySelector("#error-message"),
  template: document.querySelector("#event-template"),
  viewButtons: [...document.querySelectorAll(".view-button")],
  periodNavigations: [...document.querySelectorAll(".period-navigation")],
  previousPeriods: [...document.querySelectorAll('[data-period-control="previous"]')],
  nextPeriods: [...document.querySelectorAll('[data-period-control="next"]')],
  navigationToggle: document.querySelector("#navigation-toggle"),
  siteNavigation: document.querySelector("#site-navigation"),
  navigationLinks: [...document.querySelectorAll(".navigation-link")],
  aboutNavigationLink: document.querySelector("#about-navigation-link"),
  pagePanels: [...document.querySelectorAll("[data-page-panel]")],
  pageTitle: document.querySelector("#page-title"),
  parishSelectorToggle: document.querySelector("#parish-selector-toggle"),
  parishName: document.querySelector("#parish-name"),
  aboutEyebrow: document.querySelector("#about-eyebrow"),
  parishOfficeAddress: document.querySelector("#parish-office-address"),
  parishPhone: document.querySelector("#parish-phone"),
  parishEmail: document.querySelector("#parish-email"),
  parishWebsite: document.querySelector("#parish-website"),
  parishHours: document.querySelector("#parish-hours"),
  parishHoursCard: document.querySelector("#parish-hours-card"),
  parishClergy: document.querySelector("#parish-clergy"),
  parishClergyCard: document.querySelector("#parish-clergy-card"),
  parishChurches: document.querySelector("#parish-churches"),
  parishLocationsTitle: document.querySelector("#parish-locations-title"),
  aboutContent: document.querySelector("#about-content"),
  aboutError: document.querySelector("#about-error"),
  aboutLogo: document.querySelector("#about-logo"),
  brandLogo: document.querySelector("#parish-logo"),
  selectedRegionName: document.querySelector("#selected-region-name"),
  parishTagline: document.querySelector("#parish-tagline"),
  parishSelector: document.querySelector("#parish-selector"),
  themeChoices: [...document.querySelectorAll('input[name="theme"]')],
  liturgicalDetailChoices: [
    ...document.querySelectorAll('input[name="liturgical-detail"]'),
  ],
  themeColor: document.querySelector("#theme-color"),
};
const mobileLayout = window.matchMedia("(max-width: 800px)");

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

const monthNameFormatter = new Intl.DateTimeFormat("en-AU", {
  timeZone: "UTC",
  month: "long",
});

function titleCase(value) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function closeParishSelector() {
  elements.parishSelectorToggle.setAttribute("aria-expanded", "false");
  elements.parishSelector.hidden = true;
}

function closeNavigation() {
  elements.navigationToggle.setAttribute("aria-expanded", "false");
  elements.navigationToggle.setAttribute("aria-label", "Open navigation");
  elements.siteNavigation.classList.remove("navigation-open");
}

function applyThemePreferences() {
  const theme = resolvedTheme(state.preferences.theme, state.parishTheme);
  document.documentElement.dataset.themeChoice = state.preferences.theme;
  document.body.dataset.themeChoice = state.preferences.theme;
  document.body.dataset.theme = theme;
  elements.themeColor.content = theme === "traditional" ? "#F0EBDE" : "#ffffff";
  elements.themeChoices.forEach((input) => {
    input.checked = input.value === state.preferences.theme;
  });
  elements.liturgicalDetailChoices.forEach((input) => {
    input.checked = input.value === state.preferences.liturgicalDetail;
  });
}

function showPage(page) {
  const selectedPage = ["about", "settings"].includes(page) ? page : "calendar";
  elements.pagePanels.forEach((panel) => {
    panel.hidden = panel.dataset.pagePanel !== selectedPage;
  });
  elements.navigationLinks.forEach((link) => {
    if (link.dataset.page === selectedPage) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  const aboutTitle = state.isAggregate ? "About GC Pilgrim" : "About the Parish";
  const sectionTitle = selectedPage === "about"
    ? aboutTitle
    : selectedPage === "settings" ? "Settings" : "Calendar";
  elements.pageTitle.textContent = sectionTitle;
  document.title = state.parishName
    ? `${sectionTitle} · ${state.parishName} · GC Pilgrim`
    : selectedPage === "about" ? "About GC Pilgrim"
    : selectedPage === "settings" ? "Settings · GC Pilgrim"
    : "GC Pilgrim";
  closeNavigation();
  window.scrollTo({ top: 0, behavior: "auto" });
  updateStickyOffset();
}

function currentPageFromHash() {
  const page = window.location.hash.slice(1);
  return ["about", "settings"].includes(page) ? page : "calendar";
}

function displayHours(value) {
  const format = (time) => {
    const [hour, minute] = time.split(":").map(Number);
    return `${hour % 12 || 12}:${String(minute).padStart(2, "0")}${hour >= 12 ? "pm" : "am"}`;
  };
  const [start, end] = value.split("-");
  return `${format(start)} - ${format(end)}`;
}

function renderParish(parish) {
  state.isAggregate = false;
  state.parishName = parish.name;
  elements.selectedRegionName.hidden = true;
  elements.selectedRegionName.textContent = "";
  elements.aboutNavigationLink.textContent = "About the Parish";
  elements.aboutEyebrow.textContent = "Our parish";
  elements.parishName.textContent = parish.name;
  elements.parishTagline.textContent = parish.branding?.tagline || "";
  elements.parishTagline.hidden = !elements.parishTagline.textContent;
  elements.brandLogo.hidden = false;
  elements.brandLogo.src = parish.branding?.logo || "assets/gc-pilgrim.svg";
  elements.brandLogo.alt = parish.name;
  elements.aboutLogo.src = parish.branding?.logo || "assets/gc-pilgrim.svg";
  elements.aboutLogo.alt = `${parish.name} logo`;
  state.parishTheme = parish.branding?.theme || "gc-pilgrim";
  applyThemePreferences();

  const contact = parish.contact || {};
  const office = parish.office || {};
  elements.parishOfficeAddress.textContent = office.address || "";
  elements.parishPhone.hidden = !contact.phone;
  elements.parishEmail.hidden = !contact.email;
  elements.parishWebsite.hidden = !contact.website;
  if (contact.phone) {
    elements.parishPhone.href = `tel:${contact.phone.replace(/[^\d+]/g, "")}`;
    elements.parishPhone.textContent = contact.phone;
  }
  if (contact.email) {
    elements.parishEmail.href = `mailto:${contact.email}`;
    elements.parishEmail.textContent = contact.email;
  }
  if (contact.website) elements.parishWebsite.href = contact.website;

  const weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"];
  const availableDays = weekdays.filter((day) => office.hours?.[day]);
  elements.parishHoursCard.hidden = availableDays.length === 0;
  elements.parishHours.replaceChildren(...availableDays.map((day) => {
    const hours = office.hours[day];
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = titleCase(day);
    description.textContent = displayHours(hours);
    row.append(term, description);
    return row;
  }));

  elements.parishClergyCard.hidden = !parish.clergy?.length;
  elements.parishClergy.replaceChildren(...(parish.clergy || []).map((member) => {
    const item = document.createElement("article");
    const name = document.createElement("h4");
    const role = document.createElement("p");
    name.textContent = member.name;
    role.textContent = member.role;
    item.append(name, role);
    return item;
  }));

  const hasMassLocations = parish.churches.some((church) => (
    ["chaplaincy", "mass-centre", "retirement-community"].includes(church.location_type)
  ));
  elements.parishLocationsTitle.textContent = hasMassLocations
    ? "Churches and Mass locations"
    : "Churches";
  elements.parishChurches.replaceChildren(...orderedChurches(parish.churches).map((church) => {
    const item = document.createElement("article");
    const heading = document.createElement("div");
    const name = document.createElement("h4");
    const address = document.createElement("p");
    name.textContent = church.name;
    address.textContent = church.address || "";
    address.hidden = !church.address;
    heading.append(name);
    if (church.is_primary_site) {
      const badge = document.createElement("span");
      badge.className = "primary-site-badge";
      badge.textContent = "Primary church";
      heading.append(badge);
    } else if (church.status === "temporarily-closed") {
      const badge = document.createElement("span");
      badge.className = "primary-site-badge";
      badge.textContent = "Temporarily closed";
      heading.append(badge);
    } else if (church.location_type === "chaplaincy") {
      const badge = document.createElement("span");
      badge.className = "primary-site-badge";
      badge.textContent = "Chaplaincy";
      heading.append(badge);
    } else if (church.location_type === "mass-centre") {
      const badge = document.createElement("span");
      badge.className = "primary-site-badge";
      badge.textContent = "Mass centre";
      heading.append(badge);
    } else if (church.location_type === "retirement-community") {
      const badge = document.createElement("span");
      badge.className = "primary-site-badge";
      badge.textContent = "Retirement community";
      heading.append(badge);
    }
    item.append(heading, address);
    return item;
  }));
  elements.aboutContent.hidden = false;
  showPage(currentPageFromHash());
}

function renderAggregateAbout(aggregateView, parishes) {
  state.isAggregate = true;
  state.parishName = aggregateView.name;
  elements.aboutNavigationLink.textContent = "About GC Pilgrim";
  elements.aboutEyebrow.textContent = "Across the Gold Coast";
  elements.parishName.textContent = "About GC Pilgrim";
  elements.parishTagline.textContent =
    "One calendar for Catholic worship and parish life across the Gold Coast.";
  elements.parishTagline.hidden = false;
  elements.brandLogo.hidden = true;
  elements.brandLogo.removeAttribute("src");
  elements.brandLogo.alt = "";
  elements.aboutLogo.src = "assets/gold-coast-mascot.png";
  elements.aboutLogo.alt = "GC Pilgrim mascot";
  elements.selectedRegionName.textContent = "All Gold Coast";
  elements.selectedRegionName.hidden = false;
  state.parishTheme = "gc-pilgrim";
  applyThemePreferences();

  const appCard = document.createElement("section");
  appCard.className = "about-card";
  appCard.innerHTML = `
    <p class="about-card-label">About the app</p>
    <h3>A shared Catholic calendar</h3>
    <p class="about-card-copy">
      GC Pilgrim brings together public schedules from Gold Coast Catholic
      parishes. Choose a parish for its own calendar and contact details, or
      All Gold Coast to explore every available event in one place.
    </p>
  `;

  const parishesCard = document.createElement("section");
  parishesCard.className = "about-card about-churches";
  const label = document.createElement("p");
  label.className = "about-card-label";
  label.textContent = "Participating communities";
  const title = document.createElement("h3");
  title.textContent = "Parishes and locations";
  const list = document.createElement("div");
  list.className = "aggregate-parish-list";
  parishes.forEach((parish) => {
    const group = document.createElement("section");
    const heading = document.createElement("h4");
    heading.textContent = parish.name;
    const churches = document.createElement("div");
    churches.className = "church-list";
    churches.replaceChildren(...orderedChurches(parish.churches).map((church) => {
      const item = document.createElement("article");
      const name = document.createElement("h5");
      const address = document.createElement("p");
      name.textContent = church.name;
      address.textContent = church.address || "";
      address.hidden = !church.address;
      item.append(name, address);
      return item;
    }));
    group.append(heading, churches);
    list.append(group);
  });
  parishesCard.append(label, title, list);
  elements.aboutContent.replaceChildren(appCard, parishesCard);
  elements.aboutContent.hidden = false;
  showPage(currentPageFromHash());
}

function eventTypeLabel(value) {
  return {
    baptism: "Baptisms",
    confession: "Reconciliation (Confession)",
    multicultural: "Multicultural Masses",
    community: "Parish Life",
  }[value] || titleCase(value);
}

function renderServiceTag(element, event) {
  if (event.event_type !== "confession") {
    element.textContent = event.service_name;
    return;
  }
  const primary = document.createElement("span");
  const secondary = document.createElement("span");
  primary.textContent = "Reconciliation";
  secondary.textContent = "(Confession)";
  element.classList.add("event-service-confession");
  element.replaceChildren(primary, secondary);
}

function multiculturalSubtype(event) {
  if (event.event_subtype) return event.event_subtype;
  const match = event.title.toLocaleLowerCase().match(/\b(hispanic|maronite|polish|italian)\s+mass\b/);
  return match ? match[1] : null;
}

function subtypeLabel(value) {
  if (value === "syro-malabar") return "Syro-Malabar Mass";
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

function cloneSelections() {
  return Object.fromEntries(
    Object.entries(state.selected).map(([group, values]) => [group, new Set(values)]),
  );
}

function selectMulticulturalPresider(selection, presider) {
  const subtypes = MULTICULTURAL_PRESIDER_SUBTYPES.get(presider);
  if (!subtypes) return false;
  selection.eventType.add(MULTICULTURAL_TYPE);
  subtypes.forEach((subtype) => selection.multiculturalSubtype.add(subtype));
  return true;
}

function selectionsForCount(group, value) {
  const selected = cloneSelections();
  selected[group].clear();
  selected[group].add(value);

  if (group === "eventType") {
    selected.multiculturalSubtype.clear();
  } else if (group === "multiculturalSubtype") {
    selected.eventType.clear();
    selected.eventType.add(MULTICULTURAL_TYPE);
  } else if (group === "presider") {
    selectMulticulturalPresider(selected, value);
  }
  return selected;
}

function countFor(group, value) {
  const selected = selectionsForCount(group, value);
  const defaults = group === "eventType" || selected.eventType.size
    ? []
    : state.useDefaultEventTypes ? DEFAULT_EVENT_TYPES : [];
  return state.events.filter((event) => (
    matchesEvent(event, selected, "", defaults)
  )).length;
}

function updateFilterCounts() {
  document.querySelectorAll(".checkbox-option input").forEach((input) => {
    const count = input.closest(".checkbox-option")?.querySelector(".filter-count");
    if (count) count.textContent = countFor(input.dataset.group, input.value);
  });
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
      if (group === "presider" && input.checked && selectMulticulturalPresider(state.selected, value)) {
        state.useDefaultEventTypes = false;
        syncFilterControls();
      }
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

function syncFilterControls() {
  document.querySelectorAll('.filters input[type="checkbox"]').forEach((input) => {
    input.checked = state.selected[input.dataset.group].has(input.value);
    input.indeterminate = false;
  });
  syncMulticulturalControls();
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
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-controls", children.id);
      toggle.setAttribute("aria-label", "Expand Multicultural Mass options");

      const toggleIcon = document.createElement("span");
      toggleIcon.className = "filter-toggle-icon";
      toggleIcon.setAttribute("aria-hidden", "true");
      toggle.append(toggleIcon);
      heading.append(toggle);
      wrapper.replaceChildren(heading);
      children.hidden = true;

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
  const eventTypes = uniqueValues((event) => [event.event_type]);
  const churches = uniqueValues((event) => [displayChurch(event.church)]);
  const presiders = uniqueValues((event) => event.presiders);

  buildEventTypeFilters();
  elements.eventTypeFilters.closest(".filter-section").hidden = eventTypes.length === 0;
  buildCheckboxes(
    elements.churchFilters,
    "church",
    churches,
  );
  elements.churchFilters.closest(".filter-section").hidden = churches.length === 0;
  elements.presiderFilters.replaceChildren();
  presiderGroups(presiders).forEach((group, index) => {
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
  elements.presiderFilters.closest(".filter-section").hidden = presiders.length === 0;
}

function matchesFilters(event) {
  return matchesEvent(
    event,
    state.selected,
    "",
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

function eventAccentColour(event) {
  return {
    adoration: "gold",
    confession: "violet",
    rosary: "red",
    novena: "gold",
  }[event.event_type] || liturgicalColour(event);
}

function eventHasEnded(event, now = Date.now()) {
  return new Date(event.end).getTime() <= now;
}

function setPastState(element, ended) {
  element.classList.toggle("is-past", ended);
  element.dataset.past = String(ended);
}

function updatePastStates(now = Date.now()) {
  document.querySelectorAll("[data-event-end]").forEach((element) => {
    setPastState(element, Number(element.dataset.eventEnd) <= now);
  });
}

function renderCard(event) {
  const card = elements.template.content.firstElementChild.cloneNode(true);
  const imageClass = churchClass(event.church);
  card.classList.add(imageClass);
  if (
    imageClass === "church-unassigned"
    && ["mass", MULTICULTURAL_TYPE].includes(event.event_type)
  ) {
    card.classList.add("event-mass-fallback");
  }
  card.dataset.eventDate = eventDateKey(event);
  card.dataset.eventEnd = String(new Date(event.end).getTime());
  card.dataset.liturgicalColour = eventAccentColour(event);
  setPastState(card, eventHasEnded(event));

  card.querySelector(".event-church").textContent = displayChurch(event.church);
  renderServiceTag(card.querySelector(".event-service"), event);
  const parish = card.querySelector(".event-parish");
  parish.textContent = event.parish_name || "";
  parish.hidden = !state.isAggregate || !parish.textContent;
  card.querySelector(".event-time").textContent = formatEventTime(event);
  const presider = card.querySelector(".event-presider");
  presider.textContent = event.presiders.map(displayPresider).join(", ");
  presider.hidden = !presider.textContent;
  const subtitle = card.querySelector(".event-subtitle");
  const richLiturgicalInformation = showRichLiturgicalInformation(
    state.preferences.liturgicalDetail,
  );
  const observance = richLiturgicalInformation
    ? event.liturgical?.observance
    : "";
  subtitle.textContent = observance && observance !== event.service_name ? observance : "";
  subtitle.hidden = !subtitle.textContent;

  const tags = card.querySelector(".event-tags");
  if (
    richLiturgicalInformation
    && event.liturgical?.rank
    && event.liturgical.rank !== "Sunday"
  ) {
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
  const start = dailyRangeStart();
  const end = dailyRangeEnd(events, start);
  const displayedDays = Math.round(
    (dateFromKey(end) - dateFromKey(start)) / 86_400_000,
  ) + 1;
  const visible = eventsInRange(events, start, end);
  const grouped = eventsByDate(visible);
  const sections = [...grouped].map(([date, dateEvents]) => {
    const section = document.createElement("section");
    section.className = "day-section";
    section.dataset.eventDate = date;
    section.append(makeDayHeading(date), ...dateEvents.map(renderCard));
    return section;
  });

  const loadMore = document.createElement("button");
  loadMore.type = "button";
  loadMore.className = "load-more-button";
  loadMore.textContent = "Load more";
  loadMore.addEventListener("click", () => {
    state.dailyDaysVisible = displayedDays + 14;
    renderEvents();
  });

  const canLoadMore = end < state.feed.coverage.end;
  elements.events.className = "calendar-view daily-view";
  elements.events.replaceChildren(...sections, ...(canLoadMore ? [loadMore] : []));
  elements.resultsContext.textContent = "Daily";
  elements.resultsCount.textContent =
    `${visible.length} event${visible.length === 1 ? "" : "s"} · ${displayedDays} days`;
  elements.emptyMessage.hidden = visible.length !== 0;
}

function dailyRangeEnd(events, start, minimumEvents = 10) {
  const requestedEnd = addDays(start, state.dailyDaysVisible - 1);
  let end = requestedEnd < state.feed.coverage.end
    ? requestedEnd
    : state.feed.coverage.end;
  while (
    end < state.feed.coverage.end
    && eventsInRange(events, start, end).length < minimumEvents
  ) {
    end = addDays(end, 1);
  }
  return end;
}

function dailyRangeStart() {
  const today = currentBrisbaneDate();
  if (today < state.feed.coverage.start) return state.feed.coverage.start;
  if (today > state.feed.coverage.end) return state.feed.coverage.end;
  return today;
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
    ["previous", "\u2039 Previous week"],
    ["next", "Next week \u203a"],
  ].forEach(([action, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "period-button";
    button.dataset.periodAction = action;
    button.textContent = label;
    button.addEventListener("click", () => navigatePeriod(action, true));
    footerNavigation.append(button);
  });

  elements.events.className = "calendar-view weekly-view";
  elements.events.replaceChildren(...sections, footerNavigation);
  elements.resultsContext.textContent = "Weekly";
  elements.resultsCount.textContent =
    `${weekRangeFormatter.format(dateFromKey(start))}–${weekRangeFormatter.format(dateFromKey(end))} · `
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
    summary.dataset.eventEnd = String(new Date(event.end).getTime());
    summary.dataset.liturgicalColour = eventAccentColour(event);
    setPastState(summary, eventHasEnded(event));
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
  elements.resultsContext.textContent = "Monthly";
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
  elements.periodNavigations.forEach((navigation) => {
    navigation.hidden = isDaily;
  });
  if (isDaily || !state.feed) return;

  if (state.view === "weekly") {
    const previous = addDays(state.weekStart, -7);
    const next = addDays(state.weekStart, 7);
    elements.previousPeriods.forEach((button) => {
      button.disabled = !weekIntersectsCoverage(previous, state.feed.coverage);
      button.setAttribute("aria-label", "Show previous week");
      button.textContent = "\u2039 Previous week";
    });
    elements.nextPeriods.forEach((button) => {
      button.disabled = !weekIntersectsCoverage(next, state.feed.coverage);
      button.setAttribute("aria-label", "Show next week");
      button.textContent = "Next week \u203a";
    });
    const footerPrevious = elements.events.querySelector('[data-period-action="previous"]');
    const footerNext = elements.events.querySelector('[data-period-action="next"]');
    if (footerPrevious) footerPrevious.disabled = elements.previousPeriods[0].disabled;
    if (footerNext) footerNext.disabled = elements.nextPeriods[0].disabled;
  } else {
    const previous = addMonths(state.month, -1);
    const next = addMonths(state.month, 1);
    elements.previousPeriods.forEach((button) => {
      button.disabled = !monthIntersectsCoverage(previous, state.feed.coverage);
      button.setAttribute("aria-label", "Show previous month");
      button.textContent = `\u2039 ${monthNameFormatter.format(dateFromKey(previous))}`;
    });
    elements.nextPeriods.forEach((button) => {
      button.disabled = !monthIntersectsCoverage(next, state.feed.coverage);
      button.setAttribute("aria-label", "Show next month");
      button.textContent = `${monthNameFormatter.format(dateFromKey(next))} \u203a`;
    });
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
  updateFilterCounts();
  updatePastStates();
}

function isMobileLayout() {
  return mobileLayout.matches;
}

function syncViewButtons(view) {
  elements.viewButtons.forEach((candidate) => {
    const selected = candidate.dataset.view === view;
    candidate.setAttribute("aria-selected", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
  });
}

function applyView(view, previousScrollY = window.scrollY) {
  elements.events.style.minHeight = "";
  state.view = view;
  state.pendingView = null;
  if (state.view === "daily") state.dailyDaysVisible = 7;
  syncViewButtons(view);
  elements.events.setAttribute("aria-labelledby", `view-${view}`);
  resetViewToToday();
  if (view === "monthly") {
    requestAnimationFrame(() => {
      const requiredDocumentHeight = previousScrollY + window.innerHeight;
      const heightDeficit = requiredDocumentHeight - document.documentElement.scrollHeight;
      if (heightDeficit > 0) {
        const eventsHeight = elements.events.getBoundingClientRect().height;
        elements.events.style.minHeight = `${eventsHeight + heightDeficit}px`;
      }
      window.scrollTo({ top: previousScrollY, behavior: "auto" });
    });
  } else {
    scrollToCurrentDayIfLow();
  }
}

function selectView(button) {
  const view = button.dataset.view;
  if (isMobileLayout() && elements.filtersToggle.getAttribute("aria-expanded") === "true") {
    state.pendingView = view;
    syncViewButtons(view);
    return;
  }
  applyView(view);
}

function navigatePeriod(action, scrollToTop = false) {
  if (state.view === "weekly") {
    state.weekStart = addDays(state.weekStart, action === "previous" ? -7 : 7);
  } else {
    state.month = addMonths(state.month, action === "previous" ? -1 : 1);
    state.selectedMonthDate = state.month < state.feed.coverage.start
      ? state.feed.coverage.start
      : state.month;
  }
  renderEvents();
  if (scrollToTop) scrollToActivePeriod();
}

function stickyScrollOffset() {
  const header = document.querySelector(".page-header");
  return (header?.getBoundingClientRect().height || 0)
    + (elements.resultsHeader?.getBoundingClientRect().height || 0)
    + 22;
}

function scrollToCurrentDay() {
  const today = currentBrisbaneDate();
  const target = (state.view === "monthly"
    ? elements.events.querySelector(`[data-date="${today}"]`)
    : elements.events.querySelector(`[data-event-date="${today}"]`))
    || elements.events.firstElementChild;
  if (!target) return;

  requestAnimationFrame(() => {
    target.style.scrollMarginTop = `${stickyScrollOffset()}px`;
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start",
    });
  });
}

function scrollToCurrentDayIfLow() {
  requestAnimationFrame(() => {
    const today = currentBrisbaneDate();
    const target = elements.events.querySelector(`[data-event-date="${today}"]`)
      || elements.events.firstElementChild;
    if (!target) return;
    const bounds = target.getBoundingClientRect();
    const upperThird = window.innerHeight / 3;
    const lowerThird = window.innerHeight * (2 / 3);
    if (bounds.top >= upperThird && bounds.top <= lowerThird) return;
    target.style.scrollMarginTop = `${stickyScrollOffset()}px`;
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start",
    });
  });
}

function scrollToActivePeriod() {
  requestAnimationFrame(() => {
    const target = state.view === "weekly"
      ? document.querySelector(".calendar-toolbar")
      : state.view === "monthly"
      ? elements.events.querySelector(".month-grid")
      : elements.events.firstElementChild;
    if (!target) return;
    target.style.scrollMarginTop = `${stickyScrollOffset()}px`;
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start",
    });
  });
}

function showAllEvents() {
  Object.values(state.selected).forEach((selection) => selection.clear());
  state.useDefaultEventTypes = false;
  syncFilterControls();
  renderEvents();
}

function resetViewToToday() {
  const today = currentBrisbaneDate();
  const target = today < state.feed.coverage.start
    ? state.feed.coverage.start
    : today > state.feed.coverage.end ? state.feed.coverage.end : today;

  if (state.view === "daily") {
    state.dailyDaysVisible = 7;
  } else if (state.view === "weekly") {
    state.weekStart = startOfSundayWeek(target);
  } else {
    state.month = monthStart(target);
    state.selectedMonthDate = target;
  }
  renderEvents();
}

function goToToday() {
  resetViewToToday();
  requestAnimationFrame(scrollToCurrentDay);
}

function updateStickyOffset() {
  const headerHeight = document.querySelector(".page-header")?.getBoundingClientRect().height || 0;
  const resultsHeaderHeight = elements.resultsHeader?.getBoundingClientRect().height || 0;
  document.documentElement.style.setProperty("--page-header-height", `${headerHeight}px`);
  document.documentElement.style.setProperty("--results-header-height", `${resultsHeaderHeight}px`);
}

function setFiltersExpanded(expanded) {
  if (!isMobileLayout()) {
    elements.filtersToggle.setAttribute("aria-expanded", "true");
    elements.filtersContent.hidden = false;
    elements.filters.classList.remove("filters-collapsed");
    elements.filtersBackdrop.hidden = true;
    document.body.classList.remove("filters-open");
    document.body.style.top = "";
    return;
  }

  const openingScrollY = expanded ? window.scrollY : null;
  elements.filtersToggle.setAttribute("aria-expanded", String(expanded));
  elements.filtersToggle.setAttribute("aria-label", expanded ? "Close filters" : "Open filters");
  elements.filtersContent.hidden = !expanded;
  elements.filters.classList.toggle("filters-collapsed", !expanded);
  elements.filtersBackdrop.hidden = !expanded;
  if (expanded) {
    state.pendingView = state.view;
    state.filtersScrollY = openingScrollY;
    syncViewButtons(state.pendingView);
    document.body.style.top = `-${openingScrollY}px`;
    document.body.classList.add("filters-open");
    elements.filtersClose.focus();
  } else {
    const pendingView = state.pendingView;
    const filtersScrollY = state.filtersScrollY ?? window.scrollY;
    document.body.classList.remove("filters-open");
    document.body.style.top = "";
    window.scrollTo({ top: filtersScrollY, behavior: "auto" });
    const changed = pendingView && pendingView !== state.view;
    if (changed) applyView(pendingView, filtersScrollY);
    else {
      state.pendingView = null;
      syncViewButtons(state.view);
    }
    state.filtersScrollY = null;
    if (document.activeElement === elements.filtersClose) elements.filtersToggle.focus();
  }
}

function updateResponsiveFilters() {
  const mobile = isMobileLayout();
  elements.filtersToggle.hidden = !mobile;
  elements.filtersClose.hidden = !mobile;
  if (mobile) {
    elements.filters.setAttribute("role", "dialog");
    elements.filters.setAttribute("aria-modal", "true");
    setFiltersExpanded(false);
  } else {
    elements.filters.removeAttribute("role");
    elements.filters.removeAttribute("aria-modal");
    setFiltersExpanded(true);
    if (state.feed && state.pendingView && state.pendingView !== state.view) {
      applyView(state.pendingView);
    } else {
      state.pendingView = null;
      syncViewButtons(state.view);
    }
  }
}

async function fetchJSON(url, label) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${label} returned ${response.status}.`);
  return response.json();
}

async function configureParishSelector(registry, selected) {
  const parishes = await Promise.all(registry.parishes.map((parishId) => (
    fetchJSON(`${FEED_ROOT}/parishes/${parishId}/parish.json`, `${parishId} parish`)
  )));
  const options = [
    ...(registry.aggregate_view ? [{
      id: registry.aggregate_view.id,
      name: registry.aggregate_view.name,
      branding: { logo: "assets/gold-coast-mascot.png" },
    }] : []),
    ...parishes,
  ];
  elements.parishSelectorToggle.hidden = options.length < 2;
  elements.parishSelector.replaceChildren(...options.map((parish) => {
    const button = document.createElement("button");
    const label = document.createElement("span");
    button.type = "button";
    button.className = "parish-selector-option";
    button.role = "menuitemradio";
    button.setAttribute("aria-checked", String(parish.id === selected));
    label.textContent = parish.name;
    button.append(label);
    button.addEventListener("click", () => {
      const url = new URL(window.location.href);
      url.searchParams.set("parish", parish.id);
      window.localStorage.setItem("gc-pilgrim-parish", parish.id);
      window.location.assign(url);
    });
    return button;
  }));
  return parishes;
}

async function loadParishCalendar(parishId, liturgical) {
  const parishRoot = `${FEED_ROOT}/parishes/${parishId}`;
  const [parish, services, community] = await Promise.all([
    fetchJSON(`${parishRoot}/parish.json`, `${parishId} parish feed`),
    fetchJSON(`${parishRoot}/services.json`, `${parishId} services feed`),
    fetchJSON(`${parishRoot}/community.json`, `${parishId} community feed`),
  ]);
  return {
    parish,
    services,
    community,
    calendar: assembleCalendar(parish, services, community, liturgical),
  };
}

async function loadApplication() {
  try {
    const registry = validateRegistry(await fetchJSON(`${FEED_ROOT}/registry.json`, "Registry"));
    const parishId = selectedParishId(registry, window.location.search);
    window.localStorage.setItem("gc-pilgrim-parish", parishId);
    const parishes = await configureParishSelector(registry, parishId);
    const liturgical = await fetchJSON(`${FEED_ROOT}/liturgical.json`, "Liturgical feed");
    const isAggregate = parishId === registry.aggregate_view?.id;
    let feed;
    if (isAggregate) {
      const calendars = await Promise.all(
        registry.parishes.map((id) => loadParishCalendar(id, liturgical)),
      );
      feed = aggregateCalendars(calendars);
      renderAggregateAbout(registry.aggregate_view, parishes);
    } else {
      const bundle = await loadParishCalendar(parishId, liturgical);
      feed = bundle.calendar;
      renderParish(bundle.parish);
    }
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
    renderEvents();
    goToToday();
  } catch (error) {
    elements.resultsCount.textContent = "Calendar unavailable";
    elements.errorMessage.hidden = false;
    elements.errorMessage.textContent =
      `${error.message} Serve the built site with a local web server so it can read ${FEED_ROOT}.`;
    elements.aboutError.hidden = false;
    elements.aboutError.textContent = `${error.message} Parish information is temporarily unavailable.`;
  }
}

document.querySelectorAll(".filter-toggle").forEach((toggle) => {
  toggle.addEventListener("click", () => {
    const content = document.querySelector(`#${toggle.getAttribute("aria-controls")}`);
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    content.hidden = expanded;
  });
});
elements.showAllButtons.forEach((button) => {
  button.addEventListener("click", () => {
    showAllEvents();
  });
});
elements.filtersToggle.addEventListener("click", () => {
  setFiltersExpanded(elements.filtersToggle.getAttribute("aria-expanded") !== "true");
});
elements.filtersClose.addEventListener("click", () => setFiltersExpanded(false));
elements.filtersBackdrop.addEventListener("click", () => setFiltersExpanded(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && elements.parishSelectorToggle.getAttribute("aria-expanded") === "true") {
    closeParishSelector();
    elements.parishSelectorToggle.focus();
    return;
  }
  if (event.key === "Escape" && elements.navigationToggle.getAttribute("aria-expanded") === "true") {
    closeNavigation();
    elements.navigationToggle.focus();
    return;
  }
  if (event.key === "Escape" && elements.filtersToggle.getAttribute("aria-expanded") === "true") {
    setFiltersExpanded(false);
  }
});
elements.parishSelectorToggle.addEventListener("click", () => {
  const expanded = elements.parishSelectorToggle.getAttribute("aria-expanded") === "true";
  elements.parishSelectorToggle.setAttribute("aria-expanded", String(!expanded));
  elements.parishSelector.hidden = expanded;
  if (!expanded) {
    elements.parishSelector.querySelector('[aria-checked="true"]')?.focus();
  }
});
document.addEventListener("click", (event) => {
  if (!elements.parishSelectorToggle.closest(".brand-lockup").contains(event.target)) {
    closeParishSelector();
  }
});
elements.navigationToggle.addEventListener("click", () => {
  const expanded = elements.navigationToggle.getAttribute("aria-expanded") === "true";
  elements.navigationToggle.setAttribute("aria-expanded", String(!expanded));
  elements.navigationToggle.setAttribute("aria-label", expanded ? "Open navigation" : "Close navigation");
  elements.siteNavigation.classList.toggle("navigation-open", !expanded);
});
elements.navigationLinks.forEach((link) => {
  link.addEventListener("click", () => showPage(link.dataset.page));
});
elements.themeChoices.forEach((input) => {
  input.addEventListener("change", () => {
    state.preferences.theme = input.value;
    savePreferences(window.localStorage, state.preferences);
    applyThemePreferences();
  });
});
elements.liturgicalDetailChoices.forEach((input) => {
  input.addEventListener("change", () => {
    state.preferences.liturgicalDetail = input.value;
    savePreferences(window.localStorage, state.preferences);
    if (state.feed) renderEvents();
  });
});
window.addEventListener("hashchange", () => showPage(currentPageFromHash()));
elements.resultsToday.addEventListener("click", () => {
  goToToday();
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
elements.previousPeriods.forEach((button) => {
  button.addEventListener("click", () => navigatePeriod("previous", isMobileLayout()));
});
elements.nextPeriods.forEach((button) => {
  button.addEventListener("click", () => navigatePeriod("next", isMobileLayout()));
});

applyThemePreferences();
updateResponsiveFilters();
showPage(currentPageFromHash());
updateStickyOffset();
window.addEventListener("resize", updateStickyOffset);
mobileLayout.addEventListener("change", updateResponsiveFilters);
window.setInterval(updatePastStates, 30_000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) updatePastStates();
});
loadApplication();
