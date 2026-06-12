from calendar import monthrange
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


PARISH_URL = "https://stbrigidsparishnerang.org.au/mass-times/"
NEWSLETTERS_URL = "https://stbrigidsparishnerang.org.au/parishnews/"
BRISBANE = ZoneInfo("Australia/Brisbane")


def weekly(
    service_id,
    church,
    weekday,
    start,
    event_type,
    duration=60,
    subtype=None,
    devotions=None,
    excluded_ordinals=None,
):
    return {
        "id": service_id,
        "church": church,
        "recurrence": {
            "frequency": "weekly",
            "weekday": weekday,
            "excluded_ordinals": excluded_ordinals or [],
        },
        "start": start,
        "duration_minutes": duration,
        "event_type": event_type,
        "event_subtype": subtype,
        "associated_devotions": devotions or [],
    }


def monthly(
    service_id,
    church,
    weekday,
    ordinal,
    start,
    event_type,
    duration=60,
    subtype=None,
    devotions=None,
):
    return {
        "id": service_id,
        "church": church,
        "recurrence": {
            "frequency": "monthly",
            "weekday": weekday,
            "ordinal": ordinal,
        },
        "start": start,
        "duration_minutes": duration,
        "event_type": event_type,
        "event_subtype": subtype,
        "associated_devotions": devotions or [],
    }


# Newsletter automation can replace this normalized list without changing the
# generator or public services feed contract.
def normalized_service_definitions(source=None):
    if source is not None:
        return list(source)
    rosary = ["Rosary"]
    return [
        weekly("st-brigids-monday-mass", "St Brigid's", 0, "07:00", "mass", devotions=rosary),
        weekly("st-brigids-tuesday-mass", "St Brigid's", 1, "07:00", "mass", devotions=rosary),
        weekly(
            "st-brigids-tuesday-syro-malabar",
            "St Brigid's",
            1,
            "09:30",
            "multicultural",
            subtype="syro-malabar",
        ),
        weekly(
            "st-brigids-wednesday-syro-malabar",
            "St Brigid's",
            2,
            "09:30",
            "multicultural",
            subtype="syro-malabar",
        ),
        weekly("st-brigids-wednesday-reconciliation", "St Brigid's", 2, "17:15", "confession", 30),
        weekly("st-brigids-wednesday-mass", "St Brigid's", 2, "18:00", "mass", devotions=rosary),
        weekly("st-brigids-thursday-mass", "St Brigid's", 3, "07:00", "mass", devotions=rosary),
        weekly("st-brigids-friday-mass", "St Brigid's", 4, "07:00", "mass", devotions=rosary),
        weekly(
            "st-brigids-friday-syro-malabar",
            "St Brigid's",
            4,
            "18:00",
            "multicultural",
            subtype="syro-malabar",
            excluded_ordinals=[1],
        ),
        monthly(
            "st-brigids-first-friday-syro-malabar",
            "St Brigid's",
            4,
            1,
            "18:00",
            "multicultural",
            subtype="syro-malabar",
            devotions=["Adoration"],
        ),
        monthly("earle-haven-first-friday-mass", "Earle Haven", 4, 1, "09:30", "mass"),
        weekly("st-brigids-saturday-reconciliation", "St Brigid's", 5, "08:15", "confession", 30),
        weekly("st-brigids-saturday-mass", "St Brigid's", 5, "09:00", "mass"),
        weekly("st-brigids-vigil-reconciliation", "St Brigid's", 5, "17:15", "confession", 30),
        weekly("st-brigids-vigil-mass", "St Brigid's", 5, "18:00", "mass", devotions=rosary),
        weekly("st-brigids-sunday-mass", "St Brigid's", 6, "08:30", "mass", devotions=rosary),
        weekly(
            "st-brigids-sunday-syro-malabar",
            "St Brigid's",
            6,
            "10:30",
            "multicultural",
            subtype="syro-malabar",
        ),
    ]


def ordinal_in_month(value):
    return ((value.day - 1) // 7) + 1


def first_matching_weekday(year, month, weekday, ordinal):
    matches = [
        day
        for day in range(1, monthrange(year, month)[1] + 1)
        if datetime(year, month, day).weekday() == weekday
    ]
    return matches[ordinal - 1]


def service_dates(service, window_start, window_end):
    recurrence = service["recurrence"]
    cursor = window_start.date()
    if recurrence["frequency"] == "weekly":
        cursor += timedelta(days=(recurrence["weekday"] - cursor.weekday()) % 7)
        while cursor < window_end.date():
            if ordinal_in_month(cursor) not in recurrence["excluded_ordinals"]:
                yield cursor
            cursor += timedelta(days=7)
        return

    year, month = cursor.year, cursor.month
    while datetime(year, month, 1, tzinfo=BRISBANE) < window_end:
        day = first_matching_weekday(
            year,
            month,
            recurrence["weekday"],
            recurrence["ordinal"],
        )
        candidate = datetime(year, month, day, tzinfo=BRISBANE).date()
        if window_start.date() <= candidate < window_end.date():
            yield candidate
        month += 1
        if month == 13:
            year += 1
            month = 1


def title_for(service):
    if service["event_type"] == "multicultural":
        return f'{service["church"]} - Syro-Malabar Mass'
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
                "event_subtype": service.get("event_subtype"),
                "associated_devotions": list(service["associated_devotions"]),
                "title": title_for(service),
                "presiders": [],
                "location": service["church"],
                "description": None,
                "source_id": f'nerang-schedule:{service["id"]}#{start.isoformat()}',
            })
    return sorted(records, key=lambda item: (item["start"], item["end"], item["title"]))
