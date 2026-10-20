# scryapi

A Flask JSON API that mirrors Scryfall Oracle card data for search, with users and decks.

## Read first
- `docs/PRD.md`: what we're building and why.
- `docs/TDD.md`: architecture, data model, API contract and conventions (§14).
- `docs/AUDIT.md`: the ordered fix list. Work milestone by milestone, one AUDIT ID per PR,
  and tick the box when done.

## Current state (until AUDIT M0 lands)
- The code lives in `scryapi/` with cwd-relative imports, so run commands from inside
  `scryapi/`: `python bootstrap_db.py`, `python app.py`, `pytest`.
- **Warning:** `create_app()` currently downloads around 150 MB from Scryfall at startup
  (AUDIT C5). Don't run the app or the tests in a loop until that's fixed.
- Don't run the existing migration in `scryapi/migrations/versions/`. It destroys the
  FTS index (AUDIT C8).

## Target commands (after M0/M1)
- Install: `pip install -e ".[dev]"`
- Test: `pytest` (from the repo root; no network allowed)
- Lint and format: `ruff check . && ruff format .`
- DB: `flask --app scryapi db upgrade`
- Load data offline: `flask --app scryapi sync-cards --file tests/fixtures/cards_sample.json`

## Rules
- SQLite in dev/test, Postgres in prod. Dialect-specific code goes only in `search/`,
  the upsert helper and migrations.
- The app factory must have no network or heavy I/O side effects.
- Never serialise models wholesale. Use explicit schemas.
- Session-cookie auth with CSRF on every mutating route.
