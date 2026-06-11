from generators.io import write_json
from validators.feeds import validate_liturgical


def normalized_record(record):
    return {
        "observance": record["observance"],
        "rank": record.get("rank"),
        "season": record["season"],
        "season_week": record.get("season_week"),
        "psalm_week": record.get("psalm_week"),
        "colour": record.get("liturgical_colour") or record.get("colour"),
        "alternatives": record.get("alternatives", []),
        "source_url": record.get("source_url"),
    }


def annual_feed(records, generated_at, year):
    feed = {
        "schema_version": 1,
        "generated_at": generated_at,
        "year": year,
        "dates": {
            record["date"]: normalized_record(record)
            for record in records
        },
    }
    return validate_liturgical(feed, year)


def aggregate_feed(annual_feeds, generated_at):
    dates = {}
    for feed in annual_feeds:
        dates.update(feed["dates"])
    return validate_liturgical({
        "schema_version": 1,
        "generated_at": generated_at,
        "years": [feed["year"] for feed in annual_feeds],
        "dates": dates,
    })
