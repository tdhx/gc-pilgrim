"""Compatibility conversion from the SPCP combined v1 calendar feed."""

from generators.build_community import build as build_community
from generators.build_services import build as build_services


def split(legacy_feed, parish):
    records = []
    liturgical = {}
    for event in legacy_feed["events"]:
        source = dict(event)
        record = source.pop("liturgical", None)
        if record:
            liturgical[record["date"]] = record
        records.append(source)
    metadata = (
        legacy_feed["generated_at"],
        legacy_feed["timezone"],
        legacy_feed.get("sources", []),
    )
    return (
        build_services(records, list(liturgical.values()), *metadata, parish),
        build_community(records, *metadata),
    )
