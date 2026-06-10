import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import calendar_feed
import refresh_calendar


BRISBANE = ZoneInfo("Australia/Brisbane")


class CalendarGenerationTests(unittest.TestCase):
    def test_recurrence_exclusions_and_overrides(self):
        ics = """BEGIN:VCALENDAR
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
        records = refresh_calendar.build_records(
            ics,
            datetime(2026, 1, 1, tzinfo=BRISBANE),
            datetime(2026, 1, 23, tzinfo=BRISBANE),
        )
        self.assertEqual(
            [record["start"] for record in records],
            [
                "2026-01-01T09:00:00+10:00",
                "2026-01-15T11:00:00+10:00",
                "2026-01-22T09:00:00+10:00",
            ],
        )
        self.assertEqual(records[1]["presiders"], ["Fr Bradley"])

    def test_utc_dates_are_converted_to_brisbane(self):
        parsed, all_day = refresh_calendar.parse_datetime({}, "20260101T230000Z")
        self.assertFalse(all_day)
        self.assertEqual(parsed.isoformat(), "2026-01-02T09:00:00+10:00")

    def test_classification_and_normalization(self):
        text = "Polish Mass at 50 Fairway Drive with Fr Jerzy Prucnal"
        self.assertEqual(refresh_calendar.classify_event(text), "multicultural")
        self.assertEqual(refresh_calendar.multicultural_subtype(text), "polish")
        self.assertEqual(refresh_calendar.normalize_church(text), "Sacred Heart")
        self.assertEqual(refresh_calendar.extract_presiders(text), ["Fr Jerzy Prucnal"])

    def test_vigil_joins_the_following_liturgical_day(self):
        event = sample_event(
            start="2026-01-03T17:00:00+10:00",
            end="2026-01-03T18:00:00+10:00",
        )
        liturgical = [{"date": "2026-01-04", "observance": "Epiphany"}]
        feed = calendar_feed.build_feed(
            [event],
            liturgical,
            "2026-01-01T08:00:00+10:00",
        )
        self.assertEqual(feed["events"][0]["service_name"], "Vigil Mass")
        self.assertEqual(feed["events"][0]["liturgical_date"], "2026-01-04")
        self.assertEqual(feed["events"][0]["liturgical"]["observance"], "Epiphany")

    def test_multicultural_service_and_presider_display(self):
        event = sample_event(event_type="multicultural", event_subtype="italian")
        event["presiders"] = ["Fr Luis Antonio Diaz Lamus"]
        result = calendar_feed.finalize_event(event, {})
        self.assertEqual(result["service_name"], "Italian Mass")
        self.assertEqual(result["presiders"], ["Fr Luis"])

    def test_feed_encoding_is_deterministic(self):
        event = sample_event()
        first = calendar_feed.build_feed([], [], "2026-01-01T00:00:00+10:00")
        second = calendar_feed.build_feed([], [], "2026-01-01T00:00:00+10:00")
        self.assertEqual(calendar_feed.encode_feed(first), calendar_feed.encode_feed(second))
        self.assertEqual(
            calendar_feed.stable_id(event),
            calendar_feed.stable_id(dict(event)),
        )

    def test_duplicate_ids_are_rejected(self):
        event = calendar_feed.finalize_event(sample_event(), {})
        feed = {
            "schema_version": 1,
            "generated_at": "2026-01-01T00:00:00+10:00",
            "timezone": "Australia/Brisbane",
            "coverage": {"start": "2026-01-01", "end": "2026-01-01"},
            "sources": [],
            "warnings": [],
            "events": [event, dict(event)],
        }
        with self.assertRaisesRegex(ValueError, "duplicate"):
            calendar_feed.validate_feed(feed)


def sample_event(
    start="2026-01-04T09:00:00+10:00",
    end="2026-01-04T10:00:00+10:00",
    event_type="mass",
    event_subtype=None,
):
    return {
        "start": start,
        "end": end,
        "all_day": False,
        "timezone": "Australia/Brisbane",
        "church": "Sacred Heart",
        "event_type": event_type,
        "event_subtype": event_subtype,
        "associated_devotions": [],
        "title": "Sacred Heart Mass - Fr Paul",
        "presiders": ["Fr Paul"],
        "location": None,
        "description": None,
        "source_id": "fixture#2026-01-04T09:00:00+10:00",
    }


if __name__ == "__main__":
    unittest.main()
