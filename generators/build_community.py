from generators.common import WORSHIP_TYPES, envelope
from generators.churches import resolve_location
from generators.service_rules import stable_id
from validators.feeds import validate_community


def build(records, generated_at, timezone, sources, parish=None):
    events = []
    for record in records:
        event_type = record.get("event_type")
        if event_type in WORSHIP_TYPES or event_type == "administration":
            continue
        resolution = (
            resolve_location(record.get("location"), parish)
            if parish else {"church": None, "venue": record.get("venue")}
        )
        church = resolution.get("church")
        event = {
            "id": record.get("id") or stable_id(record),
            "title": record["title"],
            "start": record["start"],
            "end": record["end"],
            "status": record.get("status", "active"),
            "all_day": record.get("all_day", False),
            "timezone": record.get("timezone", timezone),
            "location": record.get("location"),
            "venue": record.get("venue") or resolution.get("venue"),
            "church_id": record.get("church_id") or (
                church["id"] if church else None
            ),
            "church_name": record.get("church_name") or (
                church.get("calendar_name", church["name"]) if church else None
            ),
            "series_id": record.get("series_id"),
            "series_title": record.get("series_title"),
            "category": record.get("category"),
            "recurrence": record.get("recurrence"),
            "description": record.get("description"),
            "source_id": record.get("source_id"),
            "source": record.get("source") or (
                sources[0]["name"] if sources else None
            ),
            "last_updated": generated_at,
        }
        events.append(event)
    feed = envelope(events, generated_at, timezone, sources, "events")
    return validate_community(feed, parish)
