# scryapi

A JSON REST API for searching Magic: The Gathering cards and managing decklists. It
mirrors Scryfall's [Oracle bulk data](https://scryfall.com/docs/api/bulk-data) locally,
so search is fast and doesn't depend on Scryfall at request time.

> Card data © Wizards of the Coast, provided by [Scryfall](https://scryfall.com). This
> project is not affiliated with or endorsed by either.

**Status:** feature-complete for v1 (card search, accounts, decks, public sharing) and
tested on SQLite and Postgres. Before the first deployment, see the hand-off list at the
end of [docs/AUDIT.md](docs/AUDIT.md).

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
| `RATELIMIT_STORAGE_URI` | `memory://` | use `redis://...` in production (memory counts per worker) |
| `SCRYAPI_RATELIMIT_SEARCH` | `60/minute` | per client IP, `/api/cards*` |
| `SCRYAPI_RATELIMIT_AUTH` | `10/minute` | per client IP, login and register combined |
| `SCRYAPI_PROXY_COUNT` | `0` | trusted reverse proxies in front of the app |

## Running

```sh
flask --app scryapi db upgrade     # create or upgrade the schema
flask --app scryapi sync-cards     # download (~25 MB) and import Scryfall Oracle cards
flask --app scryapi run --debug    # dev server with auto-reload, http://127.0.0.1:5000
```

The full sync takes about 10 seconds and leaves ~36,500 cards in `instance/dev.sqlite3`.
Optional overrides go in `.env` (copy `.env.example`).

To check the whole stack end to end (search, register/login with CSRF, decks, privacy,
logout), run this against the running server. It creates two throwaway users each run:

```sh
python scripts/smoke.py                      # default http://127.0.0.1:5000
```

Run `sync-cards` again any time. It skips the import when Scryfall's data hasn't
changed (`--force` overrides this). To work offline, use
`sync-cards --file tests/fixtures/cards_sample.json` to load 21 sample cards.

For a weekly refresh, schedule `flask --app scryapi sync-cards` with cron or your host's
scheduled jobs. Or run `flask --app scryapi run-scheduler` as a single long-lived
process.

Production: `gunicorn 'scryapi:create_app()'`, with `flask db upgrade` as a release step.

## API

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/cards` | | `name`, `type` (substring), `text` (full-text over rules text), `page` ≥ 1, `limit` 1–50 |
| GET | `/api/cards/<scryfall_id>` | | |
| GET | `/api/auth/csrf` | | returns `{csrf_token}`; send it as `X-CSRFToken` on every POST/PUT/PATCH/DELETE |
| POST | `/api/auth/register` | | `{username, email, password}` |
| POST | `/api/auth/login` | | `{login, password, remember?}`; the response's `X-CSRFToken` header is the new token |
| POST | `/api/auth/logout` | | |
| GET | `/api/auth/me` | ✓ | |
| GET | `/api/users/<username>` | | public profile |
| GET | `/api/users/<username>/decks` | | that user's public decks |
| GET | `/api/decks/public` | | all public decks, most recently updated first |
| GET | `/api/decks/mine` | ✓ | |
| POST | `/api/decks` | ✓ | `{name, description?, format?, is_public?}` |
| GET / PATCH / DELETE | `/api/decks/<id>` | owner (GET: or public) | |
| PUT | `/api/decks/<id>/cards` | owner | `{cards: [{card_id, quantity, board?}]}` replaces the list |

Auth uses session cookies. All errors are JSON:
`{"error": "<code>", "message": "...", "details": [...]}`. The full contract is in
[TDD §9](docs/TDD.md#9-api-contract-v1).

## Development

```sh
pytest                                # SQLite, no network access; HTTP calls must be mocked
TEST_DATABASE_URL=postgresql+psycopg://user@localhost/scryapi_test pytest   # Postgres
ruff check . && ruff format --check . # lint and format
```

CI (`.github/workflows/ci.yml`) runs lint, plus tests on Python 3.12/3.14 × SQLite/Postgres
with an 85% coverage floor.

Tests marked `xfail(strict=True)` describe target behaviour from the audit. When you
fix the referenced item, remove the marker.
