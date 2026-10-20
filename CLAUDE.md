# scryapi

A Flask JSON API that mirrors Scryfall Oracle card data for search, with users and decks.

## Read first
- `docs/PRD.md`: what we're building and why.
- `docs/TDD.md`: architecture, data model, API contract and conventions (§14).
- `docs/AUDIT.md`: the ordered fix list. Work milestone by milestone, one AUDIT ID per PR,
  and tick the box when done.

## Commands
- Install: `pip install -e ".[dev]"` (venv at `.venv/`)
- Test: `pytest` from the repo root. Network is blocked by an autouse fixture, so mock
  HTTP with `responses`.
- Lint and format: `ruff check . && ruff format .`
- Create tables (stopgap until C8): `SCRYAPI_ENABLE_SCHEDULER=0 flask --app scryapi init-db`
- Run: `flask --app scryapi run`. **Warning:** in dev the scheduler is on by default and
  downloads about 150 MB from Scryfall at startup (AUDIT C5). Set
  `SCRYAPI_ENABLE_SCHEDULER=0` unless you need the data.
- Don't run the migration in `migrations/versions/`. It destroys the FTS index (AUDIT C8).

## Testing conventions
- Fixtures in `tests/conftest.py`: `app`, `client`, `db`, and `cards` (21 real Scryfall
  cards from `tests/fixtures/cards_sample.json`, loaded through the real importer).
- `xfail(strict=True)` tests encode target behaviour for open AUDIT items. Fixing an item
  makes its test pass, strict mode then fails the run, and you remove the marker.

## Rules
- SQLite in dev/test, Postgres in prod. Dialect-specific code goes only in `search/`,
  the upsert helper and migrations.
- The app factory must have no network or heavy I/O side effects.
- Never serialise models wholesale. Use explicit schemas.
- Session-cookie auth with CSRF on every mutating route.
