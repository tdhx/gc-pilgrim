# SPCP Calendar

One Python calendar engine powers both the GitHub Pages debug viewer and the
iOS app. The published client contract is `feeds/v1/calendar.json`.

## Build the calendar

Run the complete network refresh and feed build:

```sh
./build-calendar
```

For deterministic local work using the checked-in intermediate JSONL files:

```sh
./build-calendar --offline
```

The command validates the v1 envelope and atomically replaces the published
feed only after generation succeeds.

## Preview the web viewer

```sh
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000`. To make the iOS app use a local feed, temporarily
override `CALENDAR_FEED_URL` in `ios/Config/Debug.xcconfig`.

## Configure GitHub Pages and iOS

Publish the repository root with GitHub Pages. Before a release build, replace
the placeholder in `ios/Config/Release.xcconfig` with the Pages URL for this
repository. The app project is `ios/SPCPCalendar.xcodeproj` and targets iOS 17+.

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
cd ios/SPCPCalendarCore && swift test
```
