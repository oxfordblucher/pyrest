# scryapi

A JSON REST API for searching Magic: The Gathering cards and managing decklists. It
mirrors Scryfall's [Oracle bulk data](https://scryfall.com/docs/api/bulk-data) locally,
so search is fast and doesn't depend on Scryfall at request time.

> Card data © Wizards of the Coast, provided by [Scryfall](https://scryfall.com). This
> project is not affiliated with or endorsed by either.

**Status:** early development. The card search API works. Users and decks are still
stubs. See [docs/AUDIT.md](docs/AUDIT.md) for the roadmap of fixes.

## Docs

- [PRD](docs/PRD.md): what we're building and why
- [TDD](docs/TDD.md): architecture, data model, API contract
- [AUDIT](docs/AUDIT.md): the ordered fix list, organised by milestone

## Setup

Requires Python 3.12+.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Settings come from environment variables. A `.env` file is loaded automatically by the
`flask` CLI.

| Variable | Default | Notes |
|---|---|---|
| `SCRYAPI_ENV` | `development` | `development`, `testing` or `production` |
| `DATABASE_URL` | `sqlite:///dev.sqlite3` (in `instance/`) | required in production |
| `SECRET_KEY` | dev placeholder | required in production, ≥ 32 chars |
| `SCRYAPI_ENABLE_SCHEDULER` | `1` in dev, `0` otherwise | downloads and imports Scryfall data at startup and weekly |

## Running

```sh
# Create tables (stopgap until migrations are fixed, AUDIT C8)
SCRYAPI_ENABLE_SCHEDULER=0 flask --app scryapi init-db

# Run the dev server. With the scheduler on, the first start downloads around 150 MB
# from Scryfall and imports it before serving.
flask --app scryapi run
```

## API (current)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/cards/` | `name`, `type` (substring), `text` (full-text rules text), `page`, `limit` (≤ 50) |
| GET | `/api/cards/<id>` | |

The target v1 API is specified in [TDD §9](docs/TDD.md#9-api-contract-v1).

## Development

```sh
pytest                                # no network access; HTTP calls must be mocked
ruff check . && ruff format --check . # lint and format
```

Tests marked `xfail(strict=True)` describe target behaviour from the audit. When you
fix the referenced item, remove the marker.
