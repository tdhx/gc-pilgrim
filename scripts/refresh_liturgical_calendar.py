#!/usr/bin/env python3

import calendar
import html
import json
import re
import urllib.request
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "liturgical-calendar.jsonl"
CALENDAR_REGION = "australia.brisbane"
YEAR = datetime.now().year
CALENDAR_URL = f"https://universalis.com/{CALENDAR_REGION}/1000/calendar.htm"

COLOURS = {
    "lit-w": "white",
    "lit-r": "red",
    "lit-g": "green",
    "lit-p": "purple",
    "lit-k": "rose",
    "lit-b": "black",
}


def clean_text(value):
    return re.sub(r"\s+", " ", html.unescape(value).replace("\xa0", " ")).strip()


class UniversalisCalendarParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_calendar = False
        self.in_row = False
        self.cell_index = -1
        self.current_date = None
        self.segments = []
        self.segment_index = 0
        self.current_span_class = None
        self.span_text = []
        self.rank_classes = set()
        self.explicit_rank = None
        self.colours = []
        self.psalm_week = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "yearly-calendar":
            self.in_calendar = True
            return
        if not self.in_calendar:
            return
        if tag == "tr":
            self.in_row = True
            self.cell_index = -1
            self.current_date = None
            self.segments = [""]
            self.segment_index = 0
            self.rank_classes = set()
            self.explicit_rank = None
            self.colours = []
            self.psalm_week = None
        elif self.in_row and tag == "td":
            self.cell_index += 1
        elif self.in_row and tag == "a":
            href = attributes.get("href", "")
            match = re.search(r"/(\d{8})/today\.htm$", href)
            if match:
                self.current_date = datetime.strptime(match.group(1), "%Y%m%d").date()
        elif self.in_row and self.cell_index == 1 and tag == "br":
            self.segments.append("")
            self.segment_index += 1
        elif self.in_row and self.cell_index == 1 and tag == "span":
            self.current_span_class = attributes.get("class")
            self.span_text = []
            if self.current_span_class in COLOURS:
                self.colours.append(COLOURS[self.current_span_class])
            if self.current_span_class and self.current_span_class.startswith("rank-"):
                self.rank_classes.add(self.current_span_class)

    def handle_endtag(self, tag):
        if tag == "table" and self.in_calendar:
            self.in_calendar = False
            return
        if not self.in_calendar:
            return
        if self.in_row and self.cell_index == 1 and tag == "span":
            if self.current_span_class == "rank":
                value = clean_text("".join(self.span_text))
                if value:
                    self.explicit_rank = value
            self.current_span_class = None
            self.span_text = []
        elif tag == "tr" and self.in_row:
            if self.current_date:
                self.rows.append(
                    {
                        "date": self.current_date,
                        "segments": [clean_text(item) for item in self.segments if clean_text(item)],
                        "rank_classes": set(self.rank_classes),
                        "explicit_rank": self.explicit_rank,
                        "colours": list(self.colours),
                        "psalm_week": self.psalm_week,
                    }
                )
            self.in_row = False

    def handle_data(self, data):
        if not self.in_calendar or not self.in_row:
            return
        if self.cell_index == 1:
            self.segments[self.segment_index] += data
            if self.current_span_class:
                self.span_text.append(data)
        elif self.cell_index == 2:
            match = re.search(r"Psalm week\s+(\d+)", data, re.IGNORECASE)
            if match:
                self.psalm_week = int(match.group(1))


def infer_rank(row):
    if row["explicit_rank"]:
        return row["explicit_rank"]
    classes = row["rank_classes"]
    if "rank-memorial" in classes:
        return "Memorial"
    if row["date"].weekday() == 6 and "rank-sunday" in classes:
        return "Sunday"
    return None


def infer_season_week(observance):
    patterns = [
        r"(?:week|the)\s+(\d+)(?:st|nd|rd|th)?\s+week.*Ordinary Time",
        r"week\s+(\d+)\s+in Ordinary Time",
        r"(\d+)(?:st|nd|rd|th)\s+Sunday in Ordinary Time",
        r"(\d+)(?:st|nd|rd|th)\s+week of Lent",
        r"(\d+)(?:st|nd|rd|th)\s+Sunday of Lent",
        r"(\d+)(?:st|nd|rd|th)\s+week of Eastertide",
        r"(\d+)(?:st|nd|rd|th)\s+Sunday of Easter",
        r"(\d+)(?:st|nd|rd|th)\s+week of Advent",
        r"(\d+)(?:st|nd|rd|th)\s+Sunday of Advent",
    ]
    for pattern in patterns:
        match = re.search(pattern, observance, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def primary_observance(row):
    value = row["segments"][0] if row["segments"] else ""
    if row["explicit_rank"]:
        value = re.sub(
            rf"\s+{re.escape(row['explicit_rank'])}$",
            "",
            value,
            flags=re.IGNORECASE,
        )
    return clean_text(value)


def find_date(rows, predicate):
    for row in rows:
        if predicate(primary_observance(row)):
            return row["date"]
    raise ValueError("Required liturgical anchor was not found")


def season_boundaries(rows):
    baptism = find_date(rows, lambda value: value == "The Baptism of the Lord")
    ash_wednesday = find_date(rows, lambda value: value == "Ash Wednesday")
    maundy_thursday = find_date(rows, lambda value: value == "Maundy Thursday")
    easter = find_date(rows, lambda value: value == "Easter Sunday")
    pentecost = find_date(rows, lambda value: value in {"Pentecost", "Pentecost Sunday"})
    advent = find_date(rows, lambda value: "1st Sunday of Advent" in value)
    christmas = date(YEAR, 12, 25)
    return {
        "baptism": baptism,
        "ash_wednesday": ash_wednesday,
        "maundy_thursday": maundy_thursday,
        "easter": easter,
        "pentecost": pentecost,
        "advent": advent,
        "christmas": christmas,
    }


def infer_season(value, boundaries):
    if value <= boundaries["baptism"] or value >= boundaries["christmas"]:
        return "Christmas"
    if value < boundaries["ash_wednesday"]:
        return "Ordinary Time"
    if value < boundaries["maundy_thursday"]:
        return "Lent"
    if value < boundaries["easter"]:
        return "Paschal Triduum"
    if value <= boundaries["pentecost"]:
        return "Eastertide"
    if value < boundaries["advent"]:
        return "Ordinary Time"
    return "Advent"


def normalize_alternative(value):
    value = re.sub(r"^or\s+", "", value, flags=re.IGNORECASE)
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    return clean_text(value)


def build_records(rows):
    boundaries = season_boundaries(rows)
    records = []
    for row in rows:
        if not row["segments"]:
            continue
        observance = primary_observance(row)
        alternatives = [
            alternative
            for segment in row["segments"][1:]
            if (alternative := normalize_alternative(segment))
        ]
        records.append(
            {
                "date": row["date"].isoformat(),
                "observance": observance,
                "rank": infer_rank(row),
                "season": infer_season(row["date"], boundaries),
                "season_week": infer_season_week(observance),
                "liturgical_colour": row["colours"][0] if row["colours"] else None,
                "psalm_week": row["psalm_week"],
                "alternatives": alternatives,
                "source_url": (
                    f"https://universalis.com/{CALENDAR_REGION}/"
                    f"{row['date'].strftime('%Y%m%d')}/today.htm"
                ),
            }
        )
    return records


def validate(records):
    expected = 366 if calendar.isleap(YEAR) else 365
    if len(records) != expected:
        raise ValueError(f"Expected {expected} dates, found {len(records)}")
    dates = [date.fromisoformat(record["date"]) for record in records]
    if len(set(dates)) != expected:
        raise ValueError("Liturgical calendar contains duplicate dates")
    if dates[0] != date(YEAR, 1, 1) or dates[-1] != date(YEAR, 12, 31):
        raise ValueError("Liturgical calendar does not cover the complete year")
    for previous, current in zip(dates, dates[1:]):
        if current != previous + timedelta(days=1):
            raise ValueError(f"Missing date after {previous}")


def build_calendar_records(calendar_html):
    parser = UniversalisCalendarParser()
    parser.feed(calendar_html)
    records = build_records(parser.rows)
    validate(records)
    return records


def fetch_calendar_html():
    request = urllib.request.Request(
        CALENDAR_URL,
        headers={"User-Agent": "SPCP-Calendar/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def write_records(records, output_path=OUTPUT_PATH):
    output_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def main():
    records = build_calendar_records(fetch_calendar_html())
    write_records(records)
    print(f"Wrote {len(records)} liturgical dates for {YEAR} to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
