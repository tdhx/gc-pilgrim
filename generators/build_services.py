from generators.common import WORSHIP_TYPES, envelope
from generators.churches import resolve_church
from generators.newsletter_overlays import apply_newsletter_overlays
from generators.service_rules import finalize_event
from validators.feeds import validate_services


def build(
    records,
    liturgical_records,
    generated_at,
    timezone,
    sources,
    parish,
    newsletter_observations=None,
):
    liturgical_by_date = {record["date"]: record for record in liturgical_records}
    services = []
    for record in records:
        if record["event_type"] not in WORSHIP_TYPES:
            continue
        service = finalize_event(record, liturgical_by_date)
        service.pop("liturgical", None)
        church_value = service.pop("church", None)
        resolution = resolve_church(church_value, parish)
        service["church_id"] = (
            resolution["church"]["id"] if resolution["status"] == "matched" else None
        )
        service["status"] = "active"
        service["source"] = sources[0]["name"] if sources else None
        service["last_updated"] = generated_at
        services.append(service)
    services = apply_newsletter_overlays(
        services,
        newsletter_observations or [],
        parish,
        generated_at,
    )
    feed = envelope(services, generated_at, timezone, sources, "services")
    return validate_services(feed, parish)
