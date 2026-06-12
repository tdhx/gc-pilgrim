import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  addDays,
  addMonths,
  aggregateCalendars,
  assembleCalendar,
  eventsInRange,
  liturgicalColour,
  matchesEvent,
  monthGrid,
  orderedChurches,
  orderedEventTypes,
  presiderGroups,
  selectedParishId,
  startOfSundayWeek,
  validateCommunity,
  validateLiturgical,
  validateParish,
  validateRegistry,
  validateServices,
} from "../app/web/calendar-core.js";

const json = async (path) => JSON.parse(await readFile(new URL(path, import.meta.url)));
const registry = await json("../feeds/v1/registry.json");
const parish = await json("../feeds/v1/parishes/surfers-paradise/parish.json");
const services = await json("../feeds/v1/parishes/surfers-paradise/services.json");
const community = await json("../feeds/v1/parishes/surfers-paradise/community.json");
const southportParish = await json("../feeds/v1/parishes/southport/parish.json");
const southportServices = await json("../feeds/v1/parishes/southport/services.json");
const southportCommunity = await json("../feeds/v1/parishes/southport/community.json");
const burleighParish = await json("../feeds/v1/parishes/burleigh-heads/parish.json");
const burleighServices = await json("../feeds/v1/parishes/burleigh-heads/services.json");
const burleighCommunity = await json("../feeds/v1/parishes/burleigh-heads/community.json");
const nerangParish = await json("../feeds/v1/parishes/nerang/parish.json");
const nerangServices = await json("../feeds/v1/parishes/nerang/services.json");
const nerangCommunity = await json("../feeds/v1/parishes/nerang/community.json");
const runawayBayParish = await json("../feeds/v1/parishes/runaway-bay/parish.json");
const runawayBayServices = await json("../feeds/v1/parishes/runaway-bay/services.json");
const runawayBayCommunity = await json("../feeds/v1/parishes/runaway-bay/community.json");
const liturgical = await json("../feeds/v1/liturgical.json");
const appSource = await readFile(new URL("../app/app.js", import.meta.url), "utf8");
const indexSource = await readFile(new URL("../app/index.html", import.meta.url), "utf8");
const diagnosticsSource = await readFile(new URL("../app/diagnostics.js", import.meta.url), "utf8");
const stylesSource = await readFile(new URL("../app/styles.css", import.meta.url), "utf8");

test("published modular feeds validate", () => {
  assert.equal(validateRegistry(registry), registry);
  assert.equal(validateParish(parish), parish);
  assert.equal(validateServices(services), services);
  assert.equal(validateCommunity(community), community);
  assert.equal(validateLiturgical(liturgical), liturgical);
  assert.equal(validateParish(southportParish), southportParish);
  assert.equal(validateServices(southportServices), southportServices);
  assert.equal(validateCommunity(southportCommunity), southportCommunity);
  assert.equal(validateParish(burleighParish), burleighParish);
  assert.equal(validateServices(burleighServices), burleighServices);
  assert.equal(validateCommunity(burleighCommunity), burleighCommunity);
  assert.equal(validateParish(nerangParish), nerangParish);
  assert.equal(validateServices(nerangServices), nerangServices);
  assert.equal(validateCommunity(nerangCommunity), nerangCommunity);
  assert.equal(validateParish(runawayBayParish), runawayBayParish);
  assert.equal(validateServices(runawayBayServices), runawayBayServices);
  assert.equal(validateCommunity(runawayBayCommunity), runawayBayCommunity);
});

test("registry selects query parish and falls back to default", () => {
  assert.equal(selectedParishId(registry), "gold-coast");
  assert.equal(selectedParishId(registry, "?parish=gold-coast"), "gold-coast");
  assert.equal(selectedParishId(registry, "?parish=surfers-paradise"), "surfers-paradise");
  assert.equal(selectedParishId(registry, "?parish=southport"), "southport");
  assert.equal(selectedParishId(registry, "?parish=burleigh-heads"), "burleigh-heads");
  assert.equal(selectedParishId(registry, "?parish=nerang"), "nerang");
  assert.equal(selectedParishId(registry, "?parish=runaway-bay"), "runaway-bay");
  assert.equal(selectedParishId(registry, "?parish=missing"), registry.default_view_id);
});

test("a saved valid parish remains selected for returning visitors", () => {
  globalThis.window = {
    localStorage: {
      getItem: () => "southport",
    },
  };
  try {
    assert.equal(selectedParishId(registry), "southport");
    assert.equal(selectedParishId(registry, "?parish=gold-coast"), "gold-coast");
  } finally {
    delete globalThis.window;
  }
});

test("Gold Coast aggregate combines parish calendars with attribution", () => {
  const surfersCalendar = assembleCalendar(parish, services, community, liturgical);
  const southportCalendar = assembleCalendar(
    southportParish,
    southportServices,
    southportCommunity,
    liturgical,
  );
  const calendar = aggregateCalendars([
    { parish, calendar: surfersCalendar },
    { parish: southportParish, calendar: southportCalendar },
    {
      parish: burleighParish,
      calendar: assembleCalendar(
        burleighParish,
        burleighServices,
        burleighCommunity,
        liturgical,
      ),
    },
    {
      parish: nerangParish,
      calendar: assembleCalendar(
        nerangParish,
        nerangServices,
        nerangCommunity,
        liturgical,
      ),
    },
    {
      parish: runawayBayParish,
      calendar: assembleCalendar(
        runawayBayParish,
        runawayBayServices,
        runawayBayCommunity,
        liturgical,
      ),
    },
  ]);
  const burleighCalendar = assembleCalendar(
    burleighParish,
    burleighServices,
    burleighCommunity,
    liturgical,
  );
  const nerangCalendar = assembleCalendar(
    nerangParish,
    nerangServices,
    nerangCommunity,
    liturgical,
  );
  const runawayBayCalendar = assembleCalendar(
    runawayBayParish,
    runawayBayServices,
    runawayBayCommunity,
    liturgical,
  );
  assert.equal(
    calendar.events.length,
    surfersCalendar.events.length
      + southportCalendar.events.length
      + burleighCalendar.events.length
      + nerangCalendar.events.length
      + runawayBayCalendar.events.length,
  );
  assert.deepEqual(
    new Set(calendar.events.map((event) => event.parish_id)),
    new Set(["surfers-paradise", "southport", "burleigh-heads", "nerang", "runaway-bay"]),
  );
  assert.ok(calendar.events.every((event) => event.id.startsWith(`${event.parish_id}:`)));
  assert.equal(calendar.sources.length, 8);
  assert.deepEqual(
    calendar.events,
    [...calendar.events].sort((left, right) => left.start.localeCompare(right.start)
      || left.end.localeCompare(right.end)
      || left.id.localeCompare(right.id)),
  );
  const selected = {
    eventType: new Set(),
    multiculturalSubtype: new Set(),
    church: new Set(),
    presider: new Set(),
  };
  assert.ok(calendar.events.filter((event) => (
    matchesEvent(event, selected, "southport")
  )).every((event) => event.parish_id === "southport"));
});

test("Southport services assemble with locations and liturgical enrichment", () => {
  const calendar = assembleCalendar(
    southportParish,
    southportServices,
    southportCommunity,
    liturgical,
  );
  assert.ok(calendar.events.length > 0);
  assert.ok(calendar.events.some((event) => event.church === "Guardian Angels"));
  assert.ok(
    calendar.events.some((event) => event.event_type === "mass" && event.liturgical?.observance),
  );
  assert.ok(calendar.events.every((event) => event.presiders.length === 0));
});

test("Burleigh services assemble with one first-Friday Healing Mass", () => {
  const calendar = assembleCalendar(
    burleighParish,
    burleighServices,
    burleighCommunity,
    liturgical,
  );
  assert.ok(calendar.events.length > 0);
  assert.ok(calendar.events.some((event) => event.church === "Mary Mother of Mercy"));
  const healingMasses = calendar.events.filter((event) => event.service_name === "Healing Mass");
  assert.ok(healingMasses.length > 0);
  assert.ok(healingMasses.every((event) => event.event_type === "mass"));
  assert.ok(healingMasses.every((event) => event.church === "Mary Mother of Mercy"));
  assert.ok(healingMasses.every((event) => new Date(event.start).getDay() === 5));
  assert.equal(burleighCommunity.events.length, 0);
});

test("Nerang services preserve Eastern rite and devotion metadata", () => {
  const calendar = assembleCalendar(
    nerangParish,
    nerangServices,
    nerangCommunity,
    liturgical,
  );
  const syroMalabar = calendar.events.filter((event) => event.event_subtype === "syro-malabar");
  assert.ok(syroMalabar.length > 0);
  assert.ok(syroMalabar.every((event) => event.service_name === "Syro-Malabar Mass"));
  assert.ok(syroMalabar.every((event) => event.liturgical === null));
  const firstFridays = syroMalabar.filter((event) => (
    new Date(event.start).getDay() === 5 && Number(event.start.slice(8, 10)) <= 7
  ));
  assert.ok(firstFridays.length > 0);
  assert.ok(firstFridays.every((event) => event.associated_devotions.includes("Adoration")));
  assert.ok(calendar.events.some((event) => event.church === "Earle Haven"));
  assert.equal(nerangCommunity.events.length, 0);
});

test("Runaway Bay services contain only the current six-Mass schedule", () => {
  const calendar = assembleCalendar(
    runawayBayParish,
    runawayBayServices,
    runawayBayCommunity,
    liturgical,
  );
  assert.ok(calendar.events.length > 0);
  assert.ok(calendar.events.every((event) => event.event_type === "mass"));
  assert.ok(calendar.events.every((event) => event.associated_devotions.length === 0));
  assert.deepEqual(
    new Set(calendar.events.map((event) => event.church)),
    new Set(["Holy Family", "Our Lady of Hope"]),
  );
  assert.ok(
    calendar.events
      .filter((event) => event.church === "Our Lady of Hope")
      .every((event) => event.service_name === "Vigil Mass"),
  );
  assert.equal(runawayBayServices.sources.length, 1);
  assert.equal(runawayBayCommunity.events.length, 0);
});

test("runtime enrichment joins church and liturgical metadata immutably", () => {
  const original = JSON.stringify(services.services[0]);
  const calendar = assembleCalendar(parish, services, community, liturgical);
  const event = calendar.events[0];
  assert.equal(event.church, "Sacred Heart");
  assert.ok(event.liturgical?.observance);
  assert.equal(JSON.stringify(services.services[0]), original);
  assert.equal(Object.isFrozen(event), true);
});

test("baptisms remain in JSON but are excluded from displayed calendars", () => {
  assert.ok(services.services.some((event) => event.event_type === "baptism"));
  const calendar = assembleCalendar(parish, services, community, liturgical);
  assert.equal(calendar.events.some((event) => event.event_type === "baptism"), false);
  const aggregate = aggregateCalendars([{ parish, calendar }]);
  assert.equal(aggregate.events.some((event) => event.event_type === "baptism"), false);
});

test("cancelled records are hidden and modified records remain", () => {
  const changed = structuredClone(services);
  changed.services[0].status = "cancelled";
  changed.services[1].status = "modified";
  const calendar = assembleCalendar(parish, changed, community, liturgical);
  assert.equal(calendar.events.some((event) => event.id === changed.services[0].id), false);
  assert.equal(calendar.events.some((event) => event.id === changed.services[1].id), true);
});

test("community records share the calendar display model", () => {
  const changed = structuredClone(community);
  changed.events.push({
    id: "community-1",
    title: "Morning Tea",
    start: "2026-06-14T10:00:00+10:00",
    end: "2026-06-14T11:00:00+10:00",
    status: "active",
  });
  const calendar = assembleCalendar(parish, services, changed, liturgical);
  const event = calendar.events.find((candidate) => candidate.id === "community-1");
  assert.equal(event.event_type, "community");
  assert.equal(event.service_name, "Morning Tea");
});

test("sparse parish metadata is accepted", () => {
  assert.equal(validateParish({
    schema_version: 1,
    id: "sparse",
    name: "Sparse Parish",
    churches: [],
  }).id, "sparse");
});

test("parish location metadata is validated", () => {
  assert.throws(
    () => validateParish({
      schema_version: 1,
      id: "broken",
      name: "Broken Parish",
      churches: [{ id: "broken", name: "Broken", status: "closed" }],
    }),
    /invalid status/,
  );
});

test("existing calendar filtering behaviour remains", () => {
  const calendar = assembleCalendar(parish, services, community, liturgical);
  const selected = {
    eventType: new Set(),
    multiculturalSubtype: new Set(),
    church: new Set(),
    presider: new Set(),
  };
  const results = calendar.events.filter((event) => (
    matchesEvent(event, selected, "", ["mass", "confession"])
  ));
  assert.ok(results.length > 0);
  assert.ok(results.every((event) => ["mass", "confession"].includes(event.event_type)));
});

test("liturgical colours use the modular colour field", () => {
  assert.equal(liturgicalColour({ liturgical: { colour: "RED" } }), "red");
  assert.equal(liturgicalColour({ liturgical: null }), "parish");
});

test("GC Pilgrim app uses registry discovery and four-feed loading", () => {
  assert.match(indexSource, /<title>GC Pilgrim<\/title>/);
  assert.match(indexSource, /id="parish-selector"/);
  assert.match(indexSource, /id="parish-selector-toggle"/);
  assert.match(indexSource, /id="selected-region-name"/);
  assert.match(indexSource, /class="pilgrim-icon"/);
  assert.match(indexSource, /class="pilgrim-icon"[\s\S]*?<div class="brand-lockup">/);
  assert.doesNotMatch(indexSource, /<(?:a|button)[^>]*class="pilgrim-icon"/);
  assert.match(indexSource, /id="about-logo"/);
  assert.doesNotMatch(indexSource, /id="diagnostics-link"/);
  assert.doesNotMatch(indexSource, /platform-brand|gc-pilgrim\.svg/);
  assert.match(appSource, /feeds\/v1/);
  assert.match(appSource, /Promise\.all\(\[/);
  assert.match(appSource, /services\.json/);
  assert.match(appSource, /community\.json/);
  assert.match(appSource, /liturgical\.json/);
  assert.doesNotMatch(appSource, /calendar\.json/);
  assert.match(diagnosticsSource, /validateRegistry/);
  assert.match(appSource, /gc-pilgrim-parish/);
  assert.match(appSource, /aggregateCalendars/);
  assert.match(appSource, /renderAggregateAbout/);
  assert.match(appSource, /adoration: "gold"/);
  assert.match(appSource, /assets\/gold-coast-mascot\.png/);
  assert.match(appSource, /All Gold Coast/);
  assert.doesNotMatch(appSource, /const logo = document\.createElement\("img"\)/);
  assert.doesNotMatch(stylesSource, /\.parish-selector-option img/);
  assert.match(indexSource, /class="event-parish"/);
  assert.match(appSource, /event-mass-fallback/);
  assert.match(appSource, /presider\.hidden = !presider\.textContent/);
  assert.match(appSource, /minimumEvents = 10/);
  assert.match(appSource, /closest\("\.filter-section"\)\.hidden/);
  assert.match(stylesSource, /body\[data-theme="southport"\]/);
  assert.match(stylesSource, /body\[data-theme="burleigh-heads"\]/);
  assert.match(stylesSource, /body\[data-theme="nerang"\]/);
  assert.match(stylesSource, /body\[data-theme="runaway-bay"\]/);
  assert.match(appSource, /Churches and Mass locations/);
  assert.match(appSource, /Mass centre/);
  assert.match(appSource, /Temporarily closed/);
  assert.match(appSource, /Retirement community/);
  assert.match(stylesSource, /body\[data-theme="gc-pilgrim"\]/);
  assert.match(stylesSource, /--theme-bar-gradient/);
  assert.match(stylesSource, /\.event-mass-fallback::before/);
  assert.match(stylesSource, /data-liturgical-colour="gold"/);
});

test("Nerang branding uses the supplied full parish asset", async () => {
  assert.equal(nerangParish.branding.logo, "assets/nerang-logo.png");
  const logo = await readFile(new URL("../app/assets/nerang-logo.png", import.meta.url));
  assert.equal(logo.readUInt32BE(16), 361);
  assert.equal(logo.readUInt32BE(20), 89);
});

test("Runaway Bay branding uses the official parish logo", async () => {
  assert.equal(runawayBayParish.branding.logo, "assets/runaway-bay-logo.png");
  const logo = await readFile(new URL("../app/assets/runaway-bay-logo.png", import.meta.url));
  assert.equal(logo.readUInt32BE(16), 689);
  assert.equal(logo.readUInt32BE(20), 101);
});

test("calendar helpers preserve existing ordering and date behaviour", () => {
  assert.deepEqual(
    orderedEventTypes(["community", "multicultural", "baptism", "mass", "confession"]),
    ["mass", "confession", "baptism", "multicultural", "community"],
  );
  assert.equal(startOfSundayWeek("2026-06-10"), "2026-06-07");
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(addMonths("2026-12-15", 1), "2027-01-01");
  assert.equal(monthGrid("2024-02-14").length, 35);
  const events = [{ start: "2026-06-14T07:00:00+10:00" }];
  assert.deepEqual(eventsInRange(events, "2026-06-14", "2026-06-20"), events);
});

test("church ordering puts primary first then descending postcodes stably", () => {
  const churches = [
    { id: "same-first", address: "First QLD 4215" },
    { id: "missing", address: "No postcode" },
    { id: "high", address: "High QLD 4221" },
    { id: "primary", address: "Primary QLD 4211", is_primary_site: true },
    { id: "same-second", address: "Second QLD 4215" },
  ];
  assert.deepEqual(
    orderedChurches(churches).map((church) => church.id),
    ["primary", "high", "same-first", "same-second", "missing"],
  );
  assert.deepEqual(churches.map((church) => church.id), [
    "same-first",
    "missing",
    "high",
    "primary",
    "same-second",
  ]);
});

test("presider grouping remains stable", () => {
  assert.deepEqual(
    presiderGroups(["Fr Luis", "Fr Warren", "Fr Bradley", "Fr Paul"]),
    [["Fr Paul", "Fr Bradley"], ["Fr Warren"], ["Fr Luis"]],
  );
});
