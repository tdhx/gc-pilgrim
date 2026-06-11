from calendar import monthrange
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


PARISH_URL = "https://scp.org.au/"
NEWSLETTERS_URL = "https://scp.org.au/newsletters-2026/"
BRISBANE = ZoneInfo("Australia/Brisbane")


def weekly(service_id, church, weekday, start, event_type, duration=60, subtype=None):
    return {
        "id": service_id,
        "church": church,
        "recurrence": {"frequency": "weekly", "weekday": weekday},
        "start": start,
        "duration_minutes": duration,
        "event_type": event_type,
        "event_subtype": subtype,
    }


def monthly(service_id, church, weekday, ordinal, start, event_type, duration=60, subtype=None):
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
    }


# Newsletter automation can replace this normalized list without changing the
# generator or public services feed contract.
def normalized_service_definitions(source=None):
    if source is not None:
        return list(source)
    return [
        weekly("guardian-angels-friday-rosary", "Guardian Angels", 4, "12:00", "rosary", 30),
        weekly("guardian-angels-friday-mass", "Guardian Angels", 4, "12:30", "mass"),
        weekly("guardian-angels-reconciliation", "Guardian Angels", 5, "16:30", "confession", 30),
        weekly("guardian-angels-vigil", "Guardian Angels", 5, "17:30", "mass"),
        weekly("guardian-angels-sunday-7", "Guardian Angels", 6, "07:00", "mass"),
        weekly("guardian-angels-sunday-9", "Guardian Angels", 6, "09:00", "mass"),
        monthly(
            "guardian-angels-filipino",
            "Guardian Angels",
            6,
            1,
            "12:00",
            "multicultural",
            subtype="filipino",
        ),
        weekly("guardian-angels-adoration", "Guardian Angels", 3, "12:00", "adoration", 24 * 60),
        weekly("st-joseph-monday-mass", "St Joseph the Worker", 0, "07:00", "mass"),
        weekly("st-joseph-wednesday-mass", "St Joseph the Worker", 2, "07:00", "mass"),
        weekly("st-joseph-sunday-mass", "St Joseph the Worker", 6, "08:00", "mass"),
        monthly("st-joseph-first-wednesday-mass", "St Joseph the Worker", 2, 1, "19:00", "mass"),
        monthly("st-joseph-first-saturday-mass", "St Joseph the Worker", 5, 1, "09:00", "mass"),
        weekly("st-joseph-monday-rosary", "St Joseph the Worker", 0, "06:00", "rosary", 30),
        weekly("st-joseph-wednesday-rosary", "St Joseph the Worker", 2, "06:00", "rosary", 30),
        monthly("st-joseph-first-wednesday-rosary", "St Joseph the Worker", 2, 1, "18:00", "rosary", 30),
        monthly("st-joseph-first-saturday-rosary", "St Joseph the Worker", 5, 1, "08:30", "rosary", 30),
        weekly("st-joseph-novena", "St Joseph the Worker", 2, "18:00", "novena", 30),
        weekly("mary-immaculate-tuesday-mass", "Mary Immaculate", 1, "09:00", "mass"),
        weekly("mary-immaculate-thursday-mass", "Mary Immaculate", 3, "09:00", "mass"),
        weekly("mary-immaculate-vigil", "Mary Immaculate", 5, "16:30", "mass"),
        weekly("mary-immaculate-sunday-930", "Mary Immaculate", 6, "09:30", "mass"),
        weekly("mary-immaculate-korean", "Mary Immaculate", 6, "15:00", "multicultural", subtype="korean"),
        weekly("mary-immaculate-sunday-530", "Mary Immaculate", 6, "17:30", "mass"),
        weekly("mary-immaculate-tuesday-adoration", "Mary Immaculate", 1, "07:45", "adoration", 45),
        weekly("mary-immaculate-thursday-adoration", "Mary Immaculate", 3, "07:45", "adoration", 45),
        weekly("hospital-friday-rosary", "Gold Coast University Hospital", 4, "10:00", "rosary", 30),
        weekly("hospital-friday-mass", "Gold Coast University Hospital", 4, "10:30", "mass"),
    ]


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
    subtype = service.get("event_subtype")
    names = {
        "mass": "Mass",
        "confession": "Reconciliation",
        "adoration": "Adoration",
        "rosary": "Rosary",
        "novena": "Novena",
    }
    service_name = f"{subtype.title()} Mass" if subtype else names[service["event_type"]]
    return f'{service["church"]} - {service_name}'


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
                "associated_devotions": [],
                "title": title_for(service),
                "presiders": [],
                "location": service["church"],
                "description": None,
                "source_id": f'southport-schedule:{service["id"]}#{start.isoformat()}',
            })
    return sorted(records, key=lambda item: (item["start"], item["end"], item["title"]))
