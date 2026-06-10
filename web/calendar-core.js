export const SUPPORTED_SCHEMA_VERSION = 1;
export const EVENT_TYPE_ORDER = ["mass", "confession", "baptism", "multicultural"];
export const LITURGICAL_COLOURS = new Set(["green", "red", "white", "violet", "rose"]);
const DATE_KEY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

const FEATURED_PRESIDERS = ["Fr Paul", "Fr Bradley"];
const PARISH_PRESIDERS = ["Fr Bernie", "Fr Damian", "Fr John", "Fr Warren"];

export function orderedEventTypes(values) {
  return [...values].sort((left, right) => {
    const leftIndex = EVENT_TYPE_ORDER.indexOf(left);
    const rightIndex = EVENT_TYPE_ORDER.indexOf(right);
    return (leftIndex < 0 ? EVENT_TYPE_ORDER.length : leftIndex)
      - (rightIndex < 0 ? EVENT_TYPE_ORDER.length : rightIndex)
      || left.localeCompare(right);
  });
}

export function presiderGroups(values) {
  const available = new Set(values);
  const take = (names) => names.filter((name) => available.delete(name));
  return [
    take(FEATURED_PRESIDERS),
    take(PARISH_PRESIDERS).sort((left, right) => left.localeCompare(right)),
    [...available].sort((left, right) => left.localeCompare(right)),
  ].filter((group) => group.length);
}

export function liturgicalColour(event) {
  const colour = event?.liturgical?.liturgical_colour?.toLocaleLowerCase();
  return LITURGICAL_COLOURS.has(colour) ? colour : "parish";
}

export function eventDateKey(event) {
  return event.start.slice(0, 10);
}

export function dateFromKey(dateKey) {
  if (!DATE_KEY_PATTERN.test(dateKey)) {
    throw new Error(`Invalid calendar date ${dateKey}.`);
  }
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

export function dateKey(date) {
  return [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, "0"),
    String(date.getUTCDate()).padStart(2, "0"),
  ].join("-");
}

export function addDays(dateKeyValue, amount) {
  const date = dateFromKey(dateKeyValue);
  date.setUTCDate(date.getUTCDate() + amount);
  return dateKey(date);
}

export function startOfSundayWeek(dateKeyValue) {
  const date = dateFromKey(dateKeyValue);
  return addDays(dateKeyValue, -date.getUTCDay());
}

export function monthStart(dateKeyValue) {
  return `${dateKeyValue.slice(0, 7)}-01`;
}

export function addMonths(dateKeyValue, amount) {
  const date = dateFromKey(monthStart(dateKeyValue));
  date.setUTCMonth(date.getUTCMonth() + amount);
  return dateKey(date);
}

export function monthGrid(dateKeyValue) {
  const first = monthStart(dateKeyValue);
  const firstDate = dateFromKey(first);
  const lastDate = new Date(Date.UTC(
    firstDate.getUTCFullYear(),
    firstDate.getUTCMonth() + 1,
    0,
  ));
  const gridStart = addDays(first, -firstDate.getUTCDay());
  const gridEnd = addDays(dateKey(lastDate), 6 - lastDate.getUTCDay());
  const dates = [];
  for (let current = gridStart; current <= gridEnd; current = addDays(current, 1)) {
    dates.push(current);
  }
  return dates;
}

export function eventsInRange(events, start, end) {
  return events.filter((event) => {
    const key = eventDateKey(event);
    return key >= start && key <= end;
  });
}

export function rangeWithinCoverage(start, end, coverage) {
  return start >= coverage.start && end <= coverage.end;
}

export function validateFeed(feed) {
  if (!feed || feed.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    throw new Error(`Unsupported calendar schema ${feed?.schema_version ?? "(missing)"}.`);
  }
  if (!Array.isArray(feed.events) || !feed.coverage || !feed.generated_at) {
    throw new Error("Calendar feed is missing required fields.");
  }
  const ids = new Set(feed.events.map((event) => event.id));
  if (ids.size !== feed.events.length) {
    throw new Error("Calendar feed contains duplicate event IDs.");
  }
  return feed;
}

export function matchesEvent(event, selected, search, defaultEventTypes = []) {
  const { eventType, church, presider, multiculturalSubtype } = selected;
  const effectiveEventTypes = eventType.size ? eventType : new Set(defaultEventTypes);
  if (effectiveEventTypes.size && !effectiveEventTypes.has(event.event_type)) return false;
  if (
    event.event_type === "multicultural"
    && effectiveEventTypes.has("multicultural")
    && multiculturalSubtype.size
    && !multiculturalSubtype.has(event.event_subtype)
  ) return false;
  const displayChurch = event.church || "Unassigned";
  if (church.size && !church.has(displayChurch)) return false;
  if (presider.size && !event.presiders.some((name) => presider.has(name))) return false;

  if (search) {
    const haystack = [
      event.title,
      event.location,
      event.description,
      displayChurch,
      event.service_name,
      event.liturgical?.observance,
      event.liturgical?.rank,
      event.liturgical?.season,
      ...event.presiders,
    ].filter(Boolean).join(" ").toLocaleLowerCase();
    if (!haystack.includes(search)) return false;
  }
  return true;
}
