import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  addDays,
  addMonths,
  assembleCalendar,
  eventsInRange,
  liturgicalColour,
  matchesEvent,
  monthGrid,
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
const liturgical = await json("../feeds/v1/liturgical.json");
const appSource = await readFile(new URL("../app/app.js", import.meta.url), "utf8");
const indexSource = await readFile(new URL("../app/index.html", import.meta.url), "utf8");
const diagnosticsSource = await readFile(new URL("../app/diagnostics.js", import.meta.url), "utf8");

test("published modular feeds validate", () => {
  assert.equal(validateRegistry(registry), registry);
  assert.equal(validateParish(parish), parish);
  assert.equal(validateServices(services), services);
  assert.equal(validateCommunity(community), community);
  assert.equal(validateLiturgical(liturgical), liturgical);
});

test("registry selects query parish and falls back to default", () => {
  assert.equal(selectedParishId(registry, "?parish=surfers-paradise"), "surfers-paradise");
  assert.equal(selectedParishId(registry, "?parish=missing"), registry.default_parish_id);
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
  assert.match(appSource, /feeds\/v1/);
  assert.match(appSource, /Promise\.all\(\[/);
  assert.match(appSource, /services\.json/);
  assert.match(appSource, /community\.json/);
  assert.match(appSource, /liturgical\.json/);
  assert.doesNotMatch(appSource, /calendar\.json/);
  assert.match(diagnosticsSource, /validateRegistry/);
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

test("presider grouping remains stable", () => {
  assert.deepEqual(
    presiderGroups(["Fr Luis", "Fr Warren", "Fr Bradley", "Fr Paul"]),
    [["Fr Paul", "Fr Bradley"], ["Fr Warren"], ["Fr Luis"]],
  );
});
