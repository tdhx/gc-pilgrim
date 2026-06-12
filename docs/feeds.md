# Feed Contracts

All public feeds use `schema_version: 1`. JSON is generated deterministically
with sorted keys and a trailing newline.

## Registry

Path: `feeds/v1/registry.json`

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Contract version |
| `default_parish_id` | string | Parish selected when the query parameter is absent or invalid |
| `default_view_id` | string | Calendar view selected for a new visitor |
| `aggregate_view` | object | Optional virtual view with stable `id` and display `name` |
| `parishes` | string array | Discoverable parish IDs |

The default parish ID must occur in `parishes`. The default view may identify
either a parish or the aggregate view. Parish IDs must be unique, and an
aggregate view ID must not conflict with a parish ID.

The aggregate view is virtual: it has no parish feed directory. At runtime the
web app reads all registered parish feeds and combines their events.

## Parish

Path: `feeds/v1/parishes/<parish-id>/parish.json`

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Contract version |
| `id` | string | Stable parish identifier |
| `name` | string | Display name |
| `churches` | array | Church definitions; may be empty |

Each church requires a unique `id` and a `name`.

Optional parish fields include:

- `contact.phone`, `contact.email`, `contact.website`
- `office.address`, `office.hours`
- `clergy`
- `branding.logo`, `branding.theme`, `branding.tagline`
- church `address`, `calendar_name`, and `is_primary_site`

The UI hides absent optional contact and office values.

## Services

Path: `feeds/v1/parishes/<parish-id>/services.json`

Envelope fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | Contract version |
| `generated_at` | yes | ISO 8601 generation timestamp |
| `timezone` | yes | Feed timezone |
| `coverage.start` | yes | Inclusive first supported date |
| `coverage.end` | yes | Inclusive last supported date |
| `sources` | no | Source name, URL, and freshness metadata |
| `warnings` | no | Non-fatal build warnings |
| `services` | yes | Chronologically sorted service records |

Every service requires:

```json
{
  "id": "stable-id",
  "event_type": "mass",
  "start": "2026-06-14T09:00:00+10:00",
  "end": "2026-06-14T10:00:00+10:00",
  "status": "active"
}
```

Supported status values are `active`, `cancelled`, and `modified`.

Common optional fields:

- `church_id`
- `service_name`
- `title`
- `event_subtype`
- `presiders`
- `associated_devotions`
- `liturgical_date`
- `source`, `source_id`, `last_updated`
- `all_day`, `timezone`
- `location`, `description`
- `notes`, `livestream_url`, `language`

When parish metadata is supplied to the validator, a non-null `church_id` must
reference a declared church.

## Community

Path: `feeds/v1/parishes/<parish-id>/community.json`

The envelope is the same shape as the services envelope, with records under
`events`.

Every community event requires:

```json
{
  "id": "stable-id",
  "title": "Morning Tea",
  "start": "2026-06-14T10:00:00+10:00",
  "end": "2026-06-14T11:00:00+10:00",
  "status": "active"
}
```

Optional fields include `location`, `description`, `contact`, `source`,
`source_id`, `last_updated`, `all_day`, and `timezone`.

At runtime, community events receive `event_type: "community"` and enter the
same display model as services.

## Liturgical

Aggregate path: `feeds/v1/liturgical.json`

Annual path: `feeds/v1/liturgical/<year>.json`

The aggregate feed contains `schema_version`, `generated_at`, `years`, and a
date-indexed `dates` object. Annual feeds additionally contain `year`.

Each date requires `observance` and `season`:

```json
{
  "dates": {
    "2026-06-14": {
      "observance": "11th Sunday in Ordinary Time",
      "rank": "Sunday",
      "season": "Ordinary Time",
      "season_week": 11,
      "psalm_week": 3,
      "colour": "green",
      "alternatives": [],
      "source_url": "https://example.test"
    }
  }
}
```

No parish-specific information belongs in this feed.

## Ordering and Dates

- Service and community records are sorted by `start`, `end`, then `id`.
- Record IDs must be unique within their feed.
- Dates and timestamps must be accepted by Python `datetime.fromisoformat`.
- Coverage start must not be later than coverage end.
- The web runtime currently accepts schema version 1 only.
