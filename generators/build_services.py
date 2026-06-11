from generators.common import CHURCH_IDS, WORSHIP_TYPES, envelope
from generators.service_rules import finalize_event
from validators.feeds import validate_services


def build(records, liturgical_records, generated_at, timezone, sources, parish):
    liturgical_by_date = {record["date"]: record for record in liturgical_records}
    services = []
    for record in records:
        if record["event_type"] not in WORSHIP_TYPES:
            continue
        service = finalize_event(record, liturgical_by_date)
        service.pop("liturgical", None)
        service["church_id"] = CHURCH_IDS.get(service.pop("church", None))
        service["status"] = "active"
        service["source"] = sources[0]["name"] if sources else None
        service["last_updated"] = generated_at
        services.append(service)
    feed = envelope(services, generated_at, timezone, sources, "services")
    return validate_services(feed, parish)
