# Code Audit — scryapi

- **Audited commit:** `27990b5` ("sanitization and routes")
- **Date:** 2026-10-20
- **Scope:** every tracked file under the repo (~700 LOC).
- **Companion docs:** [PRD](PRD.md) · [TDD](TDD.md)

Line numbers below refer to commit `27990b5`. After refactors they will drift; the
description of each issue is the source of truth.

## How to use this document (agents)

1. Work milestone by milestone (M0 → M4). Inside a milestone, follow the listed order —
   later items assume earlier ones landed.
2. One AUDIT ID (or a tightly coupled group noted below) per PR. Reference the ID in the
   PR title, e.g. `[C6] Make pagination validation reject bad input`.
3. An item is done only when every **Acceptance** bullet is met *and* covered by a test
   where one is listed.
4. When an item is done, change its status box from `[ ]` to `[x]` in this file in the
   same PR.
5. If the fix requires a decision not covered by the [TDD](TDD.md), stop and leave a note
   in the PR for the human reviewer rather than guessing.

Severity: **P0** broken/crashes · **P1** security or blocks Postgres · **P2** data
correctness/efficiency · **P3** quality/hygiene.

---

## Summary

| ID | Sev | Title | Milestone |
|----|-----|-------|-----------|
| Q1 | P3 | Not an importable package; cwd-dependent imports | M0 |
| Q3 | P3 | Dependency manifest incomplete | M0 |
| Q6 | P3 | Repo hygiene (.DS_Store, .gitignore, import side effects) | M0 |
| S3 | P1 | Hardcoded config, no SECRET_KEY, no env split | M0 |
| Q7 | P3 | Test harness essentially absent | M0 (harness) / M4 (CI) |
| C5 | P0 | Data sync runs synchronously inside the app factory | M1 |
| C4 | P0 | Weekly scheduler job has no app context — never works | M1 |
| S4 | P1 | Outbound HTTP has no timeout or required headers | M1 |
| S5 | P1 | Non-atomic download can import a truncated file | M1 |
| E4 | P1 | Column types/lengths wrong for real data; fails on Postgres | M1 |
| C7 | P0 | FTS query injection → 500; FTS table pollutes metadata | M1 |
| C8 | P0 | Only migration destroys the FTS index | M1 |
| E1 | P2 | Import never updates existing cards | M1 |
| E2 | P2 | Whole bulk file loaded into memory | M1 |
| E3 | P2 | Multi-face cards imported with NULL text | M1 |
| E5 | P2 | Missing index on `cards.name`; internal id exposed | M1 |
| E6 | P2 | FTS sync strategy undocumented | M1 |
| C6 | P0 | Request validation is a no-op | M1 |
| Q2 | P3 | Data-access layer reads `flask.request` | M1 |
| S6 | P1 | LIKE wildcard injection; unbounded params | M1 |
| S7 | P1 | No JSON error handlers; no rate limiting | M1 / M4 |
| Q4 | P3 | `print()` instead of logging | M1 |
| S1 | P1 | Plaintext password column, no auth | M2 |
| S2 | P1 | `to_dict()` serialises every column (incl. secrets) | M2 |
| C1 | P0 | List endpoints `jsonify` a `Result` object → 500 | M2 / M3 |
| C9 | P0 | `deck_cards.card_id` type mismatches `cards.id` | M3 |
| C2 | P0 | Deck route stubs return `None`; wrong signature | M3 |
| C3 | P0 | `public_routes.py` cannot be imported | M3 |
| Q5 | P3 | Dead / commented-out code | spread (see item) |
| Q8 | P3 | No README, lint config, typing | M0 / M4 |

---

## M0 — Foundation

### [x] Q1 · P3 · Make `scryapi` a real package
**Where:** all modules — e.g. `scryapi/app.py:1`, `scryapi/helpers/create.py:2-5`,
`scryapi/routes/card_routes.py:2-4`.
**Problem:** Imports are top-level (`from extensions import db`, `from models import *`)
and only resolve when the working directory is `scryapi/`. Tests, Alembic, and any WSGI
server must be launched from that exact directory. Wildcard imports in `create.py` hide
what is actually used.
**Fix:**
- Add `pyproject.toml` at the repo root; `scryapi/` becomes the package (add
  `scryapi/__init__.py` exposing `create_app`).
- Convert every import to absolute package form (`from scryapi.extensions import db`).
- Remove wildcard imports; import blueprints explicitly.
- Move the app factory from `helpers/create.py` to `scryapi/__init__.py` (or
  `scryapi/app.py`) — see TDD §4 for target layout.
- Delete `scryapi/app.py` / `bootstrap_db.py` in favour of `flask --app scryapi ...`
  commands (bootstrap replaced by `flask db upgrade`, see C8).
**Acceptance:**
- `pip install -e ".[dev]"` then `pytest` works from the repo root.
- `flask --app scryapi routes` lists all routes from the repo root.
- `grep -rn "import \*" scryapi/` returns nothing.

### [x] Q3 · P3 · Complete the dependency manifest
**Where:** `requirements.txt`.
**Problem:** Missing pytest, Flask-Migrate/Alembic (required by `migrations/env.py`),
a production WSGI server, and the Postgres driver. No dev/prod separation.
**Fix:** Declare dependencies in `pyproject.toml`:
runtime (Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF or equivalent
CSRF, requests, APScheduler, ijson, psycopg[binary], gunicorn) and
`[project.optional-dependencies] dev` (pytest, pytest-cov, ruff, responses or
requests-mock). Either delete `requirements.txt` or generate it from a lock tool.
**Acceptance:** fresh venv + `pip install -e ".[dev]"` is sufficient to run the app,
the tests, and `flask db upgrade`.
**Done note:** Flask-Login, Flask-WTF, ijson and psycopg are *not* added yet. Add each in
the milestone that first uses it (M1: ijson, psycopg; M2: Flask-Login, Flask-WTF).

### [x] Q6 · P3 · Repo hygiene
**Where:** `.DS_Store`, `scryapi/.DS_Store`, `.gitignore`, `scryapi/helpers/download.py:5-7`.
**Problem:** macOS metadata committed; `.gitignore` does not cover `*.sqlite3`,
`.venv/`, `.pytest_cache/`, `.DS_Store`, `.env`, `*.egg-info`; `download.py` creates a
directory as an import side effect.
**Fix:** `git rm --cached` both `.DS_Store`; extend `.gitignore`; move the `mkdir` into
the download function.
**Acceptance:** `git ls-files | grep -i ds_store` is empty; importing
`scryapi.sync.download` (new location) touches no filesystem.

### [x] S3 · P1 · Environment-based configuration
**Where:** `scryapi/helpers/create.py:12`.
**Problem:** DB URI is hardcoded to SQLite, there is no `SECRET_KEY` (needed for session
auth in M2), and no distinction between dev / test / prod.
**Fix:** `scryapi/config.py` with `BaseConfig`, `DevConfig`, `TestConfig`, `ProdConfig`
(see TDD §8). `create_app(config=None)` accepts an override for tests. `ProdConfig`
refuses to start without `SECRET_KEY` and `DATABASE_URL`. Support `.env` via
`python-dotenv` in dev only.
**Acceptance:** test suite uses in-memory SQLite via `TestConfig`; starting with
`FLASK_ENV`/`SCRYAPI_ENV=production` and no `SECRET_KEY` raises a clear error.

### [x] Q7 (part 1) · P3 · Test harness
**Where:** `scryapi/tests/conftest.py`, `scryapi/tests/test_sanitation/`.
**Problem:** The only fixture is a placeholder returning `"3"`; tests use a hand-rolled
mock request; no app/client fixture; no DB fixture.
**Fix:** Move tests to `tests/` at repo root. Provide `app`, `client`, `db_session`
fixtures (TestConfig, schema created per session, transaction rolled back per test) and
a small fixture file `tests/fixtures/cards_sample.json` (~20 real Scryfall oracle
objects incl. a double-faced card, a split card, and a `*`-power creature).
**Acceptance:** `pytest` passes from repo root with no network; existing sanitizer cases
are ported to request-level tests against `/api/cards`.

### [x] Q8 (part 1) · P3 · README + lint config
**Fix:** `README.md` (what it is, setup, run, test, sync data); `ruff` config in
`pyproject.toml` (lint + format, line length 100). Run `ruff format` once in its own PR.
**Acceptance:** `ruff check . && ruff format --check .` pass.

---

## M1 — Stabilise the card catalogue

Recommended order: C5 → C4 → S4 → S5 → E4 → C7 → C8 → E1 → E2 → E3 → E5 → E6 → C6/Q2 → S6 → S7 → Q4.

### [x] C5 · P0 · Take data sync out of the app factory
**Where:** `scryapi/helpers/create.py:21`, `scryapi/helpers/scheduler.py:16-23`.
**Problem:** `create_app()` calls `schedule_job(app)`, which (a) starts a
`BackgroundScheduler` in *every* process that builds the app — tests, every CLI command,
each gunicorn worker, and twice under the debug reloader; and (b) synchronously
downloads ~150 MB and imports it when the file is missing or > 7 days old. Consequences:
- Fresh setup via `bootstrap_db.py` imports *before* `db.create_all()` → "no such table".
- If the download fails, `import_cards()` raises `FileNotFoundError` and the app cannot
  boot.
- Tests/CLI hit the network.
**Fix:**
- New `flask sync-cards` CLI command (download + import), see TDD §7.
- Scheduler is opt-in (`SCRYAPI_ENABLE_SCHEDULER=1`), started once from a dedicated
  entrypoint (or run sync as an external cron / container job — preferred for prod).
- App factory must have no network or heavy I/O side effects.
**M0 state:** the scheduler is already gated by `SCRYAPI_ENABLE_SCHEDULER` (off in
test/prod, **on by default in `DevConfig`** because it is currently the only way to load
data). As part of C5, flip the `DevConfig` default to off once `flask sync-cards` exists.
**Acceptance:** `create_app(TestConfig)` performs no HTTP calls (assert with
`responses`/`requests-mock` in strict mode); `flask sync-cards` against the fixture file
(`--file tests/fixtures/cards_sample.json`) populates the DB.

### [x] C4 · P0 · Scheduled job needs an app context
**Where:** `scryapi/helpers/scheduler.py:18`.
**Problem:** `scheduler.add_job(func=lambda: do_job(), ...)` runs `import_cards()`
outside any app context → `RuntimeError: Working outside of application context`. The
weekly refresh has never worked.
**Fix:** job wrapper does `with app.app_context(): run_sync()`; add
`max_instances=1, coalesce=True`; log failures instead of crashing the thread.
**Acceptance:** unit test invokes the job function directly (no context pushed) and it
completes against the fixture file.

### [x] S4 · P1 · Outbound HTTP hygiene
**Where:** `scryapi/helpers/download.py:12`, `:27`.
**Problem:** No `timeout` (a stalled connection hangs the worker forever). Scryfall's API
requires `User-Agent` and `Accept` headers. `json.loads(raw.text)` instead of `.json()`.
**Fix:** shared `requests.Session` with headers
(`User-Agent: scryapi/<version>`, `Accept: application/json`), `timeout=(5, 60)`, a
retry adapter (3 retries, backoff, on 429/5xx).
**Acceptance:** test with `responses` verifies headers and that a timeout surfaces as a
logged failure, not a hang.

### [x] S5 · P1 · Atomic, validated download
**Where:** `scryapi/helpers/download.py:30-33`, `scryapi/helpers/scheduler.py:21`.
**Problem:** Writes directly to `card_data.json`. An interrupted download leaves a
truncated file with a fresh mtime, so the staleness check treats it as valid and the
importer crashes or imports partial data.
**Fix:** stream to `card_data.json.part`, verify size against the bulk-data
`size` field (and/or that it parses), then `os.replace`. Track freshness by the bulk
object's `updated_at` (store it in a small `sync_state` table) rather than file mtime.
**Acceptance:** simulated mid-stream failure leaves the previous file untouched.

### [x] E4 · P1 · Correct card column types (blocks Postgres)
**Where:** `scryapi/models/card.py:8-13`.
**Problem:** `name String(50)` and `type_line String(25)` are shorter than real data
(e.g. "Legendary Creature — Human Wizard" is 33 chars; split/DFC names exceed 50).
`power`/`toughness` are `Integer` but Scryfall sends strings (`"*"`, `"1+*"`, `"X"`).
SQLite silently accepts this; Postgres rejects it and the import fails.
**Fix:** `name`, `type_line`, `mana_cost` → `Text` (or `String(255)`); `power`,
`toughness` → `String(8)`; add `loyalty`, `cmc` (Numeric), `colors`/`color_identity`
(JSON), `layout`, `scryfall_uri`, `image_uri` per TDD §5.
**Acceptance:** fixture import passes on both SQLite and Postgres (CI matrix, Q7 pt 2).

### [x] C7 · P0 · Safe full-text search; keep FTS out of ORM metadata
**Where:** `scryapi/data_access/card_access.py:11-16`, `:29-30`; `scryapi/models/card.py:15-22`.
**Problem:**
- The `text` query param is passed verbatim to FTS5 `MATCH`. FTS5 query syntax errors
  (`text="`, `text=AND`, `text=foo(`) raise `sqlite3.OperationalError` → HTTP 500.
- `cards_fts` is declared as an ordinary `db.Table` on `db.metadata` (with `rowid` typed
  `String` while `content_rowid` is the integer `cards.id`). `create_all()` and Alembic
  autogenerate therefore treat it as a normal table — this is what produced the
  destructive migration in C8.
- The FTS5 DDL is SQLite-only; prod is Postgres.
**Fix:** introduce the `SearchBackend` seam from TDD §6:
- SQLite backend: tokenise user input into terms, quote each as an FTS5 string
  (`"term"` with `"` doubled), AND them; join via `text("cards_fts MATCH :q")` against
  `rowid`; DDL lives in the migration, not in model metadata.
- Postgres backend: generated `tsvector` column + GIN index, `websearch_to_tsquery`.
- Remove the module-level `cards_fts` Table and the `after_create` listener.
**Acceptance:** `GET /api/cards?text=%22` and `?text=AND` return 200 (empty or matching
results) — never 500; `db.metadata.tables` contains no `cards_fts`.
**Found during M0:** this also made `db.create_all()` crash on every fresh database
("table cards_fts already exists"), because the `after_create` hook creates the virtual
table before `create_all` reaches the plain-table declaration. M0 added a stopgap
`create_tables()` in `scryapi/__init__.py` that skips `cards_fts`. Remove it in C7/C8.
Remove the `xfail` from `tests/test_cards_api.py::test_malformed_search_text_never_errors`.

### [x] C8 · P0 · Replace the destructive migration
**Where:** `scryapi/migrations/versions/9b3e823a5792_.py`, `scryapi/migrations/env.py`,
`scryapi/helpers/create.py:6-8,19`.
**Problem:** The only migration (autogenerated, "empty message") **drops the FTS5
shadow tables** `cards_fts_idx/_docsize/_config/_data` and alters the virtual table —
running it corrupts search. Flask-Migrate is commented out in the factory, so
`migrations/env.py` (which reads `current_app.extensions['migrate']`) cannot run.
Schema is actually created by `db.create_all()` in `bootstrap_db.py`.
**M0 state:** `migrations/` now lives at the repo root. The stopgap
`flask --app scryapi init-db` command and `create_tables()` in `scryapi/__init__.py`
stand in for migrations. Delete both here.
**Fix:** enable Flask-Migrate in the factory; delete the existing revision; generate a
fresh baseline from the M1 models; add dialect-conditional `op.execute` for search
objects (FTS5 virtual table on SQLite; tsvector column + GIN index + `pg_trgm` extension
on Postgres). Extend `include_object` to exclude `cards_fts` *and* its shadow tables
(`name.startswith("cards_fts")`). Give every revision a real message.
**Acceptance:** `flask db upgrade` on empty SQLite and empty Postgres both succeed;
`flask db migrate` immediately afterwards produces no changes.

### [x] E1 · P2 · Upsert, don't ignore, on re-import
**Where:** `scryapi/helpers/populate.py:41-42`.
**Problem:** `on_conflict_do_nothing` means Oracle errata, new rulings text, or any
changed field never reach the DB after the first import. Also uses
`sqlalchemy.dialects.sqlite.insert` (line 3) — breaks on Postgres.
**Fix:** dialect-aware upsert helper (`sqlite.insert` / `postgresql.insert`, both support
`on_conflict_do_update(index_elements=["scryfall_id"], set_=...)`). Optionally delete
cards absent from the latest bulk file.
**Acceptance:** test imports fixture, mutates one card's `oracle_text` in the JSON,
re-imports, asserts the DB reflects the change.

### [x] E2 · P2 · Stream the bulk file
**Where:** `scryapi/helpers/populate.py:20-21`.
**Problem:** `json.load` materialises the full oracle bulk file (~150 MB JSON → several
hundred MB of Python objects) in memory, inside a web worker (see C5).
**Fix:** `ijson.items(f, "item")` and upsert in batches of 500–1000, committing per batch
or once at the end inside one transaction.
**Acceptance:** importer accepts any iterable of card dicts; peak RSS during the real
import stays under ~200 MB (manual check, note result in PR).

### [x] E3 · P2 · Handle multi-face cards
**Where:** `scryapi/helpers/populate.py:29-38`.
**Problem:** Transform/MDFC/split/adventure cards keep `oracle_text`, `mana_cost`,
`power`, `toughness` inside `card_faces[]`; top-level fields are absent so these cards
import with NULL text and are invisible to text search.
**Fix:** a pure `normalise_card(raw: dict) -> dict` that falls back to joining face
values with `"\n//\n"` (text) or `" // "` (cost/type); store raw faces in a JSON column
for the API to expose.
**Acceptance:** unit tests on fixture DFC + split card.

### [x] E5 · P2 · Indexes and stable public identifier
**Where:** `scryapi/models/card.py`, `scryapi/routes/card_routes.py:26`.
**Problem:** No index on `name` (every list query sorts by it; name filter uses it).
API exposes the autoincrement `id`, which changes if the DB is rebuilt and so is a poor
key for clients and deck lists.
**Fix:** index `name` (and on Postgres a trigram GIN index for `ILIKE '%x%'`); rename
`uuid` → `scryfall_id` (unique, not null) and expose it as the public `id` in API
responses; `GET /api/cards/<scryfall_id>`.
**Acceptance:** `EXPLAIN` of the default list query uses the name index (note in PR).

### [x] E6 · P2 · Document FTS sync strategy
**Where:** `scryapi/helpers/populate.py:9-14`.
**Problem:** The SQLite FTS table is an external-content table kept in sync only by a
full `'rebuild'` after import. Correct while the importer is the only writer, but this
is undocumented and fragile.
**Fix:** covered by TDD §6; add a code comment at the rebuild call. (On Postgres the
generated column removes the problem.)
**Acceptance:** comment present; TDD §6 matches the implementation.

### [x] C6 + Q2 · P0 · Real request validation; request-agnostic data layer
**Where:** `scryapi/sanitation/req_sani.py:11-14,30`; `scryapi/data_access/card_access.py:18-21`;
`scryapi/routes/card_routes.py:10-15`.
**Problem:**
- `throw_errors()` *returns* `(400, msg)`; `get_card_data` ignores the return value, so
  invalid input is never rejected.
- `if (int_arg and int_arg < 1)` — `0` is falsy, so `page=0`/`limit=0` pass validation.
- No upper bound check on `limit`; the route separately clamps to 50 and on
  `ValueError` silently resets to defaults, so the client never learns the input was bad.
- Pagination is parsed twice (route + sanitizer). The data-access function reads the
  `flask.request` global, so it can't be reused or unit-tested without a request.
**Fix:** one `parse_card_query(args) -> CardQuery` (dataclass) in the route layer that
raises a `ValidationError` mapped to a JSON 400 (`{"error": "validation_error",
"details": [...]}`); `limit` must be 1–50, `page` ≥ 1. `card_access.search_cards(query:
CardQuery, backend: SearchBackend)` takes only explicit arguments. Delete
`sanitation/` once superseded.
**Acceptance:** request tests: `page=0`, `limit=0`, `limit=51`, `page=two` → 400 with
details; valid → 200; DAL unit-tested without a request context.

### [x] S6 · P1 · Escape LIKE input; bound parameter sizes
**Where:** `scryapi/data_access/card_access.py:6-9`.
**Problem:** `name`/`type` filters interpolate into `ILIKE '%{v}%'` without escaping
`%` and `_` (not SQL injection — values are bound — but lets clients craft
pathological patterns). No max length on any query param.
**Fix:** escape `\`, `%`, `_` and use `ilike(pattern, escape="\\")`; reject params
longer than 100 chars (400).
**Acceptance:** `?name=%25` matches only names containing a literal `%`; 101-char
param → 400.

### [x] S7 · P1 · JSON error handling (rate limiting in M4)
**Where:** `scryapi/sanitation/error_handler.py` (entirely commented out).
**Problem:** Errors render Werkzeug HTML pages; unhandled exceptions return HTML 500s.
The API contract (TDD §9) is JSON-only.
**Fix:** register handlers in the factory for `HTTPException` and `Exception` returning
`{"error": <code>, "message": <safe text>}`; log the traceback server-side; never echo
exception text for 500s.
**Acceptance:** `GET /api/nope` → JSON 404; a forced exception in a test route → JSON
500 without a stack trace.

### [x] Q4 · P3 · Logging instead of print
**Where:** `download.py:19,34,37`, `populate.py:25`, `bootstrap_db.py:8`.
**Fix:** module loggers (`logging.getLogger(__name__)`); log sync start/end, counts,
duration.
**Acceptance:** `grep -rn "print(" scryapi/` returns nothing.

---

### M1 completion notes

- **New finding (fixed under S4/S5/E2):** Scryfall's bulk-data API no longer returns
  `download_uri`, only `jsonl_download_uri` (gzipped JSON Lines) and `compressed_size`.
  The original downloader would have crashed with an uncaught `KeyError`. The pipeline
  now streams the `.jsonl.gz` line by line, so ijson isn't needed. Measured on the real
  file (2026-10-20): 36,509 cards imported and 2,352 `art_series` skipped, in 9.4 s with
  183 MB peak RSS on SQLite. Real names reach 141 characters and type lines 91, which
  confirms E4.
- **E5:** `EXPLAIN QUERY PLAN` for the default listing gives
  `SCAN cards USING INDEX ix_cards_name`. Every sampled query on the full catalogue ran
  in under 50 ms.
- **C8:** the baseline covers `cards` and `sync_state` only. `users` and the deck tables
  get their own revisions in M2/M3. Until then,
  `tests/test_migrations.py::test_models_match_migrations` is strict-xfail.
- **Postgres:** the backend, upsert and migration paths are written but need a Postgres
  run (see Q7 part 2 / CI).
- The stopgap `init-db` / `create_tables()` from M0 is gone. The schema now comes only
  from migrations.

---

## M2 — Users & authentication (session cookies)

### [x] S1 · P1 · Hash passwords; implement session auth
**Where:** `scryapi/models/user.py:8`.
**Problem:** `password` column implies plaintext storage; there is no registration,
login, or authorisation anywhere.
**Fix:** rename to `password_hash`; `werkzeug.security.generate_password_hash`
(scrypt default) or argon2; Flask-Login with `HttpOnly`, `Secure` (prod),
`SameSite=Lax` cookies; CSRF protection on all state-changing endpoints; endpoints per
TDD §9 (`/api/auth/register|login|logout|me`). Normalise email to lowercase; generic
error message on bad credentials; constant-ish time (always hash on login).
**Acceptance:** tests for register, duplicate email/name (409), login success/failure,
logout, `me` requires auth (401), POST without CSRF token → 400/403.

### [x] S2 · P1 · Explicit response serialisation
**Where:** `scryapi/extensions.py:5-6` (`Base.to_dict`), used in `card_routes.py:19,29`.
**Problem:** `to_dict()` dumps every column. Applied to `User` it would leak
`email` and the password hash; applied to future models it leaks whatever is added.
**Fix:** remove `Base.to_dict`; per-resource serialiser functions (or marshmallow /
pydantic schemas) with explicit allow-lists per TDD §9.
**Acceptance:** test that `GET /api/users/<name>` response keys equal the documented set.

### [x] C1 (users) · P0 · Fix user list endpoint
**Where:** `scryapi/routes/user_routes.py:7-10`.
**Problem:** `jsonify(db.session.execute(...))` passes a `Result` object → `TypeError`
→ 500. Also an unauthenticated user directory is not in the PRD.
**Fix:** replace with `GET /api/users/<username>` public profile (S2 serialiser); drop
the list endpoint unless the PRD adds it.
**Acceptance:** request test passes.

---

### M2 completion notes

- Login and registration clear the session before `login_user`, which rotates the
  session and prevents fixation. The new CSRF token comes back in the `X-CSRFToken`
  response header, so clients don't need a second round trip.
- `WTF_CSRF_TIME_LIMIT = None`: tokens live as long as the session.
- `GET /api/users` (the user directory) is removed. Public profiles are
  `GET /api/users/<username>` and never include email.
- **Test-harness finding:** the `app` fixture's long-lived app context made Flask reuse
  `g` across test-client requests, which leaked the cached CSRF token and logged-in user
  between clients. `tests/conftest.py` now resets `g` at the start of each request.
  Production isn't affected.

---

## M3 — Decks & public sharing

### [x] C9 · P0 · Fix `deck_cards` schema
**Where:** `scryapi/models/deck_cards.py:3-7`, `scryapi/models/deck.py`.
**Problem:** `card_id` is `String` but references `cards.id` (`Integer`) — Postgres
rejects the FK. A plain association table also can't hold a quantity, which every deck
needs.
**Fix:** association object model `DeckCard(deck_id, card_id INT FK, quantity INT ≥1,
board ENUM main|side)`; `ON DELETE CASCADE` from decks; add `Deck.is_public`,
`description`, `format`, `created_at`, `updated_at`; index `decks.user_id`.
**Acceptance:** migration upgrades on both DBs; model tests for cascade delete.

### [x] C1 (decks) + C2 · P0 · Implement deck routes
**Where:** `scryapi/routes/deck_routes.py:7-22`.
**Problem:** `get_decks` jsonifies a `Result` (500); `get_user_decks`, `make_deck`,
`update_deck` return `None` (Flask raises → 500); `update_deck()` is missing the `id`
parameter declared in the route (`TypeError`).
**Fix:** implement per TDD §9: list own decks, create, get, update (owner only), delete,
add/remove cards. Ownership check returns 404 (not 403) for other users' private decks.
**Acceptance:** CRUD + authorisation tests (owner, other user, anonymous).

### [x] C3 · P0 · Rewrite public routes
**Where:** `scryapi/routes/public_routes.py:5,7,17`.
**Problem:** Module cannot be imported: `Blueprint("")` raises `ValueError`;
`publicbp.before_request()` is called without a function (`TypeError`); line 17 is a
decorator with nothing to decorate (`SyntaxError`). Currently dormant only because no
module imports it.
**Fix:** fold into the deck blueprint as `GET /api/decks/public` and
`GET /api/users/<username>/decks` (public only), per TDD §9; delete the file.
**Acceptance:** endpoints tested; file removed.

---

### M3 completion notes

- `DeckCard` is an association object keyed on (deck, card, board) with `quantity`.
  CHECK constraints cover quantity ≥ 1 and board ∈ {main, side}. Deletes cascade from
  users to decks to deck_cards, both in the DB (`ON DELETE CASCADE`) and in the ORM.
- SQLite now enforces foreign keys (`PRAGMA foreign_keys=ON`). A future migration that
  rebuilds a table in batch mode must switch them off around the rebuild.
- `public_routes.py` is deleted. Its endpoints are `GET /api/decks/public` and
  `GET /api/users/<username>/decks`.
- `tests/test_migrations.py::test_models_match_migrations` now passes: models and
  migrations agree.

---

## M4 — Hardening (human finishing pass recommended)

### [x] S7 (part 2) · Rate limiting
Flask-Limiter on `/api/cards` (e.g. 60/min/IP) and `/api/auth/*` (e.g. 10/min/IP);
storage backend Redis in prod, memory in dev.

### [x] Q7 (part 2) · CI
GitHub Actions: ruff, pytest with coverage; matrix SQLite + Postgres 16 service
container; fail under 85% line coverage on `scryapi/`.

### [x] Q8 (part 2) · Typing
Done in M5. Type hints on public functions; optional `mypy --strict` on `scryapi/sync` and
`scryapi/search`.

### [x] Q5 · Dead code sweep
Remove any remaining: `data_access/deck_access.py` (imports only),
`sanitation/error_handler.py` (commented out), dummy `my_fix` fixture,
`if __name__ == '__main__'` in `helpers/create.py`, commented code in `scheduler.py`.
Most of these disappear naturally in M0–M3; this item is the final check.

### M4 completion notes

- **Rate limits:** `/api/cards*` is limited to `SCRYAPI_RATELIMIT_SEARCH` (60/minute).
  `/api/auth/login` and `/register` share one `SCRYAPI_RATELIMIT_AUTH` bucket
  (10/minute). Responses carry `X-RateLimit-*` and `Retry-After` headers.
  `SCRYAPI_PROXY_COUNT` turns on `ProxyFix` so limits key on the real client IP. The
  storage default is `memory://`, which counts per worker. **Production needs
  `RATELIMIT_STORAGE_URI=redis://…`** (a human decision that depends on hosting).
  `RATELIMIT_SWALLOW_ERRORS` is on in prod, so a store outage doesn't take the API down.
- **CI:** `.github/workflows/ci.yml` runs ruff, plus pytest with
  `--cov-fail-under=85` on Python 3.12/3.14 × SQLite/Postgres 17. Locally the suite
  passes on SQLite and on Postgres 17 (Homebrew, 2026-10-20) with 96.6% coverage. The
  workflow hasn't run on GitHub yet because the branch hasn't been pushed.
- **Postgres verified:** a real Scryfall sync of 36,509 cards took 12.9 s with 169 MB
  peak RSS. `EXPLAIN` shows `ix_cards_name_trgm` serving `ILIKE` and
  `ix_cards_search_vector` serving full-text search. Typical queries take 2–11 ms.
  Deep `OFFSET` pages take about 90 ms.
- **Extra hardening, not in the original audit:** `MAX_CONTENT_LENGTH` of 256 KB (413
  JSON error), `X-Content-Type-Options: nosniff` and `Cache-Control: no-store` on every
  response, and a remember-me cookie that lasts 30 days instead of Flask-Login's
  default of a year.
- **Q5:** `vulture` found no dead code (every hit was a framework-registered callback).
- **Q8 part 2 (typing)** was done in M5.

---

## M5 — Owner decisions (2026-10-20)

Decided by the owner: frontend origin is undecided (so make it configurable), add
change-password but no email reset, implement full deck legality, don't push yet.
Hosting is deferred.

### [x] D1 · P2 · Identical name ordering on SQLite and Postgres
Add `cards.sort_name` (casefolded, accents stripped, computed at import) with a bytewise
collation (`COLLATE "C"` on Postgres), and order by `(sort_name, id)` everywhere. The
fixture's order must be identical on both dialects. Replaces hand-off item 5.

### [x] A1 · P1 · Change password; sign out other sessions
`POST /api/auth/password {current_password, new_password}`: 401 on a wrong current
password, same 12–128 rule, starts a fresh session. A per-user `session_version` is
embedded in the Flask-Login id, so the change invalidates every other session and
remember-me cookie.

### [x] F1 · P2 · Configurable cross-origin frontend
`SCRYAPI_CORS_ORIGINS` (comma-separated, empty by default) enables CORS with credentials
for exactly those origins and adds them to `WTF_CSRF_TRUSTED_ORIGINS`.
`SCRYAPI_COOKIE_SAMESITE` (`Lax` default; `None` forces `Secure`). With nothing set,
behaviour is unchanged.

### [x] L1 · P2 · Store card legalities; constrain deck format
Import Scryfall `legalities` into `cards.legalities` (JSON). `Deck.format` must be one
of Scryfall's format keys or null. Commander-style decks get a `commander` board.

### [x] L2 · P2 · Deck legality report
`GET /api/decks/<id>` includes `legality: {format, legal, problems: [{code, message,
card?}]}`. Report, don't block: saving an illegal deck still succeeds. Rules: per-card
legality, Vintage restricted list, constructed size/sideboard/4-copy limits (basic lands
and "any number" cards exempt), commander-style size, singleton, commander count and
color identity.

### [x] Q8 (part 2) · Typing
See M4. Type hints on public functions, plus a lenient `mypy scryapi` job in CI.

### M5 completion notes

- **D1:** `cards.sort_name` (`name_key()`: casefolded, accents and ligatures folded,
  `COLLATE "C"` on Postgres) drives ordering and the name filter, so SQLite and Postgres
  return the same order and "aether" finds "Æther Vial". Name searches rank exact, then
  prefix, then substring matches. The migration backfills 36.5k rows in about 4 s.
- **SQLite migration fix (found while testing L1):** batch-mode rebuilds of `cards`
  failed on any database with decks, because SQLite enforced the `deck_cards` foreign key
  during the table swap. That included D1's upgrade. `migrations/env.py` now turns FK
  enforcement off for the run, checks `PRAGMA foreign_key_check` at the end and turns it
  back on. Regression tests cover both directions.
- **A1:** the login id is `"<id>:<session_version>"`. A password change bumps the version,
  which signs out every other session and remember-me cookie with no server-side session
  store. Cookies issued before this change (plain ids) are signed out once.
- **F1:** `SCRYAPI_CORS_ORIGINS` and `SCRYAPI_COOKIE_SAMESITE`. With CORS on, Flask-WTF's
  same-host HTTPS Referer check is replaced by one that also accepts the configured
  origins. Preflights skip the rate limiter: the blueprint-wide search limit was counting
  them, while per-route limits weren't.
- **L1/L2:** legality for all 23 Scryfall formats, reported rather than enforced; the
  rules are in TDD §9. Checked against real decks on the full catalogue, covering partner,
  Background and Doctor pairings, the Vintage restricted list, Relentless Rats and color
  identity. A 100-card deck takes 31 ms to save and 8 ms to load. Known gaps: Pauper
  Commander's "uncommon" rule isn't checked (rarity isn't stored), and Scryfall's `tlr`
  format gets per-card legality only because its rules couldn't be confirmed. After
  upgrading an existing database, run `flask sync-cards --force` once to load legalities.
- **Q8:** models use SQLAlchemy 2 `Mapped[...]` (the migration-drift test confirms the
  schema is unchanged). mypy is clean, with full annotations required in services,
  schemas, search, sync, models and formats, and it runs in the CI lint job.
- **Not done, deliberately:** keyset pagination. Deep `OFFSET` pages take about 90 ms,
  well inside NFR-1, and cursors would change the API contract.
- **Verified:** 260 tests on SQLite and on Postgres 17, plus `scripts/smoke.py` against
  the dev server on both, including a SQLite database upgraded from the M4 schema.

---

## M6 — Removed cards (owner decision 2026-10-20)

### [x] R1 · P2 · Drop removed cards from decks and notify owners
Resolves PRD open Q5. Cards Scryfall stops listing are deleted from every deck in the
import transaction, with one `cards_removed` notification per affected deck
(`GET /api/notifications`, mark read, `unread_notifications` on `Me`). They stay in
`cards` as inactive, so ids are stable if Scryfall restores them, and decks can't add
them. An import dropping more than 2% of the catalogue (and more than 50 cards) is refused
unless `--allow-removals` is passed.

### M6 completion notes

- Verified on the full Postgres catalogue. Removing Lightning Bolt and Counterspell from
  the bulk file removed them from 6 decks and notified their owners ("Scryfall no longer
  lists 2 cards from your deck “Izzet Tempo”, so they were removed: Counterspell ×3,
  Lightning Bolt ×4."). Loading the 21-card sample over the full catalogue was refused
  ("would remove 36567 of 36588 cards") with nothing changed.
- A failure after the deck entries are deleted (tested by failing the search rebuild)
  rolls back the import, the removals and the notifications together.
- Cost: the active-id snapshot and the prune add about 160 ms to an import. Separately,
  full imports on Postgres take about 18 s, up from 13 s, since L1 started storing
  legalities (23 keys per card). Fine for a weekly job.
- Cards that were already inactive and still sat in decks from before this change are
  removed (with notifications) by the first sync after upgrading.

---

## Hand-off: decisions and work for the human pass

Everything above is implemented and tested. What's left needs the owner:

1. **Hosting (PRD open Q4, deferred by the owner).** Pick a platform, then configure
   `DATABASE_URL`, `SECRET_KEY`, `RATELIMIT_STORAGE_URI` (Redis), `SCRYAPI_PROXY_COUNT`
   and a persistent `SCRYAPI_DATA_DIR`. Run `flask db upgrade` as a release step and
   schedule `flask sync-cards` weekly.
2. **Frontend origin:** nothing to code. When the frontend's URL is known, set
   `SCRYAPI_CORS_ORIGINS` (and `SCRYAPI_COOKIE_SAMESITE=None` only if it's on a different
   site). See TDD §8.
3. **Push and CI (the owner said not yet):** push `v1` to `origin`, open a PR
   and confirm the CI matrix (lint, mypy, tests on SQLite and Postgres) is green. It has
   never run on GitHub.
4. **Optional review:** read the API contract (TDD §9) as a frontend author would, and
   spot-check the legality rules against formats you play.

---

## Positive notes

- Batching the import (500 rows/statement) and using `on_conflict` was the right instinct.
- Bound parameters are used throughout — no classic SQL injection found.
- Blueprint-per-resource and a separate data-access layer are a sound structure to build on.
- `migrations/env.py` already has an `include_object` hook — the right place to exclude FTS objects.
