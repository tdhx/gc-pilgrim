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
from sources.manual import southport
from sources.google_calendar import adapter as google_calendar
from sources.website import liturgical as universalis
from validators.feeds import validate_registry


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARISH_ID = "surfers-paradise"
PARISH_IDS = ("surfers-paradise", "southport")
TIMEZONE = "Australia/Brisbane"
BRISBANE = ZoneInfo(TIMEZONE)
YEARS = (2026, 2027, 2028)


def build(offline=False, generated_at=None):
    generated_at = generated_at or datetime.now(BRISBANE).isoformat(timespec="seconds")

    if offline:
        surfers_records = read_json_lines(
            ROOT / "raw" / DEFAULT_PARISH_ID / "google-calendar.jsonl"
        )
        annual_records = {
            year: read_json_lines(ROOT / "raw" / "liturgical" / f"{year}.jsonl")
            for year in YEARS
        }
        source_status = "cached"
    else:
        start, end = google_calendar.default_window()
        surfers_records = google_calendar.build_records(
            google_calendar.fetch_calendar_text(), start, end
        )
        google_calendar.write_records(
            surfers_records,
            ROOT / "raw" / DEFAULT_PARISH_ID / "google-calendar.jsonl",
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

    surfers_sources = [{
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
    start, end = google_calendar.default_window()
    parish_inputs = {
        "surfers-paradise": {
            "records": surfers_records,
            "sources": surfers_sources,
        },
        "southport": {
            "records": southport.normalise(start, end),
            "sources": [
                {
                    "name": "Southport published recurring schedule",
                    "url": southport.PARISH_URL,
                    "status": "baseline",
                },
                {
                    "name": "Southport parish newsletters",
                    "url": southport.NEWSLETTERS_URL,
                    "status": "future-automation",
                },
            ],
        },
    }
    registry = validate_registry({
        "schema_version": 1,
        "default_parish_id": DEFAULT_PARISH_ID,
        "parishes": list(PARISH_IDS),
    })

    output = ROOT / "feeds" / "v1"
    write_json(output / "registry.json", registry)
    parish_feeds = {}
    for parish_id in PARISH_IDS:
        parish = build_parish(ROOT / "parishes" / parish_id / "parish.json")
        config = read_json(ROOT / "parishes" / parish_id / "config.json")
        records = parish_inputs[parish_id]["records"]
        sources = parish_inputs[parish_id]["sources"]
        services = build_services(
            records,
            liturgical_records,
            generated_at,
            config["timezone"],
            sources,
            parish,
        )
        community = build_community(
            [] if parish_id == "southport" else records,
            generated_at,
            config["timezone"],
            sources,
        )
        parish_output = output / "parishes" / parish_id
        write_json(parish_output / "parish.json", parish)
        write_json(parish_output / "services.json", services)
        write_json(parish_output / "community.json", community)
        parish_feeds[parish_id] = {
            "parish": parish,
            "services": services,
            "community": community,
        }
    for feed in annual_feeds:
        write_json(output / "liturgical" / f"{feed['year']}.json", feed)
    write_json(output / "liturgical.json", aggregate_feed(annual_feeds, generated_at))
    return {
        "registry": registry,
        "parishes": parish_feeds,
        "liturgical": aggregate_feed(annual_feeds, generated_at),
    }


def main():
    parser = argparse.ArgumentParser(description="Build GC Pilgrim modular feeds.")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    feeds = build(offline=args.offline)
    print(
        "Wrote "
        + ", ".join(
            f"{parish_id}: {len(feeds['parishes'][parish_id]['services']['services'])} services"
            for parish_id in PARISH_IDS
        )
        + "."
    )


if __name__ == "__main__":
    main()
