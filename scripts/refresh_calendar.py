#!/usr/bin/env python3

import calendar
import html
import json
import re
import urllib.request
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
ICS_URL = (
    "https://calendar.google.com/calendar/ical/"
    "5ecffb0b502eb6919b066ca976b06c370a81aaae0109caf8e05119f9c4fc5ee6"
    "%40group.calendar.google.com/public/basic.ics"
)
OUTPUT_PATH = ROOT / "calendar-digest.txt"
BRISBANE = ZoneInfo("Australia/Brisbane")


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def default_window():
    start = datetime.combine(datetime.now(BRISBANE).date(), time.min, BRISBANE)
    return start, add_months(start, 3)


def unfold_ics(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def unescape_ics(value):
    value = value.replace("\\n", "\n").replace("\\N", "\n")
    value = value.replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
    return html.unescape(value).strip()


def parse_property(line):
    if ":" not in line:
        return None
    left, value = line.split(":", 1)
    parts = left.split(";")
    name = parts[0].upper()
    params = {}
    for part in parts[1:]:
        if "=" in part:
            key, param_value = part.split("=", 1)
            params[key.upper()] = param_value
    return name, params, unescape_ics(value)


def parse_ics_events(text):
    events = []
    current = None
    for line in unfold_ics(text).splitlines():
        if line == "BEGIN:VEVENT":
            current = defaultdict(list)
        elif line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
        elif current is not None:
            prop = parse_property(line)
            if prop:
                name, params, value = prop
                current[name].append((params, value))
    return events


def first(event, name):
    values = event.get(name, [])
    return values[0] if values else ({}, "")


def parse_datetime(params, value):
    is_date = params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value)
    if is_date:
        parsed = datetime.strptime(value[:8], "%Y%m%d").date()
        return datetime.combine(parsed, time.min, BRISBANE), True

    if value.endswith("Z"):
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return parsed.astimezone(BRISBANE), False

    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
    tzid = params.get("TZID", "Australia/Brisbane")
    try:
        zone = ZoneInfo(tzid)
    except Exception:
        zone = BRISBANE
    return parsed.replace(tzinfo=zone).astimezone(BRISBANE), False


def parse_until(value, all_day):
    if not value:
        return None
    params = {"VALUE": "DATE"} if len(value) == 8 else {}
    parsed, parsed_all_day = parse_datetime(params, value)
    if parsed_all_day or all_day:
        return parsed + timedelta(days=1) - timedelta(microseconds=1)
    return parsed


def parse_rrule(value):
    result = {}
    for part in value.split(";"):
        if "=" in part:
            key, item = part.split("=", 1)
            result[key.upper()] = item
    return result


def weekday_number(token):
    return {
        "MO": 0,
        "TU": 1,
        "WE": 2,
        "TH": 3,
        "FR": 4,
        "SA": 5,
        "SU": 6,
    }[token]


def in_rule_bounds(candidate, start, until):
    return candidate >= start and (until is None or candidate <= until)


def expand_daily(start, rule, window_start, window_end, all_day):
    interval = int(rule.get("INTERVAL", "1"))
    until = parse_until(rule.get("UNTIL"), all_day)
    first_index = max(0, (window_start.date() - start.date()).days // interval - 1)
    candidate = start + timedelta(days=first_index * interval)
    while candidate < window_end:
        if candidate >= window_start and in_rule_bounds(candidate, start, until):
            yield candidate
        if until is not None and candidate > until:
            break
        candidate += timedelta(days=interval)


def expand_weekly(start, rule, window_start, window_end, all_day):
    interval = int(rule.get("INTERVAL", "1"))
    until = parse_until(rule.get("UNTIL"), all_day)
    wkst = weekday_number(rule.get("WKST", "MO"))
    start_week = start.date() - timedelta(days=(start.weekday() - wkst) % 7)
    bydays = rule.get("BYDAY")
    weekdays = [weekday_number(item[-2:]) for item in bydays.split(",")] if bydays else [start.weekday()]
    cursor = max(start.date(), window_start.date() - timedelta(days=7))
    end_date = window_end.date() + timedelta(days=1)

    while cursor <= end_date:
        week_start = cursor - timedelta(days=(cursor.weekday() - wkst) % 7)
        weeks = (week_start - start_week).days // 7
        if weeks >= 0 and weeks % interval == 0 and cursor.weekday() in weekdays:
            candidate = datetime.combine(cursor, start.timetz().replace(tzinfo=None), start.tzinfo)
            if candidate >= window_start and candidate < window_end and in_rule_bounds(candidate, start, until):
                yield candidate
        if until is not None and datetime.combine(cursor, time.min, start.tzinfo) > until + timedelta(days=1):
            break
        cursor += timedelta(days=1)


def nth_weekday(year, month, ordinal, weekday):
    month_calendar = calendar.monthcalendar(year, month)
    matches = [week[weekday] for week in month_calendar if week[weekday] != 0]
    if ordinal > 0:
        return matches[ordinal - 1]
    return matches[ordinal]


def expand_monthly(start, rule, window_start, window_end, all_day):
    interval = int(rule.get("INTERVAL", "1"))
    until = parse_until(rule.get("UNTIL"), all_day)
    cursor_year, cursor_month = start.year, start.month
    month_index = 0
    bydays = rule.get("BYDAY", "")

    while True:
        if bydays:
            match = re.fullmatch(r"([+-]?\d+)(MO|TU|WE|TH|FR|SA|SU)", bydays)
            if not match:
                raise ValueError(f"Unsupported monthly BYDAY: {bydays}")
            day_number = nth_weekday(
                cursor_year,
                cursor_month,
                int(match.group(1)),
                weekday_number(match.group(2)),
            )
        else:
            day_number = min(start.day, calendar.monthrange(cursor_year, cursor_month)[1])

        candidate = datetime(
            cursor_year,
            cursor_month,
            day_number,
            start.hour,
            start.minute,
            start.second,
            tzinfo=start.tzinfo,
        )
        if month_index % interval == 0:
            if candidate >= window_start and candidate < window_end and in_rule_bounds(candidate, start, until):
                yield candidate
        if candidate >= window_end or (until is not None and candidate > until):
            break

        cursor_month += 1
        if cursor_month == 13:
            cursor_month = 1
            cursor_year += 1
        month_index += 1


def expand_recurrence(start, event, window_start, window_end, all_day):
    _, rrule_value = first(event, "RRULE")
    if not rrule_value:
        if window_start <= start < window_end:
            yield start
        return

    rule = parse_rrule(rrule_value)
    frequency = rule["FREQ"]
    if frequency == "DAILY":
        yield from expand_daily(start, rule, window_start, window_end, all_day)
    elif frequency == "WEEKLY":
        yield from expand_weekly(start, rule, window_start, window_end, all_day)
    elif frequency == "MONTHLY":
        yield from expand_monthly(start, rule, window_start, window_end, all_day)
    else:
        raise ValueError(f"Unsupported recurrence frequency: {frequency}")


def event_start(event):
    params, value = first(event, "DTSTART")
    return parse_datetime(params, value)


def event_end(event, start, all_day):
    params, value = first(event, "DTEND")
    if value:
        return parse_datetime(params, value)[0]
    return start + (timedelta(days=1) if all_day else timedelta(hours=1))


def recurrence_key(event):
    params, value = first(event, "RECURRENCE-ID")
    if not value:
        return None
    return parse_datetime(params, value)[0]


def exdates(event):
    values = set()
    for params, raw in event.get("EXDATE", []):
        for item in raw.split(","):
            values.add(parse_datetime(params, item)[0])
    return values


CHURCH_PATTERNS = {
    "Sacred Heart": [
        r"\bsacred\s+heart\b",
        r"\bclear\s+island\s+waters\b",
        r"\bciw\b",
        r"\bsh\b",
        r"\b50\s+fairway\b",
    ],
    "St. Vincent's": [
        r"\b(?:st\.?|saint)\s+vincent(?:'s|s)?\b",
        r"\bsurfers(?:\s+paradise)?\b",
        r"\bsv\b",
        r"\b40\s+hamilton\b",
        r"\bhamilton\s+avenue\b",
    ],
    "Stella Maris": [
        r"\bstella\s+maris\b",
        r"\bbroadbeach\b",
        r"\bmermaid\s+beach\b",
        r"\bsm\b",
        r"\b254\s+hedges\b",
        r"\bhedges\s+avenue\b",
    ],
}


def normalize_church(text):
    matched = []
    for church, patterns in CHURCH_PATTERNS.items():
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            matched.append(church)
    return matched[0] if len(matched) == 1 else None


def classify_event(text):
    lowered = text.lower()
    if re.search(r"\b(reconciliation|reconciliations|confession|confessions|reco)\b", lowered):
        return "confession"
    if re.search(r"\b(polish|italian|hispanic|maronite)\s+mass\b", lowered):
        return "multicultural"
    if re.search(r"\b(funeral|requiem|burial)\b", lowered):
        return "funeral"
    if re.search(r"\b(baptism|baptisms|baptismal)\b", lowered):
        return "baptism"
    if re.search(r"\b(meeting|rehearsal|preparation|formation|workshop)\b", lowered):
        return "meeting"
    if re.search(r"\bmass(?:es)?\b", lowered):
        return "mass"
    if re.search(
        r"\b(?:sacred\s+heart|clear\s+island\s+waters|st\.?\s+vincent(?:'s|s)?|"
        r"saint\s+vincent(?:'s|s)?|surfers|stella\s+maris|broadbeach)\b"
        r"[^.\n]{0,100}\bfr\.?\b",
        lowered,
    ):
        return "mass"
    if re.search(r"\b(day off|holiday|holidays|away|on call|office|administration)\b", lowered):
        return "administration"
    if re.search(
        r"\b(liturgy|stations of the cross|adoration|benediction|service|sacrament|confirmation|communion)\b",
        lowered,
    ):
        return "liturgy"
    return "other"


def multicultural_subtype(text):
    lowered = text.lower()
    for subtype in ("hispanic", "maronite", "polish", "italian"):
        if re.search(rf"\b{subtype}\s+mass\b", lowered):
            return subtype
    return None


KNOWN_PRESIDERS = [
    (r"\bbradley\b", "Fr Bradley"),
    (r"\bpaul(?:\s+kelly)?\b", "Fr Paul"),
    (r"\bbernie(?:\s+gallagher)?\b", "Fr Bernie"),
    (r"\banthony\b", "Fr Anthony"),
    (r"\bjohn\s+maher\b|\bmaher\b|\bjohn\b", "Fr John Maher"),
    (r"\bwarren(?:\s+kinne)?\b", "Fr Warren"),
    (r"\bjoshua\s+nash(?:\s+omi)?\b", "Fr Joshua Nash OMI"),
    (r"\bdamian\b|\bdamien\b", "Fr Damian"),
    (r"\balbert\b", "Fr Albert"),
    (r"\bfadi\b", "Fr Fadi"),
    (r"\bzac\b", "Fr Zac"),
    (r"\bandrew\s+grace\b", "Fr Andrew Grace"),
    (r"\bjerzy(?:\s+prucnal)?\b", "Fr Jerzy"),
    (r"\bsyrilus\s+madin\b", "Fr Syrilus Madin"),
    (r"\bluis\s+antonio\s+diaz(?:\s+lamus)?\b", "Fr Luis Antonio Diaz Lamus"),
]

MULTICULTURAL_PRESIDER_FALLBACKS = {
    "polish": "Fr Jerzy",
    "hispanic": "Fr Luis Antonio Diaz Lamus",
    "italian": "Fr Luis Antonio Diaz Lamus",
    "maronite": "Fr Fadi Salame",
}


def extract_presiders(text):
    priest_contexts = [
        match.group(0)
        for match in re.finditer(
            r"(?:\bfr\.?\b|\bfather\b)[^.;\n]{0,180}",
            text,
            re.IGNORECASE,
        )
    ]
    context = " ".join(priest_contexts)
    found = []
    for pattern, normalized in KNOWN_PRESIDERS:
        if re.search(pattern, context, re.IGNORECASE) and normalized not in found:
            found.append(normalized)
    return found


def clean_text(value):
    if not value:
        return None
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip() or None


def iso_value(value, all_day):
    if all_day:
        return value.date().isoformat()
    return value.astimezone(BRISBANE).isoformat(timespec="seconds")


def normalized_record(event, occurrence_start, occurrence_end, all_day, source_id):
    title = first(event, "SUMMARY")[1] or "(Untitled event)"
    location = clean_text(first(event, "LOCATION")[1])
    description = clean_text(first(event, "DESCRIPTION")[1])
    combined = "\n".join(item for item in (title, location, description) if item)
    event_type = classify_event(combined)
    event_subtype = multicultural_subtype(combined) if event_type == "multicultural" else None
    presider_title = re.sub(
        r"\(\s*(?:fr\.?|father)\b[^)]*\baway\b[^)]*\)",
        "",
        title,
        flags=re.IGNORECASE,
    )
    presiders = extract_presiders(presider_title)
    if not presiders:
        presiders = extract_presiders(description or "")
    if not presiders and event_subtype in MULTICULTURAL_PRESIDER_FALLBACKS:
        presiders = [MULTICULTURAL_PRESIDER_FALLBACKS[event_subtype]]
    if (
        event_type == "confession"
        and occurrence_start.hour == 16
        and occurrence_start.minute == 0
        and occurrence_end > occurrence_start + timedelta(minutes=30)
    ):
        occurrence_end = occurrence_start + timedelta(minutes=30)
    church = normalize_church(combined)
    if re.search(r"\bhealing\s+mass\b", combined, re.IGNORECASE):
        church = "Sacred Heart"
    associated_devotions = (
        ["Adoration", "Benediction"]
        if re.search(r"\bfirst\s+saturday\s+mass\b", combined, re.IGNORECASE)
        else []
    )
    return {
        "start": iso_value(occurrence_start, all_day),
        "end": iso_value(occurrence_end, all_day),
        "all_day": all_day,
        "timezone": "Australia/Brisbane",
        "church": church,
        "event_type": event_type,
        "event_subtype": event_subtype,
        "associated_devotions": associated_devotions,
        "title": title,
        "presiders": presiders,
        "location": location,
        "description": description,
        "source_id": source_id,
    }


def build_records(calendar_text, window_start=None, window_end=None):
    if window_start is None or window_end is None:
        window_start, window_end = default_window()
    events = parse_ics_events(calendar_text)
    by_uid = defaultdict(list)
    for event in events:
        uid = first(event, "UID")[1]
        if uid:
            by_uid[uid].append(event)

    output = []
    for uid, grouped_events in by_uid.items():
        masters = [event for event in grouped_events if recurrence_key(event) is None]
        overrides = {
            recurrence_key(event): event
            for event in grouped_events
            if recurrence_key(event) is not None
        }

        for master in masters:
            status = first(master, "STATUS")[1].upper()
            if status == "CANCELLED":
                continue
            start, all_day = event_start(master)
            end = event_end(master, start, all_day)
            duration = end - start
            excluded = exdates(master)

            for occurrence_start in expand_recurrence(
                start, master, window_start, window_end, all_day
            ):
                if occurrence_start in excluded or occurrence_start in overrides:
                    continue
                source_id = f"{uid}#{occurrence_start.isoformat()}"
                output.append(
                    normalized_record(
                        master,
                        occurrence_start,
                        occurrence_start + duration,
                        all_day,
                        source_id,
                    )
                )

        for recurrence_id, override in overrides.items():
            status = first(override, "STATUS")[1].upper()
            if status == "CANCELLED":
                continue
            start, all_day = event_start(override)
            if not (window_start <= start < window_end):
                continue
            end = event_end(override, start, all_day)
            source_id = f"{uid}#{recurrence_id.isoformat()}"
            output.append(normalized_record(override, start, end, all_day, source_id))

    deduplicated = {}
    for record in output:
        key = (record["source_id"], record["start"])
        deduplicated[key] = record

    records = sorted(
        (
            record
            for record in deduplicated.values()
            if record["event_type"] != "administration"
        ),
        key=lambda record: (record["start"], record["end"], record["title"]),
    )
    return records


def fetch_calendar_text():
    request = urllib.request.Request(ICS_URL, headers={"User-Agent": "SPCP-Calendar/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def write_records(records, output_path=OUTPUT_PATH):
    output_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def main():
    window_start, window_end = default_window()
    records = build_records(fetch_calendar_text(), window_start, window_end)
    write_records(records)
    print(
        f"Wrote {len(records)} events from "
        f"{window_start.date()} to {window_end.date()} to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
