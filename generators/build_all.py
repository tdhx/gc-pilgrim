#!/usr/bin/env python3

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from generators.build_community import build as build_community
from generators.build_liturgical import aggregate_feed, annual_feed
from generators.build_parish import build as build_parish
from generators.build_services import build as build_services
from generators.io import read_json, read_json_lines, write_json
from sources.google_calendar import adapter as google_calendar
from sources.website import liturgical as universalis
from validators.feeds import validate_registry


ROOT = Path(__file__).resolve().parent.parent
PARISH_ID = "surfers-paradise"
TIMEZONE = "Australia/Brisbane"
BRISBANE = ZoneInfo(TIMEZONE)
YEARS = (2026, 2027, 2028)


def build(offline=False, generated_at=None):
    generated_at = generated_at or datetime.now(BRISBANE).isoformat(timespec="seconds")
    parish = build_parish(ROOT / "parishes" / PARISH_ID / "parish.json")
    config = read_json(ROOT / "parishes" / PARISH_ID / "config.json")

    if offline:
        calendar_records = read_json_lines(
            ROOT / "raw" / PARISH_ID / "google-calendar.jsonl"
        )
        annual_records = {
            year: read_json_lines(ROOT / "raw" / "liturgical" / f"{year}.jsonl")
            for year in YEARS
        }
        source_status = "cached"
    else:
        start, end = google_calendar.default_window()
        calendar_records = google_calendar.build_records(
            google_calendar.fetch_calendar_text(), start, end
        )
        google_calendar.write_records(
            calendar_records,
            ROOT / "raw" / PARISH_ID / "google-calendar.jsonl",
        )
        annual_records = {}
        for year in YEARS:
            records = universalis.build_calendar_records(
                universalis.fetch_calendar_html(year), year
            )
            universalis.write_records(
                records, ROOT / "raw" / "liturgical" / f"{year}.jsonl"
            )
            annual_records[year] = records
        source_status = "fresh"

    calendar_sources = [{
        "name": "SPCP Google Calendar",
        "url": google_calendar.ICS_URL,
        "status": source_status,
    }]
    annual_feeds = [
        annual_feed(annual_records[year], generated_at, year)
        for year in YEARS
    ]
    liturgical_records = [
        {"date": key, **value}
        for feed in annual_feeds
        for key, value in feed["dates"].items()
    ]
    services = build_services(
        calendar_records,
        liturgical_records,
        generated_at,
        config["timezone"],
        calendar_sources,
        parish,
    )
    community = build_community(
        calendar_records,
        generated_at,
        config["timezone"],
        calendar_sources,
    )
    registry = validate_registry({
        "schema_version": 1,
        "default_parish_id": PARISH_ID,
        "parishes": [PARISH_ID],
    })

    output = ROOT / "feeds" / "v1"
    parish_output = output / "parishes" / PARISH_ID
    write_json(output / "registry.json", registry)
    write_json(parish_output / "parish.json", parish)
    write_json(parish_output / "services.json", services)
    write_json(parish_output / "community.json", community)
    for feed in annual_feeds:
        write_json(output / "liturgical" / f"{feed['year']}.json", feed)
    write_json(output / "liturgical.json", aggregate_feed(annual_feeds, generated_at))
    return {
        "registry": registry,
        "parish": parish,
        "services": services,
        "community": community,
        "liturgical": aggregate_feed(annual_feeds, generated_at),
    }


def main():
    parser = argparse.ArgumentParser(description="Build GC Pilgrim modular feeds.")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    feeds = build(offline=args.offline)
    print(
        f"Wrote {len(feeds['services']['services'])} services and "
        f"{len(feeds['community']['events'])} community events."
    )


if __name__ == "__main__":
    main()
