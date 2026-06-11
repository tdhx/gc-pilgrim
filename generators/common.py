from datetime import datetime


WORSHIP_TYPES = {
    "adoration",
    "mass",
    "confession",
    "baptism",
    "multicultural",
    "funeral",
    "liturgy",
    "novena",
    "rosary",
    "wedding",
}


def envelope(records, generated_at, timezone, sources, collection):
    ordered = sorted(records, key=lambda item: (item["start"], item["end"], item["id"]))
    start = generated_at[:7] + "-01"
    end = ordered[-1]["start"][:10] if ordered else generated_at[:10]
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "timezone": timezone,
        "coverage": {"start": start, "end": end},
        "sources": sources,
        "warnings": [],
        collection: ordered,
    }


def iso_now(zone):
    return datetime.now(zone).isoformat(timespec="seconds")
