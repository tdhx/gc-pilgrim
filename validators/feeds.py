#!/usr/bin/env python3

from datetime import date, datetime


SCHEMA_VERSION = 1
STATUSES = {"active", "cancelled", "modified"}
CHURCH_STATUSES = {"temporarily-closed"}
LOCATION_TYPES = {"chaplaincy", "mass-centre", "retirement-community"}


def _require(feed, fields, label):
    missing = [field for field in fields if feed.get(field) in (None, "")]
    if missing:
        raise ValueError(f"{label} is missing {', '.join(missing)}")


def _validate_envelope(feed, collection_name):
    if feed.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported feed schema")
    _require(feed, ("generated_at", "timezone", "coverage"), "Feed")
    coverage = feed["coverage"]
    _require(coverage, ("start", "end"), "Coverage")
    if coverage["start"] > coverage["end"]:
        raise ValueError("Feed coverage is invalid")
    records = feed.get(collection_name)
    if not isinstance(records, list):
        raise ValueError(f"Feed must include {collection_name}")
    return records


def _validate_records(records, required, label):
    identifiers = []
    for record in records:
        _require(record, required, label)
        if record["status"] not in STATUSES:
            raise ValueError(f"{label} {record['id']} has invalid status")
        datetime.fromisoformat(record["start"])
        datetime.fromisoformat(record["end"])
        identifiers.append(record["id"])
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{label} feed contains duplicate IDs")
    if records != sorted(records, key=lambda item: (item["start"], item["end"], item["id"])):
        raise ValueError(f"{label} feed is not sorted")


def validate_registry(feed):
    if feed.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported registry schema")
    _require(feed, ("default_parish_id", "parishes"), "Registry")
    parishes = feed["parishes"]
    if not isinstance(parishes, list) or not parishes:
        raise ValueError("Registry must include at least one parish")
    if len(parishes) != len(set(parishes)):
        raise ValueError("Registry contains duplicate parish IDs")
    if feed["default_parish_id"] not in parishes:
        raise ValueError("Registry default parish is not registered")
    aggregate = feed.get("aggregate_view")
    if aggregate:
        _require(aggregate, ("id", "name"), "Aggregate view")
        if aggregate["id"] in parishes:
            raise ValueError("Registry aggregate view conflicts with a parish")
    view_ids = ([aggregate["id"]] if aggregate else []) + parishes
    default_view_id = feed.get("default_view_id")
    if default_view_id and default_view_id not in view_ids:
        raise ValueError("Registry default view is not registered")
    return feed


def validate_parish(feed):
    if feed.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported parish schema")
    _require(feed, ("id", "name", "churches"), "Parish")
    if not isinstance(feed["churches"], list):
        raise ValueError("Parish churches must be a list")
    identifiers = []
    for church in feed["churches"]:
        _require(church, ("id", "name"), "Church")
        if church.get("status") and church["status"] not in CHURCH_STATUSES:
            raise ValueError(f"Church {church['id']} has invalid status")
        if church.get("location_type") and church["location_type"] not in LOCATION_TYPES:
            raise ValueError(f"Church {church['id']} has invalid location type")
        identifiers.append(church["id"])
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Parish contains duplicate church IDs")
    return feed


def validate_services(feed, parish=None):
    records = _validate_envelope(feed, "services")
    _validate_records(records, ("id", "event_type", "start", "end", "status"), "Service")
    if parish:
        church_ids = {church["id"] for church in parish["churches"]}
        invalid = [
            record["id"]
            for record in records
            if record.get("church_id") and record["church_id"] not in church_ids
        ]
        if invalid:
            raise ValueError(f"Services reference unknown churches: {', '.join(invalid)}")
    return feed


def validate_community(feed):
    records = _validate_envelope(feed, "events")
    _validate_records(records, ("id", "title", "start", "end", "status"), "Community event")
    return feed


def validate_liturgical(feed, expected_year=None):
    if feed.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported liturgical schema")
    dates = feed.get("dates")
    if not isinstance(dates, dict) or not dates:
        raise ValueError("Liturgical feed must include dates")
    for key, record in dates.items():
        parsed = date.fromisoformat(key)
        if expected_year is not None and parsed.year != expected_year:
            raise ValueError(f"Liturgical date {key} is outside {expected_year}")
        _require(record, ("observance", "season"), f"Liturgical date {key}")
    return feed
