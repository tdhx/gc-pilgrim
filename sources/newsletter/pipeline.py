#!/usr/bin/env python3

import base64
import calendar
import hashlib
import html
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

from generators.churches import (
    church_names,
    normalize_church_name,
    resolve_church,
    resolve_location,
)


ROOT = Path(__file__).resolve().parents[2]
BRISBANE = ZoneInfo("Australia/Brisbane")
TIMEZONE = "Australia/Brisbane"
DEFAULT_MODEL = "gpt-5.5"
MIN_CONFIDENCE = 0.75
SERIES_FRESHNESS_DAYS = 90
COMMUNITY_CATEGORIES = (
    "faith-formation", "prayer", "social", "outreach", "wellbeing",
    "youth", "pilgrimage", "fundraising", "other",
)
WEEKDAYS = (
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
)
SURFERS_PARADISE_NEWSLETTER_URL = "https://news-parish.blogspot.com/"
BURLEIGH_NEWSLETTER_URL = (
    "https://burleighheadscatholic.com.au/parish-newsletter/"
)
SUPPORTED_PARISHES = ("surfers-paradise", "burleigh-heads")


@dataclass(frozen=True)
class NewsletterDocument:
    parish_id: str
    source_id: str
    title: str
    url: str
    download_url: str
    published_date: str


class NewsletterLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        self._href = dict(attrs).get("href")
        self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


class BloggerPostParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.posts = []
        self._post = None
        self._depth = 0
        self._capture_title = False
        self._capture_date = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if self._post is None and tag.lower() == "div" and "date-posts" in classes:
            self._post = {"title": [], "date": None, "links": []}
            self._depth = 1
            return
        if self._post is None:
            return
        if tag.lower() == "div":
            self._depth += 1
        if tag.lower() == "h3" and "post-title" in classes:
            self._capture_title = True
        if tag.lower() == "abbr" and "published" in classes:
            self._post["date"] = attributes.get("title")
            self._capture_date = True
        if tag.lower() == "a" and attributes.get("href"):
            self._post["links"].append(attributes["href"])

    def handle_data(self, data):
        if self._post is not None and self._capture_title:
            self._post["title"].append(data)

    def handle_endtag(self, tag):
        if self._post is None:
            return
        if tag.lower() == "h3":
            self._capture_title = False
        if tag.lower() == "abbr":
            self._capture_date = False
        if tag.lower() == "div":
            self._depth -= 1
            if self._depth == 0:
                self.posts.append(self._post)
                self._post = None


def fetch_bytes(url, headers=None):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GC-Pilgrim/1.0", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_text(url):
    return fetch_bytes(url).decode("utf-8")


def parse_document_date(value):
    normalized = re.sub(r"[_–—-]+", " ", value)
    match = re.search(
        r"\b(?:Sunday\s*,?\s*)?(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|"
        r"Oct|Nov|Dec)\s+(\d{2,4})\b",
        normalized,
        re.IGNORECASE,
    )
    if not match:
        return None
    parsed = datetime.strptime(
        f"{match.group(1)} {match.group(2)[:3]} {match.group(3)}",
        "%d %b %Y" if len(match.group(3)) == 4 else "%d %b %y",
    )
    return parsed.date().isoformat()


def discover_burleigh(html_text):
    parser = NewsletterLinkParser()
    parser.feed(html_text)
    documents = []
    for url, title in parser.links:
        if not url.lower().endswith(".pdf") or "newsletter" not in title.lower():
            continue
        published_date = parse_document_date(title)
        if not published_date:
            continue
        documents.append(NewsletterDocument(
            parish_id="burleigh-heads",
            source_id=url,
            title=title,
            url=url,
            download_url=url,
            published_date=published_date,
        ))
    if not documents:
        raise ValueError("Burleigh newsletter page contained no dated PDF links")
    return max(documents, key=lambda item: (item.published_date, item.title))


def drive_file_id(url):
    match = re.search(r"drive\.google\.com/file/d/([^/?#]+)", html.unescape(url))
    return match.group(1) if match else None


def discover_surfer_files(html_text):
    parser = BloggerPostParser()
    parser.feed(html_text)
    for post in parser.posts:
        file_id = next(
            (drive_file_id(url) for url in post["links"] if drive_file_id(url)),
            None,
        )
        if not file_id or not post["date"]:
            continue
        published_date = datetime.fromisoformat(post["date"]).date().isoformat()
        title = re.sub(r"\s+", " ", " ".join(post["title"])).strip()
        return NewsletterDocument(
            parish_id="surfers-paradise",
            source_id=file_id,
            title=title or f"SPCP newsletter {published_date}",
            url=f"https://drive.google.com/file/d/{file_id}/view",
            download_url=f"https://drive.google.com/uc?export=download&id={file_id}",
            published_date=published_date,
        )
    raise ValueError("Newsletter hub contained no dated post with a Drive PDF")


def discover_latest(parish_id, google_api_key=None):
    if parish_id == "burleigh-heads":
        return discover_burleigh(fetch_text(BURLEIGH_NEWSLETTER_URL))
    if parish_id == "surfers-paradise":
        return discover_surfer_files(fetch_text(SURFERS_PARADISE_NEWSLETTER_URL))
    raise ValueError(f"Unsupported newsletter parish: {parish_id}")


def extract_pdf_text(path, reader_factory=None):
    if reader_factory is None:
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise RuntimeError(
                "pypdf is required; install dependencies from requirements.txt"
            ) from error
        reader_factory = PdfReader
    reader = reader_factory(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(
        f"--- Page {index} ---\n{text}"
        for index, text in enumerate(pages, start=1)
        if text
    )


def text_quality(text):
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return {"usable": False, "reason": "empty", "readable_ratio": 0.0}
    readable = sum(character.isprintable() or character.isspace() for character in text)
    readable_ratio = readable / len(text)
    keywords = sum(
        bool(re.search(pattern, text, re.IGNORECASE))
        for pattern in (
            r"\bnewsletter\b",
            r"\b(?:mass|parish|community)\b",
            r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
            r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
        )
    )
    reason = None
    if len(compact) < 500:
        reason = "too-short"
    elif readable_ratio < 0.9:
        reason = "garbled"
    elif keywords < 2:
        reason = "missing-structure-signals"
    return {
        "usable": reason is None,
        "reason": reason,
        "characters": len(text),
        "readable_ratio": round(readable_ratio, 4),
        "structure_signals": keywords,
    }


EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "community_events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {"type": "string", "enum": ["add", "update", "cancel"]},
                    "existing_event_id": {"type": ["string", "null"]},
                    "title": {"type": "string"},
                    "date": {"type": ["string", "null"]},
                    "start_time": {"type": ["string", "null"]},
                    "end_time": {"type": ["string", "null"]},
                    "all_day": {"type": "boolean"},
                    "location": {"type": ["string", "null"]},
                    "series_title": {"type": ["string", "null"]},
                    "category": {
                        "type": "string",
                        "enum": list(COMMUNITY_CATEGORIES),
                    },
                    "description": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": "string"},
                    "ambiguity": {"type": ["string", "null"]},
                },
                "required": [
                    "action", "existing_event_id", "title", "date", "start_time",
                    "end_time", "all_day", "location", "series_title", "category",
                    "description", "confidence", "evidence", "ambiguity",
                ],
            },
        },
        "community_series": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {"type": "string", "enum": ["add", "update", "cancel"]},
                    "existing_series_id": {"type": ["string", "null"]},
                    "series_title": {"type": "string"},
                    "occurrence_title": {"type": ["string", "null"]},
                    "category": {
                        "type": "string",
                        "enum": list(COMMUNITY_CATEGORIES),
                    },
                    "frequency": {"type": "string", "enum": ["weekly", "monthly"]},
                    "interval": {"type": "integer", "minimum": 1, "maximum": 12},
                    "weekdays": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(WEEKDAYS)},
                    },
                    "ordinal": {
                        "type": ["integer", "null"],
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "start_date": {"type": ["string", "null"]},
                    "end_date": {"type": ["string", "null"]},
                    "start_time": {"type": ["string", "null"]},
                    "end_time": {"type": ["string", "null"]},
                    "location": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": "string"},
                    "ambiguity": {"type": ["string", "null"]},
                },
                "required": [
                    "action", "existing_series_id", "series_title",
                    "occurrence_title", "category", "frequency", "interval",
                    "weekdays", "ordinal", "start_date", "end_date",
                    "start_time", "end_time", "location", "description",
                    "confidence", "evidence", "ambiguity",
                ],
            },
        },
        "worship_observations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {"type": "string", "enum": ["active", "cancelled"]},
                    "event_type": {
                        "type": "string",
                        "enum": [
                            "adoration", "mass", "confession", "baptism",
                            "multicultural", "funeral", "liturgy", "novena",
                            "rosary", "wedding",
                        ],
                    },
                    "title": {"type": "string"},
                    "date": {"type": ["string", "null"]},
                    "start_time": {"type": ["string", "null"]},
                    "end_time": {"type": ["string", "null"]},
                    "church": {"type": ["string", "null"]},
                    "replaces_event_type": {
                        "type": ["string", "null"],
                        "enum": ["mass", None],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": "string"},
                    "ambiguity": {"type": ["string", "null"]},
                },
                "required": [
                    "action", "event_type", "title", "date", "start_time",
                    "end_time", "church", "replaces_event_type", "confidence",
                    "evidence", "ambiguity",
                ],
            },
        },
    },
    "required": ["community_events", "community_series", "worship_observations"],
}


SYSTEM_PROMPT = """You extract parish activities from a Catholic newsletter.
Return explicitly announced one-off events and recurring groups. Community events
include meetings, meals, fundraisers, faith formation, social events, volunteering,
youth, pilgrimages, yoga, exercise, bridge, craft, meditation and parish groups.
Put repeating activities such as every Tuesday, weekdays, or third Saturday in
community_series rather than inventing a single occurrence. Preserve a concise
series_title, use occurrence_title for session-specific wording, and choose the
closest controlled category. Worship
observations include Mass, reconciliation, adoration, rosary, liturgy and sacraments.
Do not invent dates or resolve genuine ambiguity. Use ISO dates and 24-hour HH:MM.
Use action update/cancel only when the newsletter explicitly corrects or cancels an
existing event. Set replaces_event_type to "mass" only when the newsletter explicitly
states that a liturgy replaces Mass or that there is no Mass in that slot. Otherwise
set it to null. A worship cancellation may omit start_time when date, church and
event type are explicit. Evidence must be a short exact excerpt from the supplied
document. Check activity-heading sections carefully so recurring parish life is not
omitted."""


def existing_events_prompt(records):
    future = [
        {
            "id": record.get("id"),
            "title": record["title"],
            "start": record["start"],
            "end": record["end"],
            "location": record.get("location"),
            "status": record.get("status", "active"),
        }
        for record in records
        if record["start"][:10] >= date.today().isoformat()
    ]
    return json.dumps(future, ensure_ascii=False, indent=2)


def openai_client():
    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError(
            "The OpenAI SDK is required; install dependencies from requirements.txt"
        ) from error
    return OpenAI()


def parse_with_openai(client, model, document, text, pdf_bytes=None):
    context = (
        f"Parish: {document.parish_id}\n"
        f"Newsletter publication date: {document.published_date}\n"
        f"Existing future community events:\n{text['existing']}\n\n"
    )
    if pdf_bytes is None:
        user_content = context + "Newsletter text:\n" + text["newsletter"]
    else:
        encoded = base64.b64encode(pdf_bytes).decode("ascii")
        user_content = [
            {
                "type": "input_file",
                "filename": Path(urllib.parse.urlparse(document.download_url).path).name
                or "newsletter.pdf",
                "file_data": f"data:application/pdf;base64,{encoded}",
            },
            {"type": "input_text", "text": context + "Extract the newsletter."},
        ]
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "parish_newsletter_events",
                "schema": EXTRACTION_SCHEMA,
                "strict": True,
            }
        },
    )
    return json.loads(response.output_text)


def normalize_title(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def infer_category(value):
    source = normalize_title(value or "")
    rules = (
        ("faith-formation", ("formation", "bible study", "scripture study", "catech")),
        ("prayer", ("prayer", "rosary", "meditation", "devotion")),
        ("wellbeing", ("yoga", "exercise", "fitness", "heart health")),
        ("youth", ("youth", "kids", "children")),
        ("pilgrimage", ("pilgrimage", "shrine", "excursion")),
        ("fundraising", ("fundrais", "appeal", "raffle")),
        ("outreach", ("outreach", "volunteer", "care concern", "st vincent de paul")),
        ("social", ("social", "morning tea", "bbq", "bridge", "craft", "luncheon")),
    )
    for category, needles in rules:
        if any(needle in source for needle in needles):
            return category
    return "other"


def normalize_church(value):
    return normalize_church_name(value)


def is_lay_led_liturgy(observation):
    source = " ".join([
        observation.get("title") or "",
        observation.get("evidence") or "",
    ])
    return bool(re.search(
        r"\b(?:lay[\s-]*led|liturgy\s+of\s+the\s+word|communion)\b",
        source,
        re.IGNORECASE,
    ))


def validate_date(value):
    return date.fromisoformat(value).isoformat()


def validate_time(value):
    return time.fromisoformat(value).strftime("%H:%M")


def event_times(candidate):
    event_date = validate_date(candidate["date"])
    if candidate["all_day"]:
        start = event_date
        end = (date.fromisoformat(event_date) + timedelta(days=1)).isoformat()
        return start, end, []
    start_time = validate_time(candidate["start_time"])
    start = datetime.combine(
        date.fromisoformat(event_date),
        time.fromisoformat(start_time),
        BRISBANE,
    )
    warnings = []
    if candidate.get("end_time"):
        end = datetime.combine(
            start.date(),
            time.fromisoformat(validate_time(candidate["end_time"])),
            BRISBANE,
        )
        if end <= start:
            end += timedelta(days=1)
    else:
        end = start + timedelta(hours=1)
        warnings.append("Missing end time; defaulted to one hour")
    return (
        start.isoformat(timespec="seconds"),
        end.isoformat(timespec="seconds"),
        warnings,
    )


def new_event_id(parish_id, candidate):
    identity = "\0".join([
        parish_id,
        normalize_title(candidate["title"]),
        candidate["date"] or "",
        candidate.get("location") or "",
    ])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def find_existing(candidate, records):
    requested = candidate.get("existing_event_id")
    if requested:
        return next((record for record in records if record.get("id") == requested), None)
    title = normalize_title(candidate["title"])
    candidate_date = candidate.get("date")
    matches = [
        record for record in records
        if normalize_title(record["title"]) == title
        and record["start"][:10] == candidate_date
    ]
    return matches[0] if len(matches) == 1 else None


def normalized_location(candidate, parish):
    value = candidate.get("location")
    if not parish:
        return {
            "location": value, "venue": value, "church_id": None,
            "church_name": None, "_resolution_status": "unmatched",
        }
    resolution = resolve_location(value, parish)
    church = resolution.get("church")
    return {
        "location": value,
        "venue": resolution.get("venue") or value,
        "church_id": church["id"] if church else None,
        "church_name": (
            church.get("calendar_name", church["name"]) if church else None
        ),
        "_resolution_status": resolution["status"],
    }


def reconcile_community(parish_id, existing, candidates, document, parish=None):
    records = [dict(record) for record in existing]
    decisions = []
    quarantined = []
    for candidate in candidates:
        reasons = []
        if candidate.get("confidence", 0) < MIN_CONFIDENCE:
            reasons.append("low-confidence")
        if candidate.get("ambiguity"):
            reasons.append("ambiguous")
        if not candidate.get("date"):
            reasons.append("missing-date")
        if not candidate.get("all_day") and not candidate.get("start_time"):
            reasons.append("missing-start-time")
        if reasons:
            quarantined.append({"candidate": candidate, "reasons": reasons})
            continue
        try:
            start, end, warnings = event_times(candidate)
        except ValueError:
            quarantined.append({"candidate": candidate, "reasons": ["invalid-date-or-time"]})
            continue

        match = find_existing(candidate, records)
        action = candidate["action"]
        if action in {"update", "cancel"} and match is None:
            quarantined.append({"candidate": candidate, "reasons": ["existing-event-not-found"]})
            continue
        if action == "cancel":
            match["status"] = "cancelled"
            match["last_newsletter_id"] = document.source_id
            decisions.append({"action": "cancelled", "id": match["id"], "warnings": warnings})
            continue

        event_id = match["id"] if match else new_event_id(parish_id, candidate)
        source_id = (
            match.get("source_id")
            if match
            else f"newsletter:{parish_id}:event:{event_id}"
        )
        location = normalized_location(candidate, parish)
        if location.pop("_resolution_status") == "ambiguous":
            quarantined.append({
                "candidate": candidate,
                "reasons": ["ambiguous-location"],
            })
            continue
        normalized = {
            "id": event_id,
            "event_type": "community",
            "title": candidate["title"].strip(),
            "start": start,
            "end": end,
            "status": "modified" if match else "active",
            "all_day": candidate["all_day"],
            "timezone": TIMEZONE,
            **location,
            "series_title": candidate.get("series_title"),
            "category": candidate.get("category") or infer_category(
                " ".join([
                    candidate.get("title") or "",
                    candidate.get("description") or "",
                ])
            ),
            "description": candidate.get("description"),
            "source_id": source_id,
            "source": f"{parish_id} parish newsletter",
            "last_newsletter_id": document.source_id,
        }
        if match:
            records[records.index(match)] = normalized
            decision = "deduplicated" if action == "add" else "updated"
        else:
            duplicate = next(
                (record for record in records if record.get("id") == event_id),
                None,
            )
            if duplicate:
                records[records.index(duplicate)] = normalized
                decision = "deduplicated"
            else:
                records.append(normalized)
                decision = "added"
        decisions.append({"action": decision, "id": event_id, "warnings": warnings})
    records.sort(key=lambda item: (item["start"], item["end"], item["id"]))
    return records, decisions, quarantined


def new_series_id(parish_id, candidate):
    identity = "\0".join([
        parish_id,
        normalize_title(candidate["series_title"]),
        candidate.get("location") or "",
        candidate.get("start_time") or "",
    ])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def reconcile_series(parish_id, existing, candidates, document, parish=None):
    records = [dict(record) for record in existing]
    decisions = []
    quarantined = []
    for candidate in candidates:
        reasons = []
        if candidate.get("confidence", 0) < MIN_CONFIDENCE:
            reasons.append("low-confidence")
        if not candidate.get("start_time"):
            reasons.append("missing-start-time")
        if not candidate.get("weekdays"):
            reasons.append("missing-weekday")
        if candidate.get("frequency") == "monthly" and not candidate.get("ordinal"):
            reasons.append("missing-monthly-ordinal")
        if reasons:
            quarantined.append({"candidate": candidate, "reasons": reasons})
            continue
        try:
            start_time = validate_time(candidate["start_time"])
            end_time = (
                validate_time(candidate["end_time"])
                if candidate.get("end_time") else None
            )
            start_date = (
                validate_date(candidate["start_date"])
                if candidate.get("start_date") else document.published_date
            )
            end_date = (
                validate_date(candidate["end_date"])
                if candidate.get("end_date") else None
            )
        except ValueError:
            quarantined.append({"candidate": candidate, "reasons": ["invalid-date-or-time"]})
            continue

        location = normalized_location(candidate, parish)
        if location.pop("_resolution_status") == "ambiguous":
            quarantined.append({
                "candidate": candidate,
                "reasons": ["ambiguous-location"],
            })
            continue
        proposed_id = candidate.get("existing_series_id") or new_series_id(
            parish_id, candidate
        )
        match = next(
            (record for record in records if record["series_id"] == proposed_id),
            None,
        )
        if match is None and not candidate.get("existing_series_id"):
            signature_matches = [
                record for record in records
                if record.get("frequency") == candidate["frequency"]
                and record.get("start_time") == start_time
                and record.get("ordinal") == candidate.get("ordinal")
                and set(record.get("weekdays", [])) == set(candidate["weekdays"])
                and (
                    (
                        location.get("church_id")
                        and record.get("church_id") == location["church_id"]
                        and normalize_title(record.get("venue") or "")
                        == normalize_title(location.get("venue") or "")
                    )
                    or (
                        not location.get("church_id")
                        and normalize_title(record.get("location") or "")
                        == normalize_title(location.get("location") or "")
                    )
                )
            ]
            match = signature_matches[0] if len(signature_matches) == 1 else None
        series_id = match["series_id"] if match else proposed_id
        if candidate["action"] in {"update", "cancel"} and match is None:
            quarantined.append({
                "candidate": candidate,
                "reasons": ["existing-series-not-found"],
            })
            continue
        if candidate["action"] == "cancel":
            match["status"] = "cancelled"
            match["last_seen"] = document.published_date
            decisions.append({"action": "cancelled-series", "id": series_id})
            continue

        normalized = {
            "series_id": series_id,
            "series_title": candidate["series_title"].strip(),
            "occurrence_title": (
                candidate.get("occurrence_title")
                or candidate["series_title"]
            ),
            "category": candidate.get("category") or infer_category(
                " ".join([
                    candidate.get("series_title") or "",
                    candidate.get("description") or "",
                ])
            ),
            "frequency": candidate["frequency"],
            "interval": candidate.get("interval", 1),
            "weekdays": candidate["weekdays"],
            "ordinal": candidate.get("ordinal"),
            "start_date": start_date,
            "end_date": end_date,
            "start_time": start_time,
            "end_time": end_time,
            **location,
            "description": candidate.get("description"),
            "status": "active",
            "source": f"{parish_id} parish newsletter",
            "source_id": f"newsletter:{parish_id}:series:{series_id}",
            "last_seen": document.published_date,
            "last_newsletter_id": document.source_id,
        }
        if match:
            records[records.index(match)] = normalized
            action = "updated-series"
        else:
            records.append(normalized)
            action = "added-series"
        decisions.append({"action": action, "id": series_id})
    records.sort(key=lambda item: item["series_id"])
    return records, decisions, quarantined


def add_months(value, amount):
    month_index = value.month - 1 + amount
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def series_dates(series, window_start, window_end):
    first = max(date.fromisoformat(series["start_date"]), window_start)
    last = min(
        date.fromisoformat(series["end_date"]) if series.get("end_date") else window_end,
        window_end,
    )
    weekdays = {WEEKDAYS.index(value) for value in series["weekdays"]}
    dates = []
    cursor = first
    while cursor <= last:
        if series["frequency"] == "weekly":
            anchor = date.fromisoformat(series["start_date"])
            week_index = (cursor - anchor).days // 7
            include = cursor.weekday() in weekdays and week_index % series["interval"] == 0
        else:
            include = False
            if cursor.weekday() in weekdays:
                ordinal = (cursor.day - 1) // 7 + 1
                anchor = date.fromisoformat(series["start_date"])
                month_index = (cursor.year - anchor.year) * 12 + cursor.month - anchor.month
                include = (
                    ordinal == series["ordinal"]
                    and month_index % series["interval"] == 0
                )
        if include:
            dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def expand_series(records, window_start=None, window_end=None, today=None):
    today = today or datetime.now(BRISBANE).date()
    window_start = window_start or today.replace(day=1)
    window_end = window_end or add_months(window_start, 3) - timedelta(days=1)
    events = []
    for series in records:
        if series.get("status") == "cancelled":
            continue
        last_seen = date.fromisoformat(series["last_seen"])
        if today > last_seen + timedelta(days=SERIES_FRESHNESS_DAYS):
            continue
        for occurrence_date in series_dates(series, window_start, window_end):
            start = datetime.combine(
                occurrence_date,
                time.fromisoformat(series["start_time"]),
                BRISBANE,
            )
            if series.get("end_time"):
                end = datetime.combine(
                    occurrence_date,
                    time.fromisoformat(series["end_time"]),
                    BRISBANE,
                )
                if end <= start:
                    end += timedelta(days=1)
            else:
                end = start + timedelta(hours=1)
            event_id = hashlib.sha256(
                f'{series["series_id"]}\0{occurrence_date.isoformat()}'.encode("utf-8")
            ).hexdigest()[:24]
            events.append({
                "id": event_id,
                "event_type": "community",
                "title": series["occurrence_title"],
                "series_id": series["series_id"],
                "series_title": series["series_title"],
                "category": series["category"],
                "start": start.isoformat(timespec="seconds"),
                "end": end.isoformat(timespec="seconds"),
                "status": "active",
                "all_day": False,
                "timezone": TIMEZONE,
                "location": series.get("location"),
                "venue": series.get("venue"),
                "church_id": series.get("church_id"),
                "church_name": series.get("church_name"),
                "description": series.get("description"),
                "source_id": (
                    f'{series["source_id"]}:occurrence:{occurrence_date.isoformat()}'
                ),
                "source": series["source"],
                "last_newsletter_id": series["last_newsletter_id"],
                "recurrence": {
                    "frequency": series["frequency"],
                    "interval": series["interval"],
                    "weekdays": series["weekdays"],
                    "ordinal": series.get("ordinal"),
                    "last_seen": series["last_seen"],
                },
            })
    return sorted(events, key=lambda item: (item["start"], item["id"]))


def divergence_details(observation, services, parish=None):
    reasons = []
    if (
        observation.get("confidence", 0) < MIN_CONFIDENCE
    ):
        reasons.append("confidence below 0.75")
    if observation.get("ambiguity") and observation.get("action") != "cancelled":
        reasons.append(f'ambiguous: {observation["ambiguity"]}')
    if not observation.get("date"):
        reasons.append("missing date")
    if not observation.get("start_time") and observation.get("action") != "cancelled":
        reasons.append("missing start time")
    if reasons:
        return {
            "classification": "quarantined",
            "matched_source_id": None,
            "classification_reason": "; ".join(reasons),
            "schedule_candidates": [],
            "normalized_church": normalize_church(observation.get("church")),
            "resolved_church_id": None,
            "resolved_church_name": None,
            "church_resolution": "unmatched",
            "publication_decision": "audit-only",
        }

    target_date = observation["date"]
    target_time = (
        validate_time(observation["start_time"])
        if observation.get("start_time") else None
    )
    target_church = normalize_church(observation.get("church") or "")
    resolution = resolve_church(observation.get("church"), parish) if parish else None
    if resolution and resolution["status"] != "matched":
        return {
            "classification": "quarantined",
            "matched_source_id": None,
            "classification_reason": (
                f'Church name is {resolution["status"]}: '
                f'{observation.get("church") or "(missing)"}'
            ),
            "schedule_candidates": [],
            "normalized_church": resolution["normalized"],
            "resolved_church_id": None,
            "resolved_church_name": None,
            "church_resolution": resolution["status"],
            "church_candidates": resolution["candidates"],
            "publication_decision": "audit-only",
        }
    resolved_church = resolution["church"] if resolution else None
    resolved_names = {
        normalize_church(name)
        for name in church_names(resolved_church or {})
        if name
    }
    comparison_type = observation.get("replaces_event_type") or observation["event_type"]
    same_type_date = [
        service for service in services
        if service["event_type"] == comparison_type
        and service["start"][:10] == target_date
    ]
    candidates = [
        service for service in same_type_date
        if (
            not target_church
            or (
                resolved_church
                and (
                    service.get("church_id") == resolved_church["id"]
                    or normalize_church(service.get("church") or "") in resolved_names
                )
            )
            or normalize_church(service.get("church") or "") == target_church
        )
    ]
    exact = (
        next(
            (service for service in candidates if service["start"][11:16] == target_time),
            None,
        )
        if target_time else None
    )
    unique_untimed = (
        candidates[0]
        if observation["action"] == "cancelled"
        and target_time is None
        and len(candidates) == 1
        else None
    )
    matched_service = exact or unique_untimed
    comparison_candidates = candidates or same_type_date
    summaries = [
        {
            "source_id": service.get("source_id"),
            "title": service.get("title"),
            "date": service["start"][:10],
            "start_time": service["start"][11:16],
            "end_time": service.get("end", "")[11:16] or None,
            "church": service.get("church"),
            "church_id": service.get("church_id"),
            "event_type": service["event_type"],
        }
        for service in comparison_candidates
    ]
    if (
        matched_service
        and observation["event_type"] == "liturgy"
        and observation.get("replaces_event_type")
    ):
        classification = "replacement"
        reason = (
            f'Explicit {comparison_type} replacement matches date, time, '
            "and normalized church"
        )
        publication_decision = "cancel-and-add-replacement"
    elif matched_service and observation["action"] == "cancelled":
        classification = "cancelled"
        reason = (
            "Exact schedule match; newsletter explicitly marks it cancelled"
            if target_time
            else "Unique match on date, type, and normalized church; newsletter explicitly marks it cancelled"
        )
        publication_decision = "cancel-matched-service"
    elif exact:
        classification = "matched"
        reason = "Exact match on date, type, time, and normalized church"
        publication_decision = "no-change"
    elif candidates and observation["action"] == "cancelled":
        classification = "quarantined"
        reason = (
            "Cancellation time does not exactly match the scheduled service"
            if target_time
            else "Multiple scheduled services match the untimed cancellation"
        )
        publication_decision = "audit-only"
    elif candidates:
        classification = "changed"
        reason = "Same date, type, and normalized church, but the time differs"
        publication_decision = "modify-matched-service"
    elif same_type_date:
        classification = "unmatched"
        reason = "Same date and type exist, but no normalized church match"
        publication_decision = "audit-only"
    else:
        classification = "unmatched"
        reason = "No scheduled service has the same date and event type"
        publication_decision = (
            "add-worship"
            if (
                observation["action"] == "active"
                and resolved_church
                and target_time
            )
            else "audit-only"
        )
    return {
        "classification": classification,
        "matched_source_id": matched_service.get("source_id") if matched_service else (
            candidates[0].get("source_id") if candidates else None
        ),
        "classification_reason": reason,
        "schedule_candidates": summaries,
        "normalized_church": (
            resolution["normalized"] if resolution else target_church
        ),
        "resolved_church_id": (
            resolved_church["id"] if resolved_church else None
        ),
        "resolved_church_name": (
            resolved_church.get("calendar_name", resolved_church["name"])
            if resolved_church else observation.get("church")
        ),
        "church_resolution": resolution["status"] if resolution else (
            "matched" if target_church else "unmatched"
        ),
        "publication_decision": publication_decision,
    }


def classify_divergence(observation, services, parish=None):
    details = divergence_details(observation, services, parish)
    return details["classification"], details["matched_source_id"]


def reconcile_divergences(existing, observations, services, document, parish=None):
    existing = [
        item for item in existing
        if item.get("newsletter_id") != document.source_id
    ]
    by_key = {
        (
            item["newsletter_id"],
            item["event_type"],
            item.get("date"),
            item.get("start_time"),
            item.get("church"),
        ): item
        for item in existing
    }
    for observation in observations:
        try:
            details = divergence_details(observation, services, parish)
        except ValueError:
            details = {
                "classification": "quarantined",
                "matched_source_id": None,
                "classification_reason": "Invalid date or time",
                "schedule_candidates": [],
                "normalized_church": normalize_church(observation.get("church")),
                "resolved_church_id": None,
                "resolved_church_name": None,
                "church_resolution": "unmatched",
                "publication_decision": "audit-only",
            }
        item = {
            "newsletter_id": document.source_id,
            "newsletter_url": document.url,
            **observation,
            **details,
        }
        key = (
            item["newsletter_id"],
            item["event_type"],
            item.get("date"),
            item.get("start_time"),
            item.get("church"),
        )
        by_key[key] = item
    return sorted(
        by_key.values(),
        key=lambda item: (
            item.get("date") or "",
            item.get("start_time") or "",
            item["event_type"],
        ),
    )


def read_json(path, default):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def read_json_lines(path):
    path = Path(path)
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_json(path, value):
    atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def write_json_lines(path, records):
    atomic_write(
        path,
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                for record in records),
    )


def state_dir(parish_id, root=ROOT):
    return Path(root) / "raw" / parish_id / "newsletter"


def load_oneoff_community_records(parish_id, root=ROOT):
    return read_json_lines(state_dir(parish_id, root) / "community.jsonl")


def load_community_records(parish_id, root=ROOT):
    directory = state_dir(parish_id, root)
    return (
        load_oneoff_community_records(parish_id, root)
        + expand_series(read_json_lines(directory / "series.jsonl"))
    )


def likely_activity_headings(text):
    keywords = re.compile(
        r"\b(?:group|yoga|exercise|bridge|craft|meditation|formation|study|"
        r"pilgrimage|excursion|rosary|adoration|appeal|youth|social|class)\b",
        re.IGNORECASE,
    )
    headings = []
    for line in text.splitlines():
        compact = re.sub(r"\s+", " ", line).strip(" -–—:")
        if (
            5 <= len(compact) <= 100
            and keywords.search(compact)
            and (
                compact.upper() == compact
                or compact.endswith("-")
                or " GROUP" in compact.upper()
            )
        ):
            headings.append(compact)
    return list(dict.fromkeys(headings))


def completeness_audit(text, extracted):
    accepted = [
        " ".join([
            item.get("title") or item.get("series_title") or "",
            item.get("evidence") or "",
        ]).lower()
        for key in ("community_events", "community_series", "worship_observations")
        for item in extracted.get(key, [])
    ]
    missing = [
        heading for heading in likely_activity_headings(text)
        if not any(
            all(word in candidate for word in normalize_title(heading).split()[:3])
            for candidate in accepted
        )
    ]
    return {
        "likely_activity_headings": likely_activity_headings(text),
        "unmatched_activity_headings": missing,
    }


def process_latest(
    parish_id,
    services,
    model=None,
    root=ROOT,
    client=None,
    document=None,
    pdf_bytes=None,
    parish=None,
    force=False,
):
    model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    directory = state_dir(parish_id, root)
    state_path = directory / "state.json"
    state = read_json(state_path, {})
    document = document or discover_latest(parish_id)
    if not force and state.get("latest_document_id") == document.source_id:
        audit_path = Path(root) / state["latest_audit"]
        audit = read_json(audit_path, {})
        extracted = audit.get("extraction", {})
        observations = extracted.get("worship_observations", [])
        divergence_path = directory / "service-divergences.jsonl"
        divergences = reconcile_divergences(
            read_json_lines(divergence_path),
            observations,
            services,
            document,
            parish,
        )
        write_json_lines(divergence_path, divergences)
        return {
            "status": "unchanged",
            "document": asdict(document),
            "divergences_refreshed": len(observations),
        }

    pdf_bytes = pdf_bytes if pdf_bytes is not None else fetch_bytes(document.download_url)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temporary:
        temporary.write(pdf_bytes)
        temporary.flush()
        newsletter_text = extract_pdf_text(temporary.name)
    quality = text_quality(newsletter_text)
    existing = load_oneoff_community_records(parish_id, root)
    client = client or openai_client()
    prompt_text = {
        "existing": existing_events_prompt(existing),
        "newsletter": newsletter_text,
    }
    if quality["usable"]:
        parser_mode = "text"
        extracted = parse_with_openai(client, model, document, prompt_text)
    else:
        parser_mode = "pdf-fallback"
        extracted = parse_with_openai(
            client, model, document, prompt_text, pdf_bytes=pdf_bytes
        )

    extracted.setdefault("community_series", [])
    community, decisions, quarantined = reconcile_community(
        parish_id,
        existing,
        extracted["community_events"],
        document,
        parish,
    )
    series_path = directory / "series.jsonl"
    series, series_decisions, series_quarantined = reconcile_series(
        parish_id,
        read_json_lines(series_path),
        extracted["community_series"],
        document,
        parish,
    )
    divergence_path = directory / "service-divergences.jsonl"
    divergences = reconcile_divergences(
        read_json_lines(divergence_path),
        extracted["worship_observations"],
        services,
        document,
        parish,
    )
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", document.source_id).strip("-")
    text_path = directory / "extracted" / f"{safe_id}.txt"
    audit_path = directory / "audits" / f"{safe_id}.json"
    audit = {
        "schema_version": 1,
        "processed_at": datetime.now(BRISBANE).isoformat(timespec="seconds"),
        "document": asdict(document),
        "sha256": digest,
        "parser_mode": parser_mode,
        "text_quality": quality,
        "model": model,
        "extraction": extracted,
        "decisions": decisions,
        "series_decisions": series_decisions,
        "quarantined": quarantined,
        "series_quarantined": series_quarantined,
        "completeness": completeness_audit(newsletter_text, extracted),
    }
    atomic_write(text_path, newsletter_text + ("\n" if newsletter_text else ""))
    write_json(audit_path, audit)
    write_json_lines(directory / "community.jsonl", community)
    write_json_lines(series_path, series)
    write_json_lines(divergence_path, divergences)
    write_json(state_path, {
        "latest_document_id": document.source_id,
        "latest_document_date": document.published_date,
        "latest_document_sha256": digest,
        "latest_audit": str(audit_path.relative_to(Path(root))),
    })
    return {
        "status": "processed",
        "document": asdict(document),
        "parser_mode": parser_mode,
        "community_events": len(community),
        "community_series": len(series),
        "decisions": decisions,
        "quarantined": len(quarantined) + len(series_quarantined),
        "divergences": len(divergences),
    }
