import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from generators.churches import resolve_church
from generators.service_rules import stable_id
from sources.newsletter.pipeline import divergence_details


BRISBANE = ZoneInfo("Australia/Brisbane")
MIN_CONFIDENCE = 0.75


def observation_source_id(parish_id, observation):
    identity = "\0".join([
        parish_id,
        observation.get("newsletter_id") or "",
        observation.get("event_type") or "",
        observation.get("date") or "",
        observation.get("start_time") or "",
        observation.get("church") or "",
    ])
    return f"newsletter:{parish_id}:worship:{hashlib.sha256(identity.encode()).hexdigest()[:24]}"


def observation_times(observation):
    start = datetime.fromisoformat(
        f'{observation["date"]}T{observation["start_time"]}:00'
    ).replace(tzinfo=BRISBANE)
    if observation.get("end_time"):
        end = datetime.fromisoformat(
            f'{observation["date"]}T{observation["end_time"]}:00'
        ).replace(tzinfo=BRISBANE)
        if end <= start:
            end += timedelta(days=1)
    else:
        end = start + timedelta(hours=1)
    return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")


def added_worship(parish_id, observation, church, generated_at):
    start, end = observation_times(observation)
    source_id = observation_source_id(parish_id, observation)
    event_type = observation["event_type"]
    title = observation.get("title") or event_type.title()
    record = {
        "source_id": source_id,
        "title": title,
        "event_type": event_type,
        "service_name": title,
        "presiders": [],
        "associated_devotions": [],
        "start": start,
        "end": end,
        "all_day": False,
        "timezone": "Australia/Brisbane",
        "location": church.get("calendar_name", church["name"]),
        "description": observation.get("evidence"),
        "liturgical_date": (
            observation["date"] if event_type in {"mass", "multicultural"} else None
        ),
        "church_id": church["id"],
        "status": "active",
        "source": "Parish newsletter",
        "last_updated": generated_at,
    }
    record["id"] = stable_id(record)
    return record


def apply_newsletter_overlays(services, observations, parish, generated_at):
    result = [dict(service) for service in services]
    church_names = {
        church["id"]: church.get("calendar_name", church["name"])
        for church in parish["churches"]
    }

    for observation in sorted(
        observations,
        key=lambda item: (
            item.get("date") or "",
            item.get("start_time") or "",
            item.get("newsletter_id") or "",
            item.get("event_type") or "",
        ),
    ):
        if (
            observation.get("confidence", 0) < MIN_CONFIDENCE
            or observation.get("ambiguity")
            or not observation.get("date")
            or (
                observation.get("action") != "cancelled"
                and not observation.get("start_time")
            )
        ):
            continue
        resolution = resolve_church(observation.get("church"), parish)
        if resolution["status"] != "matched":
            continue
        comparable = [
            {
                **service,
                "church": church_names.get(service.get("church_id")),
            }
            for service in result
        ]
        details = divergence_details(observation, comparable, parish)
        decision = details["publication_decision"]
        matched = next(
            (
                service for service in result
                if service.get("source_id") == details.get("matched_source_id")
            ),
            None,
        )

        if decision == "cancel-matched-service" and matched:
            matched["status"] = "cancelled"
        elif decision == "modify-matched-service" and matched:
            start, end = observation_times(observation)
            matched["start"] = start
            matched["end"] = end
            matched["status"] = "modified"
        elif decision == "cancel-and-add-replacement" and matched:
            matched["status"] = "cancelled"
            replacement = added_worship(
                parish["id"], {**observation, **details}, resolution["church"], generated_at
            )
            if not any(service["id"] == replacement["id"] for service in result):
                result.append(replacement)
        elif decision == "add-worship":
            addition = added_worship(
                parish["id"], {**observation, **details}, resolution["church"], generated_at
            )
            if not any(service["id"] == addition["id"] for service in result):
                result.append(addition)

    return sorted(result, key=lambda item: (item["start"], item["end"], item["id"]))
