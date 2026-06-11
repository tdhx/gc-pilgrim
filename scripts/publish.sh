#!/bin/sh

set -eu

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "Usage: $0 \"commit message\"" >&2
  exit 64
fi

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

if [ -z "$(git status --porcelain)" ]; then
  echo "No changes to publish."
  exit 0
fi

echo "Checking changes..."
git diff --check

echo "Running Python tests..."
python3 -m unittest discover -s tests

echo "Running web tests..."
npm run test:web

echo "Committing and pushing..."
git add -A
git commit -m "$1"
git push

commit=$(git rev-parse HEAD)

echo "Triggering GitHub Pages..."
gh api --method POST repos/tdhx/spcp-calendar/pages/builds >/dev/null

attempt=0
while [ "$attempt" -lt 24 ]; do
  page_info=$(gh api repos/tdhx/spcp-calendar/pages/builds/latest \
    --jq '[.status, .commit] | @tsv')
  page_status=$(printf '%s\n' "$page_info" | cut -f1)
  page_commit=$(printf '%s\n' "$page_info" | cut -f2)

  if [ "$page_status" = "built" ] && [ "$page_commit" = "$commit" ]; then
    break
  fi

  if [ "$page_status" = "errored" ]; then
    echo "GitHub Pages failed to build commit $commit." >&2
    exit 1
  fi

  attempt=$((attempt + 1))
  sleep 5
done

if [ "$page_status" != "built" ] || [ "$page_commit" != "$commit" ]; then
  echo "Timed out waiting for GitHub Pages to publish $commit." >&2
  exit 1
fi

echo "Verifying the live feed..."
curl -fsS https://tdhx.github.io/spcp-calendar/feeds/v1/calendar.json |
  python3 -c '
import json
import sys

feed = json.load(sys.stdin)
assert feed["schema_version"] == 1
assert isinstance(feed["events"], list)
event_count = len(feed["events"])
print(f"Live feed verified: {event_count} events")
'

curl -fsS https://tdhx.github.io/spcp-calendar/feeds/v1/parish.json |
  python3 -c '
import json
import sys

feed = json.load(sys.stdin)
assert feed["schema_version"] == 1
assert feed["id"] == "surfers-paradise"
assert len(feed["churches"]) == 3
print("Live parish feed verified:", feed["name"])
'

echo "Published $commit"
echo "https://tdhx.github.io/spcp-calendar/"
