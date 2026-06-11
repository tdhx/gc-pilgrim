# Architecture

GC Pilgrim separates source ingestion, canonical parish metadata, generated
feeds, and runtime enrichment.

## Data Flow

```text
Google Calendar / website / newsletter / manual records
                         |
                     adapters
                         |
              normalized source records
                         |
                     generators
                         |
 parish.json  services.json  community.json  liturgical.json
                         |
             immutable runtime enrichment
```

Adapters expose `fetch()` and `normalise()`. Generators never require a
particular source type, and the web app only understands published feeds.

## Published Layout

```text
feeds/v1/
  registry.json
  liturgical.json
  liturgical/YYYY.json
  parishes/<parish-id>/
    parish.json
    services.json
    community.json
```

`registry.json` declares the default parish and all discoverable parish IDs.
The web app accepts `?parish=<id>` and falls back to the registry default.

## Compatibility

`generators/compat_split.py` converts the former SPCP combined calendar into
modular services and community feeds. The old feed remains only as a migration
test fixture; it is not published.

The deprecated SPCP iOS client is intentionally excluded. Its history remains
in the original `spcp-calendar` repository.
