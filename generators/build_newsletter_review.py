import json
from pathlib import Path

from generators.churches import resolve_church
from generators.io import read_json, read_json_lines


PARISH_NAMES = {
    "surfers-paradise": "Surfers Paradise",
    "burleigh-heads": "Burleigh Heads",
}


def optional_json_lines(path):
    return read_json_lines(path) if path.exists() else []


def latest_audit(directory):
    state_path = directory / "state.json"
    if not state_path.exists():
        return None
    state = read_json(state_path)
    audit_path = directory.parents[2] / state["latest_audit"]
    return read_json(audit_path) if audit_path.exists() else None


def review_divergences(records, parish, schedule):
    enriched = []
    for record in records:
        item = dict(record)
        resolution = resolve_church(item.get("church"), parish or {"churches": []})
        item["normalized_church"] = resolution["normalized"]
        item["church_resolution"] = resolution["status"]
        item["resolved_church_id"] = (
            resolution["church"]["id"] if resolution["church"] else None
        )
        item["resolved_church_name"] = (
            resolution["church"].get("calendar_name", resolution["church"]["name"])
            if resolution["church"] else None
        )
        matching_results = [
            service
            for service in schedule
            if service["start"][:10] == item.get("date")
            and service["start"][11:16] == item.get("start_time")
            and (
                not resolution["church"]
                or service.get("church_id") == resolution["church"]["id"]
            )
        ]
        matched_base = next(
            (
                service for service in schedule
                if service.get("source_id") == item.get("matched_source_id")
            ),
            None,
        )
        published_liturgy = next(
            (
                service for service in matching_results
                if service["event_type"] == "liturgy"
                and (service.get("source_id") or "").startswith("newsletter:")
            ),
            None,
        )
        if item.get("replaces_event_type") and matched_base and published_liturgy:
            item["publication_decision"] = "cancel-and-add-replacement"
        elif item.get("classification") == "cancelled" and matched_base:
            item["publication_decision"] = (
                "cancel-matched-service"
                if matched_base["status"] == "cancelled" else "audit-only"
            )
        elif item.get("classification") == "changed" and matched_base:
            item["publication_decision"] = (
                "modify-matched-service"
                if matched_base["status"] == "modified" else "audit-only"
            )
        elif published_liturgy:
            item["publication_decision"] = "add-liturgy"
            item["matched_source_id"] = (
                item.get("matched_source_id")
                or published_liturgy.get("source_id")
            )
        else:
            item["publication_decision"] = "audit-only"
        enriched.append(item)
    return enriched


def build(root, generated_at, parish_feeds=None):
    root = Path(root)
    parish_feeds = parish_feeds or {}
    parishes = []
    for parish_id, parish_name in PARISH_NAMES.items():
        directory = root / "raw" / parish_id / "newsletter"
        audit = latest_audit(directory)
        feeds = parish_feeds.get(parish_id, {})
        parish = feeds.get("parish")
        services = feeds.get("services", {}).get("services", [])
        churches = {
            church["id"]: church.get("calendar_name", church["name"])
            for church in (parish or {}).get("churches", [])
        }
        schedule = [
            {
                "id": service["id"],
                "source_id": service.get("source_id"),
                "title": service.get("title"),
                "event_type": service["event_type"],
                "start": service["start"],
                "end": service["end"],
                "church_id": service.get("church_id"),
                "church": churches.get(service.get("church_id")),
                "status": service["status"],
            }
            for service in services
        ]
        divergences = review_divergences(
            read_json_lines(directory / "service-divergences.jsonl"),
            parish,
            schedule,
        )
        parishes.append({
            "id": parish_id,
            "name": parish_name,
            "parish": parish,
            "schedule": schedule,
            "document": audit.get("document") if audit else None,
            "processed_at": audit.get("processed_at") if audit else None,
            "parser_mode": audit.get("parser_mode") if audit else None,
            "model": audit.get("model") if audit else None,
            "text_quality": audit.get("text_quality") if audit else None,
            "events": optional_json_lines(directory / "community.jsonl"),
            "series": optional_json_lines(directory / "series.jsonl"),
            "quarantined": audit.get("quarantined", []) if audit else [],
            "series_quarantined": (
                audit.get("series_quarantined", []) if audit else []
            ),
            "completeness": audit.get("completeness", {}) if audit else {},
            "divergences": divergences,
        })
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "parishes": parishes,
    }
