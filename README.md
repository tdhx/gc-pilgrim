# GC Pilgrim

GC Pilgrim is a lightweight Catholic parish companion that aggregates public
parish information into four independent feeds:

- `parish.json` - who the parish is
- `services.json` - when people can pray
- `community.json` - how people can participate
- `liturgical.json` - what the Church is celebrating

The first published parish is Surfers Paradise Catholic Parish. The platform
supports richer and sparser parish definitions without changing the app.

## Build

Generate feeds from checked-in source records:

```sh
./build-feeds --offline
```

Refresh public sources and regenerate all feeds:

```sh
./build-feeds
```

Build the GitHub Pages artifact:

```sh
./build-site
python3 -m http.server 8000 --directory _site
```

## Test

```sh
python3 -m unittest discover -s tests
npm run test:web
```

See [docs/architecture.md](docs/architecture.md) for feed contracts and adapter
boundaries.
