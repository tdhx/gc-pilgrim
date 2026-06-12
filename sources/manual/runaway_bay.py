from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


PARISH_URL = "https://www.holyfamilyrunawaybay.org.au/mass-times.html"
BRISBANE = ZoneInfo("Australia/Brisbane")


def weekly(service_id, church, weekday, start, duration=60):
    return {
        "id": service_id,
        "church": church,
        "weekday": weekday,
        "start": start,
        "duration_minutes": duration,
    }


def normalized_service_definitions(source=None):
    if source is not None:
        return list(source)
    return [
        weekly("holy-family-tuesday-mass", "Holy Family", 1, "09:30"),
        weekly("holy-family-thursday-mass", "Holy Family", 3, "09:30"),
        weekly("holy-family-vigil-mass", "Holy Family", 5, "16:00"),
        weekly("our-lady-of-hope-vigil-mass", "Our Lady of Hope", 5, "17:30"),
        weekly("holy-family-sunday-7-mass", "Holy Family", 6, "07:00"),
        weekly("holy-family-sunday-9-mass", "Holy Family", 6, "09:00"),
    ]


def service_dates(service, window_start, window_end):
    cursor = window_start.date()
    cursor += timedelta(days=(service["weekday"] - cursor.weekday()) % 7)
    while cursor < window_end.date():
        yield cursor
        cursor += timedelta(days=7)


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
                "event_type": "mass",
                "event_subtype": None,
                "associated_devotions": [],
                "title": f'{service["church"]} - Mass',
                "presiders": [],
                "location": service["church"],
                "description": None,
                "source_id": f'runaway-bay-schedule:{service["id"]}#{start.isoformat()}',
            })
    return sorted(records, key=lambda item: (item["start"], item["end"], item["title"]))
