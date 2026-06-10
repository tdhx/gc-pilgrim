import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  matchesEvent,
  orderedEventTypes,
  presiderGroups,
  validateFeed,
} from "../web/calendar-core.js";

const feed = JSON.parse(await readFile(new URL("../feeds/v1/calendar.json", import.meta.url)));

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
