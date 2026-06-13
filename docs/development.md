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

## Community Newsletter Extraction

Install the optional ingestion dependencies:

```sh
python3 -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. The `.env` file is
gitignored and loaded automatically by `extract-community-events`.
`OPENAI_MODEL` defaults to `gpt-5.5`.

Surfers Paradise discovery uses the newest post on its public newsletter hub
that contains a Google Drive PDF link.

Process the newest newsletter for one parish or both:

```sh
./extract-community-events --parish burleigh-heads
./extract-community-events --all
./extract-community-events --all --force
```

`--force` reparses the newest document even when its ID matches `state.json`.

The extractor writes reviewable state under `raw/<parish>/newsletter/`:

- extracted text and per-document audit JSON
- accumulated `community.jsonl`
- recurring `series.jsonl`, expanded into the rolling three-month feed window
- `service-divergences.jsonl`, used for audited trusted schedule overlays
- `state.json`, used to avoid reprocessing the same newest document

Recurring series retain stable IDs, refresh when mentioned again, and stop
publishing 90 days after their last newsletter mention. Missing end times use a
one-hour default. Community records use controlled categories and preserve a
specific campus venue alongside its canonical parent `church_id`.

Local PDF text extraction is the normal path. The original PDF is sent to the
model only when the text layer fails quality checks. Downloaded PDFs are
temporary and are not committed.

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
- field-for-field preservation of unchanged legacy SPCP records

Node coverage includes:

- registry selection and fallback
- immutable church and liturgical enrichment
- cancelled and modified statuses
- Liturgical, Community, and Combined feed modes
- normalized church aliases and trusted newsletter schedule overlays
- unique untimed cancellations and ambiguous untimed quarantine
- recurring newsletter expansion, stable IDs, and 90-day expiry
- community event assembly
- Monthly view and persisted mascot selection
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
