# Adding a Parish

The public feed and web runtime support multiple parishes, but the current
generator orchestration is still Surfers Paradise-specific. Onboarding a second
production parish therefore requires both data work and a small generator
refactor.

## Parish Definition

Create:

```text
parishes/<parish-id>/
  parish.json
  config.json
```

Minimum `parish.json`:

```json
{
  "schema_version": 1,
  "id": "example-parish",
  "name": "Example Parish",
  "churches": []
}
```

Add contact, office, clergy, church, and branding metadata only when it is
available. Church IDs must be stable and unique within the parish.

Example config:

```json
{
  "parish_id": "example-parish",
  "timezone": "Australia/Brisbane",
  "sources": {
    "services": "manual",
    "community": "manual",
    "liturgical": "universalis-brisbane"
  }
}
```

## Source Adapter

Use an existing adapter or add one under `sources/`. Adapters should expose:

```python
fetch(...)
normalise(...)
```

Normalized service candidates must contain the fields needed by the service
rules, including source identity and start/end values. Community candidates
must at least support stable identity, title, start, and end.

Do not make the app understand source-specific fields.

## Generator Work Required

To add another parish to the current production builder:

1. Add the parish ID to `PARISH_IDS` in `generators/build_all.py`.
2. Add a normalized source adapter and configure its records and diagnostics
   in the parish input mapping.
3. Add parish and config definitions under `parishes/<parish-id>/`.
4. Add source, recurrence, feed-contract, and runtime selection tests.
5. Decide whether liturgical years remain global constants or are derived from
   required service coverage.

These changes should not alter the public feed contracts.

## Registry and Runtime

Add the parish ID to `feeds/v1/registry.json` through generation, not by
hard-coding the web app. With more than one parish:

- `?parish=<id>` selects a parish.
- An invalid ID falls back to `default_view_id`, or `default_parish_id` when no
  default view is configured.
- The parish selector becomes visible automatically.
- When an aggregate view is registered, the new parish is included in it
  automatically; no separate aggregate feed is generated.

## Acceptance Tests

Add fixtures and tests for:

- the parish's minimum and rich metadata forms
- source normalization
- unique IDs and chronological ordering
- church references
- empty services or community feeds
- registry selection
- rendering without optional contact, office, clergy, or branding fields

Do not publish placeholder parish records as if they were authoritative.
