# GC Pilgrim

GC Pilgrim is a lightweight Catholic parish companion that aggregates public
parish information into four independent feeds:

- `parish.json` - who the parish is
- `services.json` - when people can pray
- `community.json` - how people can participate
- `liturgical.json` - what the Church is celebrating

The published registry includes Surfers Paradise, Southport, Burleigh Heads,
Nerang, Runaway Bay, and Coomera. The web runtime supports richer and sparser
parish definitions without changing its feed contract. Its default Gold Coast
wide view combines events from every registered parish at runtime.

## Live Project

- Site: <https://tdhx.github.io/gc-pilgrim/>
- Repository: <https://github.com/tdhx/gc-pilgrim>
- Diagnostics: <https://tdhx.github.io/gc-pilgrim/diagnostics.html>

## Quick Start

Install source-ingestion dependencies:

```sh
python3 -m pip install -r requirements.txt
```

Generate feeds from checked-in source records:

```sh
./build-feeds --offline
```

Run the test suites:

```sh
python3 -m unittest discover -s tests
npm run test:web
```

Build and preview the GitHub Pages artifact:

```sh
./build-site
python3 -m http.server 8000 --directory _site
```

Then open <http://127.0.0.1:8000/>.

Refreshing public sources requires network access:

```sh
./build-feeds
```

## Documentation

- [Architecture](docs/architecture.md)
- [Feed contracts](docs/feeds.md)
- [Development and testing](docs/development.md)
- [Publishing](docs/publishing.md)
- [Adding a parish](docs/adding-a-parish.md)
- [Operations and deployment](docs/operations.md)
- [Migration post-mortem](docs/post-mortem.md)

## Current Scope

The runtime and feed contracts are modular. The build orchestrator generates
six parish feeds and liturgical years 2026-2028. Surfers Paradise and Burleigh
Heads also include newsletter-derived community and worship overlays.
