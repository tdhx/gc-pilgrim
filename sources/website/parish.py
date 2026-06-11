#!/usr/bin/env python3

import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from generators.io import write_json
from validators.feeds import validate_parish


ROOT = Path(__file__).resolve().parents[2]
PARISH_URL = "https://surfersparadiseparish.com.au"
OUTPUT_PATH = ROOT / "parishes" / "surfers-paradise" / "parish.json"


class PageTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.ignored_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data):
        if not self.ignored_depth:
            value = " ".join(data.split())
            if value:
                self.parts.append(value)


def page_text(html):
    parser = PageTextParser()
    parser.feed(html)
    return " ".join(parser.parts)


def capture(text, pattern, label):
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not find {label} on parish homepage")
    return " ".join(match.group(1).split()).strip(" ,")


def normalize_address(value):
    value = re.sub(r",\s*(QLD)\b", r" \1", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip(" ,")


def parse_homepage(html):
    text = page_text(html)
    parish_name = capture(
        text,
        r"Welcome to\s+(Surfers Paradise Catholic Parish)\b",
        "parish name",
    )
    priest = capture(text, r"Parish Priest:\s*(Fr\.?\s+Paul)\b", "parish priest")
    associate = capture(
        text,
        r"Associate Pastor:\s*(Fr\.?\s+Bradley Davies)\b",
        "associate pastor",
    )
    office_address = normalize_address(capture(
        text,
        r"Parish Office Address:\s*(.+?\bQLD(?:,\s*Australia)?(?:\s+\d{4})?)\s+Office Hours:",
        "office address",
    ).replace(", Australia", ""))
    email = capture(
        text,
        r"Parish Email:\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
        "parish email",
    )
    phone = capture(
        text,
        r"Parish Phone Number:\s*(\(\d{2}\)\s*\d{4}\s*\d{4})",
        "parish phone",
    )

    church_specs = (
        ("sacred-heart", "Sacred Heart Church", True),
        ("stella-maris", "Stella Maris Church", False),
        ("st-vincents", "St Vincent's Church", False),
    )
    churches = []
    for church_id, name, primary in church_specs:
        address = normalize_address(capture(
            text,
            rf"{re.escape(name)}\s+Address:\s*(.+?\bQLD\s+\d{{4}})",
            f"{name} address",
        ))
        churches.append({
            "id": church_id,
            "name": name,
            "address": address,
            "is_primary_site": primary,
        })
    if not re.search(r"\b\d{4}$", office_address):
        primary_address = next(
            church["address"] for church in churches if church["is_primary_site"]
        )
        if primary_address.startswith(office_address):
            office_address = primary_address

    feed = {
        "schema_version": 1,
        "id": "surfers-paradise",
        "name": parish_name,
        "contact": {
            "phone": phone,
            "email": email,
            "website": PARISH_URL,
        },
        "office": {
            "address": office_address,
            "hours": {
                "monday": "09:00-14:00",
                "tuesday": "09:00-14:00",
                "wednesday": "09:00-14:00",
                "thursday": "09:00-14:00",
                "friday": "09:00-12:00",
            },
        },
        "clergy": [
            {"role": "Parish Priest", "name": priest.replace("Fr.", "Fr")},
            {"role": "Associate Pastor", "name": associate.replace("Fr.", "Fr")},
        ],
        "churches": churches,
    }
    return validate_parish(feed)


def fetch_homepage():
    request = urllib.request.Request(
        f"{PARISH_URL}/",
        headers={"User-Agent": "GC-Pilgrim/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8")


def write_feed(feed):
    write_json(OUTPUT_PATH, validate_parish(feed))


def main():
    feed = parse_homepage(fetch_homepage())
    write_feed(feed)
    print(f'Wrote {feed["name"]} parish data to {OUTPUT_PATH}')


if __name__ == "__main__":
    main()


def fetch():
    return fetch_homepage()


def normalise(homepage):
    return parse_homepage(homepage)
