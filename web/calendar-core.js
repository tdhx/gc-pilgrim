export const SUPPORTED_SCHEMA_VERSION = 1;
export const EVENT_TYPE_ORDER = ["mass", "confession", "baptism", "multicultural"];

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
