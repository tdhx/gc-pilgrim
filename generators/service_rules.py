#!/usr/bin/env python3

import hashlib
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


BRISBANE = ZoneInfo("Australia/Brisbane")
SCHEMA_VERSION = 1
MULTICULTURAL_TYPE = "multicultural"


def title_case(value):
    return " ".join(word[:1].upper() + word[1:] for word in value.split())


def subtype_label(value):
    if value == "syro-malabar":
        return "Syro-Malabar Mass"
    return f"{title_case(value)} Mass"


def normalized_presiders(names):
    display_names = {
        "Fr John Maher": "Fr John",
        "Fr Jerzy Prucnal": "Fr Jerzy",
        "Fr Luis Antonio Diaz Lamus": "Fr Luis",
    }
    return list(dict.fromkeys(display_names.get(name, name) for name in names))


def event_date(event):
    return event["start"][:10]


def event_hour(event):
    if event["all_day"]:
        return 0
    return datetime.fromisoformat(event["start"]).astimezone(BRISBANE).hour


def is_first_saturday_mass(event):
    source = f'{event["title"]} {event.get("description") or ""}'
    return bool(re.search(r"\bfirst\s+saturday\s+mass\b", source, re.IGNORECASE))


def is_roman_mass(event):
    return event["event_type"] == "mass" or (
        event["event_type"] == MULTICULTURAL_TYPE
        and event.get("event_subtype") not in {"maronite", "syro-malabar"}
    )


def is_vigil_mass(event):
    value = datetime.fromisoformat(event_date(event))
    return (
        is_roman_mass(event)
        and value.weekday() == 5
        and event_hour(event) >= 16
        and not is_first_saturday_mass(event)
    )


def service_name(event):
    event_type = event["event_type"]
    source = f'{event["title"]} {event.get("description") or ""}'.lower()
    if event_type == "confession":
        return "Reconciliation"
    if event_type == "baptism":
        return "Baptism"
    if event_type == MULTICULTURAL_TYPE:
        return subtype_label(event.get("event_subtype") or "Multicultural")
    if event_type != "mass":
        return title_case(event_type)
    named_masses = (
        ("healing mass", "Healing Mass"),
        ("ash wednesday", "Ash Wednesday Mass"),
        ("christmas", "Christmas Mass"),
        ("funeral", "Funeral Mass"),
        ("first saturday", "First Saturday Mass"),
    )
    for needle, name in named_masses:
        if needle in source:
            return name
    start = datetime.fromisoformat(event["start"])
    if start.astimezone(BRISBANE).weekday() == 6:
        return "Sunday Mass"
    if is_vigil_mass(event):
        return "Vigil Mass"
    return "Weekday Mass"


def stable_id(event):
    digest = hashlib.sha256(
        f'{event["source_id"]}\0{event["start"]}'.encode("utf-8")
    ).hexdigest()
    return digest[:24]


def finalize_event(event, liturgical_by_date):
    result = dict(event)
    if (
        not result.get("church")
        and re.search(r"\bhealing mass\b", result["title"], re.IGNORECASE)
    ):
        result["church"] = "Sacred Heart"
    result["presiders"] = normalized_presiders(result.get("presiders", []))
    result["service_name"] = service_name(result)
    result["id"] = stable_id(result)
    result["liturgical_date"] = None
    result["liturgical"] = None
    if is_roman_mass(result):
        date_value = datetime.fromisoformat(event_date(result))
        if is_vigil_mass(result):
            date_value += timedelta(days=1)
        liturgical_date = date_value.date().isoformat()
        result["liturgical_date"] = liturgical_date
        result["liturgical"] = liturgical_by_date.get(liturgical_date)
    return result


def validate_feed(feed):
    if feed["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported feed schema")
    events = feed["events"]
    ids = [event["id"] for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("Feed contains duplicate event IDs")
    if events != sorted(events, key=lambda item: (item["start"], item["end"], item["title"])):
        raise ValueError("Feed events are not sorted")
    for event in events:
        required = ("id", "start", "end", "timezone", "event_type", "service_name", "title", "source_id")
        missing = [key for key in required if not event.get(key)]
        if missing:
            raise ValueError(f'Event {event.get("id", "(unknown)")} is missing {", ".join(missing)}')
        datetime.fromisoformat(event["start"]) if not event["all_day"] else datetime.fromisoformat(event["start"])
        datetime.fromisoformat(event["end"]) if not event["all_day"] else datetime.fromisoformat(event["end"])
    coverage = feed["coverage"]
    if coverage["start"] > coverage["end"]:
        raise ValueError("Feed coverage is invalid")


def build_feed(events, liturgical_records, generated_at, warnings=None, sources=None):
    liturgical_by_date = {record["date"]: record for record in liturgical_records}
    finalized = [finalize_event(event, liturgical_by_date) for event in events]
    finalized.sort(key=lambda item: (item["start"], item["end"], item["title"]))
    generated_date = datetime.fromisoformat(generated_at).astimezone(BRISBANE)
    coverage_start = generated_date.date().replace(day=1).isoformat()
    coverage_end = finalized[-1]["start"][:10] if finalized else generated_at[:10]
    feed = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "timezone": "Australia/Brisbane",
        "coverage": {"start": coverage_start, "end": coverage_end},
        "sources": sources or [],
        "warnings": warnings or [],
        "events": finalized,
    }
    validate_feed(feed)
    return feed


def encode_feed(feed):
    return json.dumps(feed, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
