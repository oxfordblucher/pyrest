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
| `DATABASE_URL` | `sqlite:///dev.sqlite3` (in `instance/`) | required in production (Postgres) |
| `SECRET_KEY` | dev placeholder | required in production, ≥ 32 chars |
| `SCRYAPI_DATA_DIR` | `instance/data` | where the downloaded bulk file is kept |

## Running

```sh
flask --app scryapi db upgrade     # create or upgrade the schema
flask --app scryapi sync-cards     # download (~25 MB) and import Scryfall Oracle cards
flask --app scryapi run            # dev server
```

Run `sync-cards` again any time. It skips the import when Scryfall's data hasn't
changed (`--force` overrides this). To work offline, use
`sync-cards --file tests/fixtures/cards_sample.json` to load 21 sample cards.

For a weekly refresh, schedule `flask --app scryapi sync-cards` with cron or your host's
scheduled jobs. Or run `flask --app scryapi run-scheduler` as a single long-lived
process.

Production: `gunicorn 'scryapi:create_app()'`, with `flask db upgrade` as a release step.

## API (current)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/cards` | `name`, `type` (substring), `text` (full-text over rules text), `page` ≥ 1, `limit` 1–50 |
| GET | `/api/cards/<scryfall_id>` | |

All errors are JSON: `{"error": "<code>", "message": "...", "details": [...]}`.
The full v1 API is specified in [TDD §9](docs/TDD.md#9-api-contract-v1).

## Development

```sh
pytest                                # no network access; HTTP calls must be mocked
ruff check . && ruff format --check . # lint and format
```

Tests marked `xfail(strict=True)` describe target behaviour from the audit. When you
fix the referenced item, remove the marker.
