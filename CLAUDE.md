# scryapi

A Flask JSON API that mirrors Scryfall Oracle card data for search, with users and decks.

## Status
M0–M4 of `docs/AUDIT.md` are done. What's left is listed under "Hand-off" at the end of
that file. Those items need an owner's decision (hosting, frontend origin, password
policy), so don't guess them.

## Read first
- `docs/PRD.md`: what we're building and why.
- `docs/TDD.md`: architecture, data model, API contract and conventions (§14).
- `docs/AUDIT.md`: the ordered fix list. Work milestone by milestone, one AUDIT ID per PR,
  and tick the box when done.

## Commands
- Install: `pip install -e ".[dev]"` (venv at `.venv/`)
- Test: `pytest` from the repo root. Network is blocked by an autouse fixture, so mock
  HTTP with `responses`.
- Postgres: `TEST_DATABASE_URL=postgresql+psycopg://user@host/db pytest`. CI runs both.
  Anything dialect-specific must pass on both.
- Lint and format: `ruff check . && ruff format .`
- Schema: `flask --app scryapi db upgrade`. For a new revision, run
  `flask --app scryapi db migrate -m "<message>"`, then review the file. Search objects
  (`cards_fts*`, `search_vector`, trigram indexes) are hand-written and dialect-conditional.
  See the baseline revision.
- Load data offline: `flask --app scryapi sync-cards --file tests/fixtures/cards_sample.json`
- Run: `flask --app scryapi run`

## Testing conventions
- Fixtures in `tests/conftest.py`: `app` (in-memory SQLite, schema built by running the
  real migrations), `client`, `db`, `no_network` (a `responses` mock, autouse), and
  `cards` (21 real Scryfall cards from `tests/fixtures/cards_sample.json`, loaded through
  the real importer). `alice`, `bob` and `anon` are `ApiClient`s (logged in, logged in,
  anonymous) that attach the CSRF token to mutating requests automatically.
- `xfail(strict=True)` tests encode target behaviour for open AUDIT items. Fixing an item
  makes its test pass, strict mode then fails the run, and you remove the marker.

## Layout
`routes/` (thin HTTP) → `schemas/` (parse args, dump JSON) → `services/` (queries, rules)
→ `models/`. `search/` holds the dialect-specific full-text search. `sync/` holds the
Scryfall pipeline and CLI commands. `errors.py` holds `ApiError` and `ValidationError`.
Raise those, and the handlers turn them into the JSON error envelope.

## Rules
- SQLite in dev/test, Postgres in prod. Dialect-specific code goes only in `search/`,
  the upsert helper and migrations.
- The app factory must have no network or heavy I/O side effects.
- Never serialise models wholesale. Use explicit schemas.
- Session-cookie auth with CSRF on every mutating route.
