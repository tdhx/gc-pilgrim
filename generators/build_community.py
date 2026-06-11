from generators.common import WORSHIP_TYPES, envelope
from generators.service_rules import stable_id
from validators.feeds import validate_community


def build(records, generated_at, timezone, sources):
    events = []
    for record in records:
        if record["event_type"] in WORSHIP_TYPES or record["event_type"] == "administration":
            continue
        event = {
            "id": stable_id(record),
            "title": record["title"],
            "start": record["start"],
            "end": record["end"],
            "status": "active",
            "all_day": record.get("all_day", False),
            "timezone": record.get("timezone", timezone),
            "location": record.get("location"),
            "description": record.get("description"),
            "source_id": record.get("source_id"),
            "source": sources[0]["name"] if sources else None,
            "last_updated": generated_at,
        }
        events.append(event)
    feed = envelope(events, generated_at, timezone, sources, "events")
    return validate_community(feed)
