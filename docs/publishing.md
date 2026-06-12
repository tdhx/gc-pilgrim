# Publishing GC Pilgrim

GC Pilgrim is published to GitHub Pages by
`.github/workflows/pages.yml`. Every push to `main` runs an offline feed
build, the Python and web test suites, the static site build, and the Pages
deployment.

Production:

- <https://tdhx.github.io/gc-pilgrim/>
- <https://tdhx.github.io/gc-pilgrim/diagnostics.html>

## 1. Review the Worktree

Work from the repository root and inspect every pending change:

```sh
git status --short
git diff
git diff --check
```

Only publish files you have reviewed. Do not discard unrelated work merely to
make the worktree clean.

## 2. Refresh Sources When Needed

Skip this step for an app-only release. To fetch fresh public calendar and
liturgical source data, run:

```sh
./build-feeds
```

This updates checked-in files under `raw/` and `feeds/`. Review those changes
before publishing. CI deliberately does not access the network; it rebuilds
feeds from the committed snapshots with `./build-feeds --offline`.

## 3. Validate Locally

Run the same build and test commands used by GitHub Actions:

```sh
./build-feeds --offline
python3 -m unittest discover -s tests
npm run test:web
npm run build:site
git diff --check
```

For app changes, preview the generated site:

```sh
python3 -m http.server 8000 --directory _site
```

Open <http://127.0.0.1:8000/> and
<http://127.0.0.1:8000/diagnostics.html>. Check the affected behavior at
desktop and mobile widths.

## 4. Commit and Push

Commit the reviewed changes on `main`, then push:

```sh
git add -A
git commit -m "Describe the release"
git push origin main
```

The push starts the `Build and publish GC Pilgrim` workflow automatically.

## 5. Monitor Deployment

Using the GitHub CLI:

```sh
gh run list --workflow pages.yml --limit 5
gh run watch
```

Alternatively, open the repository's Actions page:
<https://github.com/tdhx/gc-pilgrim/actions/workflows/pages.yml>.

Do not treat the release as published until both the build and deploy jobs
have completed successfully for the pushed commit.

## 6. Verify Production

Open the production calendar and diagnostics page. Confirm the new behavior is
present and diagnostics reports valid schema version 1 feeds.

Useful direct checks:

```sh
curl -I https://tdhx.github.io/gc-pilgrim/
curl https://tdhx.github.io/gc-pilgrim/feeds/v1/registry.json
```

If the site still shows an older version immediately after deployment, perform
a hard refresh after confirming the workflow deployed the expected commit.

## Manual Workflow Run

The Pages workflow also supports `workflow_dispatch`. To redeploy the current
`main` commit without making another commit:

```sh
gh workflow run pages.yml --ref main
```

## Rollback

Revert the problematic commit and push the revert:

```sh
git revert <commit-sha>
git push origin main
```

The normal Pages workflow rebuilds and deploys the reverted state. Avoid force
pushes and history rewrites on `main`.
