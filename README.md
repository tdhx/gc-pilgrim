# SPCP Calendar

The Python data pipeline powers the GitHub Pages site. The published client
contracts are:

- `feeds/v1/calendar.json`
- `feeds/v1/parish.json`

The legacy `ios/` project is deprecated and currently outside the supported
build, test, and publishing scope.

## Build the calendar

Run the complete network refresh and feed build:

```sh
./build-calendar
```

For deterministic local work using the checked-in intermediate JSONL files:

```sh
./build-calendar --offline
```

The command refreshes the calendar sources and scrapes the parish homepage,
then validates and atomically replaces both published v1 feeds.

## Preview the web viewer

```sh
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000`.

## Configure GitHub Pages

Publish the repository root with GitHub Pages.

## Publish changes

After reviewing the working tree, run the complete test, commit, push, and
GitHub Pages deployment workflow:

```sh
./scripts/publish.sh "Describe the change"
```

## Tests

```sh
python3 -m unittest discover -s tests
npm run test:web
```
