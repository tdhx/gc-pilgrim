import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  addDays,
  addMonths,
  eventsInRange,
  monthGrid,
  rangeWithinCoverage,
  startOfSundayWeek,
  liturgicalColour,
  matchesEvent,
  orderedEventTypes,
  presiderGroups,
  validateFeed,
} from "../web/calendar-core.js";

const feed = JSON.parse(await readFile(new URL("../feeds/v1/calendar.json", import.meta.url)));
const appSource = await readFile(new URL("../app.js", import.meta.url), "utf8");
const indexSource = await readFile(new URL("../index.html", import.meta.url), "utf8");

test("published feed validates", () => {
  assert.equal(validateFeed(feed), feed);
});

test("default filters match Masses and Reconciliation", () => {
  const selected = {
    eventType: new Set(),
    multiculturalSubtype: new Set(),
    church: new Set(),
    presider: new Set(),
  };
  const results = feed.events.filter((event) => (
    matchesEvent(event, selected, "", ["mass", "confession"])
  ));
  assert.ok(results.length > 0);
  assert.ok(results.every((event) => ["mass", "confession"].includes(event.event_type)));
});

test("explicit event selections override the default feed view", () => {
  const selected = {
    eventType: new Set(["baptism"]),
    multiculturalSubtype: new Set(),
    church: new Set(),
    presider: new Set(),
  };
  const results = feed.events.filter((event) => (
    matchesEvent(event, selected, "", ["mass", "confession"])
  ));
  assert.ok(results.length > 0);
  assert.ok(results.every((event) => event.event_type === "baptism"));
});

test("search includes joined liturgical fields", () => {
  const event = feed.events.find((candidate) => candidate.liturgical?.observance);
  assert.ok(event);
  const selected = {
    eventType: new Set(),
    multiculturalSubtype: new Set(),
    church: new Set(),
    presider: new Set(),
  };
  assert.equal(
    matchesEvent(event, selected, event.liturgical.observance.toLocaleLowerCase()),
    true,
  );
});

test("card accents use known liturgical colours with a parish fallback", () => {
  assert.equal(
    liturgicalColour({ liturgical: { liturgical_colour: "RED" } }),
    "red",
  );
  assert.equal(liturgicalColour({ liturgical: null }), "parish");
  assert.equal(
    liturgicalColour({ liturgical: { liturgical_colour: "gold" } }),
    "parish",
  );
});

test("published module URLs use matching cache-busting revisions", () => {
  assert.match(indexSource, /src="app\.js\?v=20"/);
  assert.match(appSource, /calendar-core\.js\?v=5/);
});

test("filter options use the requested display order", () => {
  assert.deepEqual(
    orderedEventTypes(["multicultural", "baptism", "mass", "confession"]),
    ["mass", "confession", "baptism", "multicultural"],
  );
  assert.deepEqual(
    presiderGroups([
      "Fr Luis",
      "Fr Warren",
      "Fr Bradley",
      "Fr Damian",
      "Fr Fadi",
      "Fr John",
      "Fr Paul",
    ]),
    [
      ["Fr Paul", "Fr Bradley"],
      ["Fr Damian", "Fr John", "Fr Warren"],
      ["Fr Fadi", "Fr Luis"],
    ],
  );
});

test("calendar helpers use Sunday week boundaries", () => {
  assert.equal(startOfSundayWeek("2026-06-10"), "2026-06-07");
  assert.equal(startOfSundayWeek("2026-06-14"), "2026-06-14");
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
});

test("month grids align to complete Sunday-first weeks", () => {
  const february = monthGrid("2024-02-14");
  assert.equal(february[0], "2024-01-28");
  assert.equal(february.at(-1), "2024-03-02");
  assert.equal(february.length, 35);

  const august = monthGrid("2026-08-20");
  assert.equal(august[0], "2026-07-26");
  assert.equal(august.at(-1), "2026-09-05");
  assert.equal(august.length, 42);
  assert.equal(addMonths("2026-12-15", 1), "2027-01-01");
});

test("events can be selected by inclusive date-key range", () => {
  const events = [
    { start: "2026-06-13T17:00:00+10:00" },
    { start: "2026-06-14T07:00:00+10:00" },
    { start: "2026-06-21" },
  ];
  assert.deepEqual(
    eventsInRange(events, "2026-06-14", "2026-06-20"),
    [events[1]],
  );
});

test("navigation requires complete ranges inside feed coverage", () => {
  const coverage = { start: "2026-06-10", end: "2026-09-09" };
  assert.equal(rangeWithinCoverage("2026-06-14", "2026-06-20", coverage), true);
  assert.equal(rangeWithinCoverage("2026-06-07", "2026-06-13", coverage), false);
  assert.equal(rangeWithinCoverage("2026-09-06", "2026-09-12", coverage), false);
});
