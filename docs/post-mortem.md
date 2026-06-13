# Modular Feed Migration Post-Mortem

Date: June 11, 2026

## Executive Summary

The SPCP Calendar web/data product was forked from commit `bce3af8` into the
public `tdhx/gc-pilgrim` repository without modifying the original SPCP
worktree. The migration replaced the published combined calendar feed with
registry-discovered parish, services, community, and liturgical feeds.

The migration preserved all 260 legacy SPCP records field-for-field across the
specified behavioural surface. It also delivered immutable runtime enrichment,
2026-2028 liturgical feeds, sparse parish validation, a GC Pilgrim application
shell, automated tests, and GitHub Pages deployment.

Production: <https://tdhx.github.io/gc-pilgrim/>

## Outcomes

Completed:

- Created a separate repository preserving SPCP history.
- Removed the deprecated iOS project from the fork.
- Adopted the target modular repository structure.
- Published registry and four-feed architecture.
- Preserved IDs, classifications, service names, presiders, churches,
  devotions, source identifiers, descriptions, times, and liturgical dates.
- Replaced embedded liturgical records with runtime date joins.
- Added status handling: cancelled records are hidden; modified records render.
- Added community records to the common runtime display model.
- Added sparse parish support and optional UI metadata handling.
- Published annual 2026, 2027, and 2028 liturgical feeds plus an aggregate feed.
- Replaced the legacy runtime feed with a migration-only fixture.
- Deployed through a passing Actions-based GitHub Pages workflow.

Final validation:

- 9 Python tests passed.
- 11 Node tests passed.
- Network and offline feed builds passed.
- Desktop, mobile, About, settings, diagnostics, and live-site checks passed.
- Live feeds reported 260 services, 0 community events, and 1,096 liturgical dates.

## What Went Well

### Isolation was respected

All implementation work occurred in a separate clone. The original
`spcp-calendar` worktree remained clean at `bce3af8`, satisfying the most
important migration safety constraint.

### The legacy feed became an executable contract

Moving the former combined feed to `tests/fixtures/legacy-calendar.json`
provided a precise equivalence oracle. The test compares every legacy record
against modular services across:

- identity and source identity
- event type and subtype
- title and service name
- start, end, timezone, and all-day state
- presiders and associated devotions
- location and description
- liturgical date

This made “preserve existing value” measurable rather than subjective.

### Runtime separation is clean

The app no longer knows whether data came from Google Calendar, Universalis, a
newsletter, or manual input. Feed validation and immutable enrichment are
centralized in `app/web/calendar-core.js`.

### Live-source testing found a real future-year issue

The 2028 Universalis page omitted per-day links that the existing parser used
to infer dates. The parser was generalized to derive dates from month headings
and day cells, then tested with a focused fixture. This improved the adapter
rather than introducing hand-maintained 2028 data.

### Deployment was verified, not assumed

The work included local artifact browsing, live endpoint checks, GitHub Actions
inspection, and a final production browser check. The deployment path was
changed from temporary branch-based Pages to the intended Actions workflow and
rerun successfully.

## What Did Not Go Smoothly

### Repository creation authentication was fragile

The available GitHub CLI token could create the repository but lacked the
`workflow` scope needed to push `.github/workflows/pages.yml`. Device
authorization produced a broken confirmation path.

Impact:

- The main project was initially pushed without the workflow file.
- A temporary `gh-pages` branch was used to make the validated site live.
- The workflow was then committed through GitHub's web editor.

Resolution:

- Verified the remote and local trees were identical.
- Added the workflow directly through the authenticated GitHub web session.
- Switched Pages from legacy branch mode to Actions mode.

Lesson:

Validate repository, workflow, and Pages permissions before the publication
phase. Repository write access alone does not imply workflow-file write access.

### The first Actions deployment failed

All build and test steps passed, but the deployment job failed because Pages
was still configured for the temporary `gh-pages` branch.

Resolution:

- Inspected job-level results.
- Changed Pages `build_type` to `workflow`.
- Reran the same workflow successfully.

Lesson:

Treat Pages source configuration as part of deployment state. A correct
workflow cannot deploy while repository settings still select legacy mode.

### The first clone command mixed creation and repository commands

The clone succeeded, but subsequent Git commands ran from `/tmp` instead of the
new clone because the command's working directory did not change dynamically.

Impact:

- No repository data was damaged.
- The checkout sequence had to be rerun from `/tmp/gc-pilgrim`.

Lesson:

Separate workspace creation from commands that assume the new workspace, or
explicitly execute the second step with the new working directory.

### The temporary Pages worktree command changed the wrong branch context

An attempted compound command created an orphan `gh-pages` branch in the
primary clone before publication was moved into the intended worktree.

Impact:

- No tracked files were lost and nothing incorrect was pushed.
- The primary clone was immediately returned to `main`.

Lesson:

For worktree publication, perform creation, branch initialization, artifact
copy, and push as distinct commands with explicit working directories.

### GitHub runner deprecation surfaced late

The successful workflow warned that its JavaScript actions target Node.js 20,
which GitHub is removing in 2026.

Resolution:

- Added `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`.
- Ran the complete workflow again successfully under Node.js 24.

Lesson:

Operational warnings deserve the same close-out discipline as failures when
their enforcement date is imminent.

## Decisions and Tradeoffs

### SPCP only for the first release

No placeholder Southport or Nerang records were published. Sparse parish
behaviour is tested using fixtures, avoiding publication of unverified data.

### Community uses the existing calendar

Community records are mapped into the common display model. Since the current
SPCP source produces no community records, the release has no visual change but
does not require a later runtime redesign.

### Aggregate and annual liturgical feeds

The app consumes one aggregate feed while annual files provide bounded,
independently retrievable archives.

### iOS was excluded

The repository already declared iOS deprecated and outside supported build,
test, and publication scope. Excluding it kept the fork aligned with the
supported product.

## Remaining Risks and Debt

### Generation is still single-parish

The runtime is registry-driven, but `generators/build_all.py` hard-codes
Surfers Paradise. A second parish requires generator iteration and adapter
dispatch.

### Church normalization is parish-configured

Church aliases now live with parish metadata and are resolved consistently by
source reconciliation and feed generation.

### Trusted newsletter corrections are merged

Exact cancellations, confirmed time changes, and high-confidence lay-led
liturgies can overlay the base schedule. Ambiguous observations remain
audit-only.

### No scheduled data refresh exists

CI deploys checked-in snapshots offline. Operators must run the network build,
review changes, and commit them.

### Newsletter automation is only an interface boundary

The newsletter adapter exposes the expected method names but intentionally
raises `NotImplementedError`.

## Follow-Up Priorities

1. Refactor build orchestration to iterate registered parish configs.
2. Make source strategy selection data-driven.
3. Move church aliases and source-specific mappings out of shared generators.
4. Add scheduled refresh automation with reviewable change output.
5. Implement newsletter extraction and explicit correction precedence.
6. Add a real sparse parish only when authoritative source data is available.

## Overall Assessment

The migration met its acceptance criteria for the supported web product and
established a sound public contract. The strongest part of the work is the
combination of isolation, legacy equivalence testing, and live deployment
verification. The main limitation is that the architecture is modular at the
feed and runtime layers before it is fully modular at the build-orchestration
layer. That is a manageable next-stage refactor, not a reason to redesign the
published feeds.
