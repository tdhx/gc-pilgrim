from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


PARISH_URL = "https://coolangatta-tugunparish.org.au/"
NEWSLETTER_URL = "https://coolangatta-tugunparish.org.au/documents/newsletter.pdf"
BRISBANE = ZoneInfo("Australia/Brisbane")


def weekly(service_id, church, weekday, start, event_type="mass", duration=60):
    return {
        "id": service_id,
        "church": church,
        "weekday": weekday,
        "start": start,
        "duration_minutes": duration,
        "event_type": event_type,
    }


def normalized_service_definitions(source=None):
    if source is not None:
        return list(source)
    return [
        weekly("st-monicas-wednesday-mass", "St Monica's", 2, "17:00"),
        weekly("st-augustines-friday-mass", "St Augustine's", 4, "08:00"),
        weekly(
            "st-monicas-saturday-reconciliation",
            "St Monica's",
            5,
            "17:15",
            "confession",
            45,
        ),
        weekly("st-monicas-vigil-mass", "St Monica's", 5, "18:00"),
        weekly("st-augustines-sunday-mass", "St Augustine's", 6, "08:00"),
        weekly("st-monicas-sunday-mass", "St Monica's", 6, "09:30"),
    ]


def service_dates(service, window_start, window_end):
    cursor = window_start.date()
    cursor += timedelta(days=(service["weekday"] - cursor.weekday()) % 7)
    while cursor < window_end.date():
        yield cursor
        cursor += timedelta(days=7)


def title_for(service):
    names = {
        "mass": "Mass",
        "confession": "Reconciliation",
    }
    return f'{service["church"]} - {names[service["event_type"]]}'


def normalise(window_start, window_end, definitions=None):
    records = []
    for service in normalized_service_definitions(definitions):
        hour, minute = (int(value) for value in service["start"].split(":"))
        for service_date in service_dates(service, window_start, window_end):
            start = datetime.combine(service_date, time(hour, minute), BRISBANE)
            end = start + timedelta(minutes=service["duration_minutes"])
            records.append({
                "start": start.isoformat(timespec="seconds"),
                "end": end.isoformat(timespec="seconds"),
                "all_day": False,
                "timezone": "Australia/Brisbane",
                "church": service["church"],
                "event_type": service["event_type"],
                "event_subtype": None,
                "associated_devotions": [],
                "title": title_for(service),
                "presiders": [],
                "location": service["church"],
                "description": None,
                "source_id": f'coolangatta-tugun-schedule:{service["id"]}#{start.isoformat()}',
            })
    return sorted(records, key=lambda item: (item["start"], item["end"], item["title"]))
