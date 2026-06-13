# Operations

## Deployment

GitHub Actions workflow: `.github/workflows/pages.yml`

On every push to `main`, the workflow:

1. Checks out the repository.
2. Generates feeds from checked-in normalized snapshots.
3. Runs Python and Node tests.
4. Builds `_site/`.
5. Uploads and deploys the Pages artifact.

The workflow can also be started manually. Pages is configured with
`build_type: workflow`.

Production:

- <https://tdhx.github.io/gc-pilgrim/>
- <https://tdhx.github.io/gc-pilgrim/diagnostics.html>

The workflow opts JavaScript actions into Node.js 24 because GitHub is removing
Node.js 20 runner support in 2026.

## Source Freshness

Deployment does not fetch public sources. It publishes checked-in snapshots
using `./build-feeds --offline`.

To refresh source data:

```sh
./build-feeds
python3 -m unittest discover -s tests
npm run test:web
```

Review and commit changed files under `raw/` and `feeds/`. Pushing `main`
deploys the reviewed result.

There is currently no scheduled refresh. Feed freshness is an operator
responsibility.

Newsletter extraction additionally requires `OPENAI_API_KEY`. This name is
suitable for a future GitHub Actions secret, but the current workflow does not
invoke the extractor.

Surfers Paradise uses the newest dated post on its public newsletter hub that
contains a Google Drive PDF link.

## Diagnostics

The diagnostics page reports:

- parish and schema version
- generated timestamp
- service coverage
- service and community counts
- total liturgical dates
- registered parishes
- source freshness labels
- feed warnings

It validates all public feeds before displaying information.

## Health Checks

Useful endpoints:

```text
/feeds/v1/registry.json
/feeds/v1/parishes/surfers-paradise/parish.json
/feeds/v1/parishes/surfers-paradise/services.json
/feeds/v1/parishes/surfers-paradise/community.json
/feeds/v1/liturgical.json
```

A healthy current deployment has:

- schema version 1 for every feed
- 260 SPCP services in the migration baseline
- an empty but valid community feed
- 1,096 liturgical dates across 2026-2028

Counts may legitimately change after source refreshes; unexpected changes
should be reviewed against raw snapshots and migration tests.

## Failure Modes

### Feed build fails

Run the failing command locally. Common causes include source HTML changes,
unsupported recurrence patterns, invalid references, or incomplete annual
liturgical coverage.

### Build passes but deploy fails

Confirm repository Pages settings use GitHub Actions, not a branch source.
The deployment job requires `pages: write` and `id-token: write`.

### App shows “Calendar unavailable”

Check browser network responses for all four modular feeds. A missing parish
feed or schema mismatch prevents runtime assembly.

### Stale data

Run a network refresh and inspect `sources[].status` plus `generated_at`.
Offline builds label source records `cached`; network builds label them
`fresh`.

## Rollback

Revert the problematic `main` commit. The workflow rebuilds and redeploys the
prior checked-in snapshots and app. The old SPCP combined feed is not a runtime
fallback; it exists only as a test fixture.
