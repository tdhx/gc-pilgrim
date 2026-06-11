#!/usr/bin/env python3

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import calendar_feed
import parish_feed
import refresh_calendar
import refresh_liturgical_calendar
import refresh_parish


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "feeds" / "v1" / "calendar.json"
BRISBANE = ZoneInfo("Australia/Brisbane")


def read_json_lines(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build(offline=False, generated_at=None):
    warnings = []
    if offline:
        events = read_json_lines(refresh_calendar.OUTPUT_PATH)
        liturgical = read_json_lines(refresh_liturgical_calendar.OUTPUT_PATH)
        parish = parish_feed.validate_feed(
            json.loads(refresh_parish.OUTPUT_PATH.read_text(encoding="utf-8"))
        )
        sources = [
            {"name": "SPCP Google Calendar", "url": refresh_calendar.ICS_URL, "status": "cached"},
            {"name": "Universalis Brisbane", "url": refresh_liturgical_calendar.CALENDAR_URL, "status": "cached"},
        ]
    else:
        window_start, window_end = refresh_calendar.default_window()
        events = refresh_calendar.build_records(
            refresh_calendar.fetch_calendar_text(), window_start, window_end
        )
        refresh_calendar.write_records(events)
        liturgical = refresh_liturgical_calendar.build_calendar_records(
            refresh_liturgical_calendar.fetch_calendar_html()
        )
        refresh_liturgical_calendar.write_records(liturgical)
        parish = refresh_parish.parse_homepage(refresh_parish.fetch_homepage())
        refresh_parish.write_feed(parish)
        sources = [
            {"name": "SPCP Google Calendar", "url": refresh_calendar.ICS_URL, "status": "fresh"},
            {"name": "Universalis Brisbane", "url": refresh_liturgical_calendar.CALENDAR_URL, "status": "fresh"},
        ]

    generated_at = generated_at or datetime.now(BRISBANE).isoformat(timespec="seconds")
    feed = calendar_feed.build_feed(events, liturgical, generated_at, warnings, sources)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".json.tmp")
    temporary.write_text(calendar_feed.encode_feed(feed), encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    return feed


def main():
    parser = argparse.ArgumentParser(description="Build the SPCP versioned calendar feed.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Build from the checked-in JSONL inputs without downloading sources.",
    )
    args = parser.parse_args()
    feed = build(offline=args.offline)
    print(
        f'Wrote {len(feed["events"])} events covering '
        f'{feed["coverage"]["start"]} to {feed["coverage"]["end"]} to {OUTPUT_PATH}'
    )
    print(f"Validated parish data at {refresh_parish.OUTPUT_PATH}")


if __name__ == "__main__":
    main()
