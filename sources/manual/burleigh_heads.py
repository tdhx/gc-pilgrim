from calendar import monthrange
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


PARISH_URL = "https://burleighheadscatholic.com.au/mass-liturgy-schedule/"
NEWSLETTERS_URL = "https://burleighheadscatholic.com.au/parish-newsletter/"
BRISBANE = ZoneInfo("Australia/Brisbane")


def weekly(
    service_id,
    church,
    weekday,
    start,
    event_type,
    duration=60,
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
    }


def monthly(
    service_id,
    church,
    weekday,
    ordinal,
    start,
    event_type,
    duration=60,
    title=None,
    description=None,
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
        "title": title,
        "description": description,
    }


# Newsletter automation can replace this normalized list without changing the
# generator or public services feed contract.
def normalized_service_definitions(source=None):
    if source is not None:
        return list(source)
    return [
        weekly("calvary-monday-mass", "Calvary", 0, "09:00", "mass"),
        weekly("mary-mother-of-mercy-tuesday-mass", "Mary Mother of Mercy", 1, "07:30", "mass"),
        weekly("our-lady-of-the-way-wednesday-mass", "Our Lady of the Way", 2, "17:30", "mass"),
        weekly("st-benedicts-thursday-reconciliation", "St Benedict's", 3, "17:00", "confession", 30),
        weekly("st-benedicts-thursday-mass", "St Benedict's", 3, "17:30", "mass"),
        weekly(
            "mary-mother-of-mercy-friday-mass",
            "Mary Mother of Mercy",
            4,
            "10:00",
            "mass",
            excluded_ordinals=[1],
        ),
        monthly(
            "mary-mother-of-mercy-first-friday-healing-mass",
            "Mary Mother of Mercy",
            4,
            1,
            "10:00",
            "mass",
            title="First Friday of the Month - Healing Mass",
            description="Anointing of the Sick is celebrated during Mass.",
        ),
        weekly("infant-saviour-saturday-mass", "Infant Saviour", 5, "08:00", "mass"),
        weekly("calvary-saturday-reconciliation", "Calvary", 5, "16:15", "confession", 45),
        weekly("calvary-vigil-mass", "Calvary", 5, "17:00", "mass"),
        weekly(
            "our-lady-of-the-way-saturday-reconciliation",
            "Our Lady of the Way",
            5,
            "17:15",
            "confession",
            45,
        ),
        weekly("our-lady-of-the-way-vigil-mass", "Our Lady of the Way", 5, "18:00", "mass"),
        weekly("infant-saviour-sunday-mass", "Infant Saviour", 6, "07:00", "mass"),
        weekly("our-lady-of-the-way-sunday-mass", "Our Lady of the Way", 6, "07:00", "mass"),
        weekly("calvary-sunday-mass", "Calvary", 6, "08:30", "mass"),
        weekly("st-benedicts-sunday-mass", "St Benedict's", 6, "08:30", "mass"),
        weekly(
            "mary-mother-of-mercy-sunday-mass",
            "Mary Mother of Mercy",
            6,
            "10:00",
            "mass",
            excluded_ordinals=[4],
        ),
        monthly(
            "mary-mother-of-mercy-family-mass",
            "Mary Mother of Mercy",
            6,
            4,
            "10:00",
            "mass",
            title="Children's Family Mass",
        ),
        weekly(
            "mary-mother-of-mercy-sunday-reconciliation",
            "Mary Mother of Mercy",
            6,
            "17:00",
            "confession",
            30,
        ),
        weekly("mary-mother-of-mercy-sunday-evening-mass", "Mary Mother of Mercy", 6, "17:30", "mass"),
        monthly("calvary-first-tuesday-adoration", "Calvary", 1, 1, "19:00", "adoration"),
        monthly(
            "mary-mother-of-mercy-third-friday-adoration",
            "Mary Mother of Mercy",
            4,
            3,
            "09:00",
            "adoration",
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
    if service.get("title"):
        return service["title"]
    names = {
        "mass": "Mass",
        "confession": "Reconciliation",
        "adoration": "Adoration",
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
                "description": service.get("description"),
                "source_id": f'burleigh-heads-schedule:{service["id"]}#{start.isoformat()}',
            })
    return sorted(records, key=lambda item: (item["start"], item["end"], item["title"]))
