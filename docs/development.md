# Development

## Requirements

- Python 3 with `zoneinfo`
- Node.js 22 or later
- A local HTTP server for browser testing
- Network access only for source refreshes

The project has no third-party Python or npm runtime dependencies.

## Reproducible Offline Build

Checked-in normalized source snapshots live under `raw/`. Generate all public
feeds without network access:

```sh
./build-feeds --offline
```

This is the mode used by GitHub Actions. It should be deterministic apart from
the `generated_at` timestamp.

## Network Refresh

```sh
./build-feeds
```

This refreshes:

- the public SPCP Google Calendar
- Universalis Brisbane calendars for 2026, 2027, and 2028

Successful refreshes replace the corresponding `raw/*.jsonl` snapshots and
regenerate all public feeds. Review changes to both `raw/` and `feeds/`.

## Tests

Run all automated checks:

```sh
python3 -m unittest discover -s tests
npm run test:web
```

Python coverage includes:

- recurrence exclusions and overrides
- future Universalis pages without date links
- all feed validators
- sparse parish metadata
- annual liturgical coverage
- status and church-reference failures
- one-to-one preservation of 260 legacy SPCP records

Node coverage includes:

- registry selection and fallback
- immutable church and liturgical enrichment
- cancelled and modified statuses
- community event assembly
- sparse parish acceptance
- existing filters and calendar date helpers
- removal of the legacy combined-feed loader

## Site Build and Preview

```sh
./build-site
python3 -m http.server 8000 --directory _site
```

Preview:

- app: <http://127.0.0.1:8000/>
- diagnostics: <http://127.0.0.1:8000/diagnostics.html>

`build-site` deletes and recreates `_site/`, copies the static app, copies
generated feeds, and adds `.nojekyll`.

## Validation Checklist

Before committing a data or code change:

1. Run the offline feed build.
2. Run Python and Node tests.
3. Run `git diff --check`.
4. Inspect feed count and coverage changes.
5. Preview desktop and mobile layouts for app changes.
6. Confirm diagnostics loads all four feed types.

## Important Fixtures

- `tests/fixtures/legacy-calendar.json` is the pre-migration combined feed.
  Do not refresh it casually; it protects migration equivalence.
- `tests/fixtures/sparse-parish/parish.json` proves that optional parish
  metadata remains optional.
