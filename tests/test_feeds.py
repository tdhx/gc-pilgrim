import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generators.compat_split import split
from generators.io import read_json
from sources.google_calendar import adapter as google_calendar
from sources.website import liturgical as universalis
from validators.feeds import (
    validate_community,
    validate_liturgical,
    validate_parish,
    validate_registry,
    validate_services,
)


BRISBANE = ZoneInfo("Australia/Brisbane")


class SourceAdapterTests(unittest.TestCase):
    def test_default_window_starts_at_current_month(self):
        fixed = datetime(2026, 6, 11, 12, 30, tzinfo=BRISBANE)
        with patch.object(google_calendar, "datetime") as mocked:
            mocked.now.return_value = fixed
            mocked.combine.side_effect = datetime.combine
            start, end = google_calendar.default_window()
        self.assertEqual(start.isoformat(), "2026-06-01T00:00:00+10:00")
        self.assertEqual(end.isoformat(), "2026-09-11T00:00:00+10:00")

    def test_recurrence_exclusions_and_overrides(self):
        source = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:weekly
DTSTART;TZID=Australia/Brisbane:20260101T090000
DTEND;TZID=Australia/Brisbane:20260101T100000
RRULE:FREQ=WEEKLY
EXDATE;TZID=Australia/Brisbane:20260108T090000
SUMMARY:Sacred Heart Mass - Fr Paul
END:VEVENT
BEGIN:VEVENT
UID:weekly
RECURRENCE-ID;TZID=Australia/Brisbane:20260115T090000
DTSTART;TZID=Australia/Brisbane:20260115T110000
DTEND;TZID=Australia/Brisbane:20260115T120000
SUMMARY:Sacred Heart Mass - Fr Bradley
END:VEVENT
END:VCALENDAR
"""
        records = google_calendar.build_records(
            source,
            datetime(2026, 1, 1, tzinfo=BRISBANE),
            datetime(2026, 1, 23, tzinfo=BRISBANE),
        )
        self.assertEqual(len(records), 3)
        self.assertEqual(records[1]["start"], "2026-01-15T11:00:00+10:00")
        self.assertEqual(records[1]["presiders"], ["Fr Bradley"])

    def test_future_universalis_pages_work_without_day_links(self):
        html = """<table id="yearly-calendar">
        <tr><th colspan="2">January</th></tr>
        <tr><td>Sat 1</td><td>Mary, the Holy Mother of God <span class="lit-w"></span></td></tr>
        </table>"""
        parser = universalis.UniversalisCalendarParser(2028)
        parser.feed(html)
        self.assertEqual(parser.rows[0]["date"].isoformat(), "2028-01-01")


class FeedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = read_json(ROOT / "feeds/v1/registry.json")
        cls.parish = read_json(
            ROOT / "feeds/v1/parishes/surfers-paradise/parish.json"
        )
        cls.services = read_json(
            ROOT / "feeds/v1/parishes/surfers-paradise/services.json"
        )
        cls.community = read_json(
            ROOT / "feeds/v1/parishes/surfers-paradise/community.json"
        )
        cls.liturgical = read_json(ROOT / "feeds/v1/liturgical.json")

    def test_published_feeds_validate(self):
        validate_registry(self.registry)
        validate_parish(self.parish)
        validate_services(self.services, self.parish)
        validate_community(self.community)
        validate_liturgical(self.liturgical)

    def test_sparse_parish_omits_all_optional_metadata(self):
        sparse = read_json(ROOT / "tests/fixtures/sparse-parish/parish.json")
        self.assertEqual(validate_parish(sparse), sparse)

    def test_liturgical_archives_cover_2026_to_2028(self):
        expected = {2026: 365, 2027: 365, 2028: 366}
        for year, count in expected.items():
            feed = read_json(ROOT / f"feeds/v1/liturgical/{year}.json")
            validate_liturgical(feed, year)
            self.assertEqual(len(feed["dates"]), count)
        self.assertEqual(len(self.liturgical["dates"]), sum(expected.values()))

    def test_status_values_are_enforced(self):
        broken = json.loads(json.dumps(self.services))
        broken["services"][0]["status"] = "unknown"
        with self.assertRaisesRegex(ValueError, "invalid status"):
            validate_services(broken, self.parish)

    def test_unknown_church_references_are_rejected(self):
        broken = json.loads(json.dumps(self.services))
        broken["services"][0]["church_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown churches"):
            validate_services(broken, self.parish)


class MigrationEquivalenceTests(unittest.TestCase):
    def test_direct_services_preserve_all_legacy_records(self):
        legacy = read_json(ROOT / "tests/fixtures/legacy-calendar.json")
        parish = read_json(ROOT / "feeds/v1/parishes/surfers-paradise/parish.json")
        services = read_json(
            ROOT / "feeds/v1/parishes/surfers-paradise/services.json"
        )
        community = read_json(
            ROOT / "feeds/v1/parishes/surfers-paradise/community.json"
        )
        self.assertEqual(len(legacy["events"]), 260)
        self.assertEqual(len(services["services"]), 260)
        self.assertEqual(community["events"], [])

        current = {record["id"]: record for record in services["services"]}
        fields = (
            "source_id",
            "title",
            "event_type",
            "event_subtype",
            "service_name",
            "presiders",
            "associated_devotions",
            "start",
            "end",
            "all_day",
            "timezone",
            "location",
            "description",
            "liturgical_date",
        )
        for old in legacy["events"]:
            new = current[old["id"]]
            for field in fields:
                self.assertEqual(old.get(field), new.get(field), (old["id"], field))
            self.assertEqual(new["status"], "active")
            self.assertNotIn("liturgical", new)

        compat_services, compat_community = split(legacy, parish)
        self.assertEqual(
            [record["id"] for record in compat_services["services"]],
            [record["id"] for record in services["services"]],
        )
        self.assertEqual(compat_community["events"], [])


if __name__ == "__main__":
    unittest.main()
