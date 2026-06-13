import re


def normalize_church_name(value):
    normalized = re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
    normalized = re.sub(r"\b(?:roman\s+)?catholic\b", " ", normalized)
    normalized = re.sub(r"\bchurch\b", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def church_names(church):
    return [
        church.get("name"),
        church.get("calendar_name"),
        *(church.get("aliases") or []),
    ]


def venue_names(venue):
    return [venue.get("name"), *(venue.get("aliases") or [])]


def resolve_church(value, parish):
    normalized = normalize_church_name(value)
    if not normalized:
        return {
            "status": "unmatched",
            "normalized": normalized,
            "church": None,
            "candidates": [],
        }
    candidates = []
    for church in parish.get("churches", []):
        names = {
            normalize_church_name(name)
            for name in church_names(church)
            if name
        }
        if normalized in names or any(
            name and re.search(rf"\b{re.escape(name)}\b", normalized)
            for name in names
        ):
            candidates.append(church)
    return {
        "status": "matched" if len(candidates) == 1 else (
            "ambiguous" if candidates else "unmatched"
        ),
        "normalized": normalized,
        "church": candidates[0] if len(candidates) == 1 else None,
        "candidates": [
            {
                "id": church["id"],
                "name": church.get("calendar_name", church["name"]),
            }
            for church in candidates
        ],
    }


def resolve_location(value, parish):
    normalized = normalize_church_name(value)
    candidates = []
    for church in parish.get("churches", []):
        for venue in church.get("venues", []):
            names = [
                normalize_church_name(name)
                for name in venue_names(venue)
                if name
            ]
            if any(name and name in normalized for name in names):
                candidates.append((church, venue))
    unique = {
        (church["id"], venue["name"]): (church, venue)
        for church, venue in candidates
    }
    matches = list(unique.values())
    if len(matches) == 1:
        church, venue = matches[0]
        return {
            "status": "matched",
            "normalized": normalized,
            "church": church,
            "venue": venue["name"],
            "candidates": [{
                "id": church["id"],
                "name": church.get("calendar_name", church["name"]),
                "venue": venue["name"],
            }],
        }
    direct = resolve_church(value, parish)
    if direct["status"] == "matched":
        church = direct["church"]
        return {
            **direct,
            "venue": church.get("calendar_name", church["name"]),
        }
    return {
        "status": "ambiguous" if matches else "unmatched",
        "normalized": normalized,
        "church": None,
        "venue": value,
        "candidates": [
            {
                "id": church["id"],
                "name": church.get("calendar_name", church["name"]),
                "venue": venue["name"],
            }
            for church, venue in matches
        ],
    }
