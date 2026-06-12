export const SUPPORTED_SCHEMA_VERSION = 1;
export const EVENT_TYPE_ORDER = ["mass", "confession", "baptism", "multicultural", "community"];
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

export function orderedChurches(churches) {
  const postcode = (church) => {
    const match = church.address?.match(/\b(\d{4})\s*$/);
    return match ? Number(match[1]) : null;
  };
  return churches
    .map((church, index) => ({ church, index, postcode: postcode(church) }))
    .sort((left, right) => {
      const primaryOrder = Number(Boolean(right.church.is_primary_site))
        - Number(Boolean(left.church.is_primary_site));
      if (primaryOrder) return primaryOrder;
      if (left.postcode === null && right.postcode !== null) return 1;
      if (left.postcode !== null && right.postcode === null) return -1;
      if (left.postcode !== right.postcode) return right.postcode - left.postcode;
      return left.index - right.index;
    })
    .map(({ church }) => church);
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
  const colour = event?.liturgical?.colour?.toLocaleLowerCase();
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

function requireSchema(feed, label) {
  if (!feed || feed.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    throw new Error(`Unsupported ${label} schema ${feed?.schema_version ?? "(missing)"}.`);
  }
}

function validateRecords(records, required, label) {
  if (!Array.isArray(records)) throw new Error(`${label} feed is missing records.`);
  const ids = new Set();
  records.forEach((record) => {
    const missing = required.filter((field) => record[field] === undefined || record[field] === "");
    if (missing.length) throw new Error(`${label} record is missing ${missing.join(", ")}.`);
    if (!["active", "cancelled", "modified"].includes(record.status)) {
      throw new Error(`${label} record ${record.id} has invalid status.`);
    }
    if (ids.has(record.id)) throw new Error(`${label} feed contains duplicate IDs.`);
    ids.add(record.id);
  });
}

export function validateRegistry(registry) {
  requireSchema(registry, "registry");
  if (!Array.isArray(registry.parishes) || !registry.parishes.length) {
    throw new Error("Registry contains no parishes.");
  }
  if (!registry.parishes.includes(registry.default_parish_id)) {
    throw new Error("Registry default parish is unavailable.");
  }
  if (registry.aggregate_view) {
    if (!registry.aggregate_view.id || !registry.aggregate_view.name) {
      throw new Error("Registry aggregate view is incomplete.");
    }
    if (registry.parishes.includes(registry.aggregate_view.id)) {
      throw new Error("Registry aggregate view conflicts with a parish.");
    }
  }
  const viewIds = registryViewIds(registry);
  if (registry.default_view_id && !viewIds.includes(registry.default_view_id)) {
    throw new Error("Registry default view is unavailable.");
  }
  return registry;
}

export function registryViewIds(registry) {
  return [
    ...(registry.aggregate_view ? [registry.aggregate_view.id] : []),
    ...registry.parishes,
  ];
}

export function selectedParishId(registry, search = "") {
  const requested = new URLSearchParams(search).get("parish");
  const remembered = typeof window !== "undefined"
    ? window.localStorage.getItem("gc-pilgrim-parish")
    : null;
  const viewIds = registryViewIds(registry);
  if (viewIds.includes(requested)) return requested;
  if (viewIds.includes(remembered)) return remembered;
  return registry.default_view_id || registry.default_parish_id;
}

export function validateParish(parish) {
  requireSchema(parish, "parish");
  if (!parish.id || !parish.name || !Array.isArray(parish.churches)) {
    throw new Error("Parish feed is missing required fields.");
  }
  parish.churches.forEach((church) => {
    if (church.status && church.status !== "temporarily-closed") {
      throw new Error(`Church ${church.id} has invalid status.`);
    }
    if (
      church.location_type
      && !["chaplaincy", "mass-centre", "retirement-community"].includes(church.location_type)
    ) {
      throw new Error(`Church ${church.id} has invalid location type.`);
    }
  });
  return parish;
}

export function validateServices(feed) {
  requireSchema(feed, "services");
  if (!feed.coverage || !feed.generated_at) throw new Error("Services feed is missing metadata.");
  validateRecords(feed.services, ["id", "event_type", "start", "end", "status"], "Service");
  return feed;
}

export function validateCommunity(feed) {
  requireSchema(feed, "community");
  if (!feed.coverage || !feed.generated_at) throw new Error("Community feed is missing metadata.");
  validateRecords(feed.events, ["id", "title", "start", "end", "status"], "Community");
  return feed;
}

export function validateLiturgical(feed) {
  requireSchema(feed, "liturgical");
  if (!feed.dates || typeof feed.dates !== "object") {
    throw new Error("Liturgical feed is missing dates.");
  }
  return feed;
}

function enrichedService(service, churches, liturgicalDates) {
  const church = churches.get(service.church_id);
  return Object.freeze({
    ...service,
    record_kind: "service",
    church: church?.calendar_name ?? church?.name ?? null,
    liturgical: service.liturgical_date
      ? liturgicalDates[service.liturgical_date] ?? null
      : null,
    title: service.title || service.service_name || service.event_type,
    service_name: service.service_name || service.title || titleCase(service.event_type),
    presiders: service.presiders || [],
    associated_devotions: service.associated_devotions || [],
    all_day: service.all_day || false,
  });
}

function enrichedCommunity(event) {
  return Object.freeze({
    ...event,
    record_kind: "community",
    event_type: "community",
    service_name: event.title,
    church: event.location || null,
    presiders: [],
    associated_devotions: [],
    all_day: event.all_day || false,
    liturgical_date: null,
    liturgical: null,
  });
}

function titleCase(value) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function uniqueMetadata(values) {
  const seen = new Set();
  return values.filter((value) => {
    const key = JSON.stringify(value);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function assembleCalendar(parish, servicesFeed, communityFeed, liturgicalFeed) {
  validateParish(parish);
  validateServices(servicesFeed);
  validateCommunity(communityFeed);
  validateLiturgical(liturgicalFeed);
  const churches = new Map(parish.churches.map((church) => [church.id, church]));
  const services = servicesFeed.services
    .filter((service) => service.status !== "cancelled" && service.event_type !== "baptism")
    .map((service) => enrichedService(service, churches, liturgicalFeed.dates));
  const community = communityFeed.events
    .filter((event) => event.status !== "cancelled")
    .map(enrichedCommunity);
  const events = [...services, ...community]
    .sort((left, right) => left.start.localeCompare(right.start)
      || left.end.localeCompare(right.end)
      || left.id.localeCompare(right.id));
  return Object.freeze({
    schema_version: 1,
    generated_at: servicesFeed.generated_at,
    timezone: servicesFeed.timezone,
    coverage: {
      start: [servicesFeed.coverage.start, communityFeed.coverage.start].sort()[0],
      end: [servicesFeed.coverage.end, communityFeed.coverage.end].sort().at(-1),
    },
    sources: uniqueMetadata([
      ...(servicesFeed.sources || []),
      ...(communityFeed.sources || []),
    ]),
    warnings: uniqueMetadata([
      ...(servicesFeed.warnings || []),
      ...(communityFeed.warnings || []),
    ]),
    events: Object.freeze(events),
  });
}

export function aggregateCalendars(parishCalendars) {
  if (!Array.isArray(parishCalendars) || !parishCalendars.length) {
    throw new Error("No parish calendars are available to aggregate.");
  }
  const events = parishCalendars.flatMap(({ parish, calendar }) => (
    calendar.events.map((event) => Object.freeze({
      ...event,
      id: `${parish.id}:${event.id}`,
      parish_id: parish.id,
      parish_name: parish.name,
    }))
  )).sort((left, right) => left.start.localeCompare(right.start)
    || left.end.localeCompare(right.end)
    || left.id.localeCompare(right.id));
  return Object.freeze({
    schema_version: 1,
    generated_at: parishCalendars
      .map(({ calendar }) => calendar.generated_at)
      .sort()
      .at(-1),
    timezone: parishCalendars[0].calendar.timezone,
    coverage: {
      start: parishCalendars
        .map(({ calendar }) => calendar.coverage.start)
        .sort()[0],
      end: parishCalendars
        .map(({ calendar }) => calendar.coverage.end)
        .sort()
        .at(-1),
    },
    sources: uniqueMetadata(
      parishCalendars.flatMap(({ calendar }) => calendar.sources || []),
    ),
    warnings: uniqueMetadata(
      parishCalendars.flatMap(({ calendar }) => calendar.warnings || []),
    ),
    events: Object.freeze(events),
  });
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
      event.parish_name,
      ...event.presiders,
    ].filter(Boolean).join(" ").toLocaleLowerCase();
    if (!haystack.includes(search)) return false;
  }
  return true;
}
