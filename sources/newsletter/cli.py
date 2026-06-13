#!/usr/bin/env python3

import argparse
import json

from generators.io import read_json, read_json_lines
from sources.google_calendar.adapter import default_window
from sources.manual import burleigh_heads
from sources.newsletter.pipeline import ROOT, SUPPORTED_PARISHES, process_latest


def services_for(parish_id):
    if parish_id == "surfers-paradise":
        return read_json_lines(
            ROOT / "raw" / "surfers-paradise" / "google-calendar.jsonl"
        )
    if parish_id == "burleigh-heads":
        start, end = default_window()
        return burleigh_heads.normalise(start, end)
    raise ValueError(f"Unsupported parish: {parish_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract community events from the latest parish newsletter."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--parish", choices=SUPPORTED_PARISHES)
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--model", help="OpenAI model; defaults to OPENAI_MODEL")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess the newest document even when it is unchanged.",
    )
    args = parser.parse_args()
    parishes = SUPPORTED_PARISHES if args.all else (args.parish,)
    results = {
        parish_id: process_latest(
            parish_id,
            services_for(parish_id),
            model=args.model,
            parish=read_json(ROOT / "parishes" / parish_id / "parish.json"),
            force=args.force,
        )
        for parish_id in parishes
    }
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
