# TDD — scryapi

- **Status:** Draft v0.1 (2026-10-20)
- **Implements:** [PRD](PRD.md)
- **Fixes tracked in:** [AUDIT](AUDIT.md)

Decisions already fixed by the owner: **session-cookie auth**, **SQLite for dev/test,
Postgres in prod**, docs live in the repo.

## 1. Overview

A Flask 3 application exposing a JSON API under `/api`. It has three subsystems:

1. **Catalogue**: the `cards` table plus a search backend, populated by the sync pipeline.
2. **Sync**: downloads Scryfall `oracle_cards` bulk data and upserts it into the catalogue.
   It runs from the CLI or a scheduler, **never from the app factory**.
3. **Accounts & decks**: users, session auth, decks and deck cards.

```
           ┌────────────── Flask app (gunicorn workers) ───────────────┐
 client ──▶│ routes (blueprints) → validation → services/DAL → models  │──▶ DB
           │                         │                                  │   (SQLite dev /
           │                         └─▶ SearchBackend (FTS5 | tsvector)│    Postgres prod)
           └────────────────────────────────────────────────────────────┘
                                                                  ▲
 scheduler/cron ──▶ `flask sync-cards` ──▶ download (Scryfall) ──▶ import (upsert) ─┘
```

## 2. Constraints

- One codebase must run on SQLite and Postgres. Dialect-specific code is isolated behind
  small seams: the search backend, the upsert helper and migrations.
- App startup does no network or bulk I/O (PRD NFR-2).
- Scryfall API etiquette: a `User-Agent` and `Accept` header, at most 10 req/s, and bulk
  data fetched no more than daily. We fetch weekly.

## 3. Layering rules

| Layer | May import | Must not |
|---|---|---|
| `routes/` (blueprints) | `schemas`, `services`, `auth` | touch `db.session` directly for anything beyond trivial gets |
| `schemas/` (validation + serialisation) | stdlib, models (types only) | access the DB or `flask.request` globals (receive args explicitly) |
| `services/` (business logic, DAL) | `models`, `search`, `extensions` | import `flask.request` |
| `search/` | `models`, `extensions` | know about HTTP |
| `sync/` | `models`, `extensions`, `requests` | be imported by the app factory except to register CLI commands |
| `models/` | `extensions` | import anything above |

## 4. Package layout (target)

```
pyproject.toml
README.md
CLAUDE.md
docs/                 PRD.md, TDD.md, AUDIT.md
migrations/           Alembic (Flask-Migrate), moved to repo root
scryapi/
  __init__.py         create_app(config=None)
  config.py           BaseConfig / DevConfig / TestConfig / ProdConfig
  extensions.py       db, migrate, login_manager, csrf, limiter
  errors.py           JSON error handlers, ValidationError
  models/             card.py, user.py, deck.py (Deck, DeckCard), sync_state.py
  schemas/            card.py, user.py, deck.py  (parse_* and dump_* functions)
  services/           cards.py, users.py, decks.py
  search/             __init__.py (get_backend), sqlite_fts.py, postgres_fts.py
  sync/               __init__.py (run_sync), download.py, normalise.py, importer.py,
                      cli.py, scheduler.py
  routes/             cards.py, auth.py, users.py, decks.py
tests/
  conftest.py
  fixtures/cards_sample.json
  test_cards_api.py, test_sync_*.py, test_auth.py, test_decks.py, ...
```

Validation and serialisation use small hand-written functions with dataclasses, which
keeps dependencies light. Pydantic v2 is an acceptable swap if the schemas grow. Pick
one approach and stay consistent.

## 5. Data model

```
users
  id              PK int
  username        text  unique not null   (3–30, [a-z0-9_], stored lowercase)
  email           text  unique not null   (stored lowercase)
  password_hash   text  not null
  created_at      timestamptz default now

cards
  id              PK int                   (internal; never exposed)
  scryfall_id     text  unique not null    (public id; Scryfall "id" / oracle print id)
  oracle_id       text  index
  name            text  not null  index    (+ pg_trgm GIN on Postgres)
  mana_cost       text
  cmc             float
  type_line       text
  oracle_text     text                     (faces joined with "\n//\n")
  power           varchar(16)              ("*", "1+*", "X" are valid)
  toughness       varchar(16)
  loyalty         varchar(16)
  colors          json
  color_identity  json
  layout          text
  card_faces      json                     (raw faces subset for multi-face cards)
  image_uri       text
  scryfall_uri    text
  is_active       bool default true        (false if dropped from latest bulk: soft delete)
  updated_at      timestamptz
  search_vector   tsvector GENERATED       (Postgres only; GIN index; not in ORM model)

decks
  id              PK int
  user_id         FK users.id  ON DELETE CASCADE  index
  name            text not null (1–100)
  description     text
  format          text                     (free text in v1)
  is_public       bool default false
  created_at, updated_at

deck_cards                                  (association object)
  deck_id         FK decks.id ON DELETE CASCADE  ┐ PK
  card_id         FK cards.id                    │
  board           text check in ('main','side')  ┘
  quantity        int  check >= 1

sync_state
  key             PK text  ('oracle_cards')
  source_updated_at text                    (Scryfall bulk "updated_at", compared for equality)
  last_success_at   timestamptz
  last_error        text
```

Notes:
- Decks reference `cards.id` (internal int) for join efficiency. The API speaks
  `scryfall_id` and services translate. Cards are soft-deleted (`is_active=false`) so
  existing decks never lose rows.
- No `Base.to_dict()`. Serialisation is always explicit (AUDIT S2).

## 6. Search

```python
class SearchBackend(Protocol):
    def apply_text_filter(self, stmt: Select, text: str) -> Select: ...
    def rebuild(self) -> None: ...  # after bulk import
```

`search.get_backend()` chooses the backend from `db.engine.dialect.name`.

**SQLite (`sqlite_fts.py`)**
- An external-content FTS5 table over rules text only (PRD FR-C1: `text` searches rules text; `name`/`type` have their own filters): `CREATE VIRTUAL TABLE cards_fts USING fts5(oracle_text, content='cards', content_rowid='id', tokenize='porter unicode61')`. Porter stemming roughly matches Postgres's `english` config. It is created in a migration and is **not** declared in ORM metadata.
- Query building: split the user input on whitespace, drop empty terms, and wrap each
  term in double quotes with internal `"` doubled. Join the terms with spaces (implicit
  AND). This turns any input into a valid FTS5 query, so there are no syntax errors.
- Filter: `Card.id.in_(select rowid from cards_fts where cards_fts match :q)` via `text()`.
- Sync: the importer is the only writer, so `rebuild()` runs
  `INSERT INTO cards_fts(cards_fts) VALUES('rebuild')` once after each import, inside the
  same transaction. Triggers were rejected because they add per-row cost to the 35k-row
  upsert for no benefit.

**Postgres (`postgres_fts.py`)**
- `search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(oracle_text, ''))) STORED` with a GIN index. Not declared in the ORM model. `migrations/env.py` excludes it and the search indexes from autogenerate.
- Results are ordered by name, not by rank, the same as on SQLite.
- Filter: `search_vector @@ websearch_to_tsquery('english', :q)`. `websearch_to_tsquery`
  never raises on user input.
- `rebuild()` is a no-op.
- `name`/`type` substring filters use `ILIKE` backed by `pg_trgm` GIN indexes.

Every substring filter escapes `\ % _` and passes `escape='\\'` (AUDIT S6).

## 7. Sync pipeline

```
flask sync-cards [--file PATH] [--force]
  1. GET https://api.scryfall.com/bulk-data/oracle_cards
       → {jsonl_download_uri, updated_at, compressed_size}
  2. if updated_at == sync_state.source_updated_at and not --force: exit "up to date"
  3. stream jsonl_download_uri → <data dir>/oracle_cards.jsonl.gz.part ;
       verify byte count == compressed_size ; os.replace → oracle_cards.jsonl.gz
  4. gzip-decode line by line → skip non-cards and art_series → normalise_card()
       → batches of 500
  5. one transaction: mark all cards is_active=false, upsert batches (dialect-aware
     ON CONFLICT (scryfall_id) DO UPDATE ... is_active=true), search.rebuild()
  6. update sync_state (last_success_at / last_error), log counts + duration
```

- `--file` skips steps 1–3 and accepts `.jsonl`, `.jsonl.gz` or a small `.json` array
  (the test fixture). Tests and offline development use it.
- **Bulk format:** as of 2026-10, Scryfall's bulk-data objects only offer gzipped JSON
  Lines (`jsonl_download_uri`). The old `download_uri` JSON array is gone. Streaming
  lines keeps peak RSS around 180 MB for the full ~36.5k-card import, which takes
  about 10 s on SQLite.
- **Normalisation:** for multi-face cards, text fields (`oracle_text`, `mana_cost`,
  `type_line`) are joined across faces so every face is searchable. Stats
  (power/toughness/loyalty) come from the first face that has them, and the per-face
  details go in `card_faces`. `art_series` layouts are skipped, the same as Scryfall's
  own search hides them by default.
- **HTTP:** one `requests.Session` with headers `User-Agent: scryapi/<version> (+repo url)`
  and `Accept: application/json;q=0.9,*/*;q=0.8`, `timeout=(5, 60)`, and urllib3 `Retry`
  (3 tries, backoff 1s, on 429/500/502/503/504).
- **Failure semantics:** a failure in any step rolls back and records `last_error`. The
  existing catalogue keeps serving (PRD FR-S4).
- **Scheduling:**
  - *Prod (preferred):* the platform cron / scheduled container runs `flask sync-cards`
    weekly. Web workers never schedule anything.
  - *Single-process option:* `flask run-scheduler [--interval SECONDS]` runs a
    `BlockingScheduler` in its own process. It syncs immediately, then on the interval,
    with `max_instances=1, coalesce=True`. The job body runs under `app.app_context()`
    and swallows errors after they're logged and recorded, so the scheduler keeps
    running.
- **Upsert helper:** `sync/importer.py::upsert_cards(rows)` picks
  `sqlalchemy.dialects.{sqlite,postgresql}.insert` by dialect. Both expose
  `on_conflict_do_update`.

## 8. Configuration & security

| Key | Dev | Test | Prod |
|---|---|---|---|
| `SQLALCHEMY_DATABASE_URI` (`DATABASE_URL`) | `sqlite:///dev.sqlite3` (in `instance/`) | `sqlite:///:memory:` | Postgres URL, **required** |
| `SECRET_KEY` | fixed dev value | fixed test value | env, **required**, ≥ 32 bytes |
| `SESSION_COOKIE_SECURE` | False | False | True |
| `SESSION_COOKIE_HTTPONLY` | True | True | True |
| `SESSION_COOKIE_SAMESITE` | Lax | Lax | Lax (see PRD open Q1) |
| `REMEMBER_COOKIE_*` | mirror the session settings | | |
| `WTF_CSRF_ENABLED` | True | True (tests fetch a token) | True |
| `RATELIMIT_STORAGE_URI` | memory:// | memory:// (disabled except in rate-limit tests) | redis:// |
| `SCRYAPI_RATELIMIT_SEARCH` / `_AUTH` | 60/minute, 10/minute | same | tune per traffic |
| `SCRYAPI_PROXY_COUNT` | 0 | 0 | number of trusted proxies (enables `ProxyFix`) |
| `MAX_CONTENT_LENGTH` | 256 KB | 256 KB | 256 KB |
| `TEST_DATABASE_URL` | – | unset → in-memory SQLite; Postgres URL in CI | – |
| `SCRYAPI_DATA_DIR` | `<instance>/data` | tmp dir | volume path |

`create_app(config: type[BaseConfig] | None = None)` selects a config from
`SCRYAPI_ENV` (`development` | `testing` | `production`) unless one is passed in.
`ProdConfig.validate()` raises at startup when a required key is missing.

**Auth (session cookies):**
- Flask-Login. `user_loader` fetches by id. Unauthorised API access returns JSON 401
  (override `login_manager.unauthorized`), with no redirect.
- Passwords use `werkzeug.security.generate_password_hash` (scrypt) or argon2-cffi.
  Login always computes a hash, even for unknown users, so response timing doesn't reveal
  which accounts exist.
- On login, regenerate the session (`session.clear()` before `login_user`) to prevent
  session fixation.
- **CSRF:** Flask-WTF `CSRFProtect` covers POST/PUT/PATCH/DELETE. The client fetches a
  token from `GET /api/auth/csrf` and sends it as the `X-CSRFToken` header. Login and
  register rotate the session, so they return the new token in an `X-CSRFToken`
  response header. Tokens last as long as the session (`WTF_CSRF_TIME_LIMIT = None`).
- Ownership checks live in services (`decks.get_visible` / `decks.get_owned`). Someone
  else's private deck returns **404** for every method, so private decks can't be
  enumerated. Changing someone else's *public* deck returns **403**, since the deck is
  visible anyway. Anonymous mutations return **401**.
- SQLite connections run `PRAGMA foreign_keys=ON` (see `extensions.py`), so FK and
  cascade behaviour matches Postgres.
- Rate limits use Flask-Limiter: `/api/cards*` 60/min/IP and `/api/auth/login|register`
  10/min/IP.

## 9. API contract (v1)

All bodies are JSON. Errors look like this:

```json
{ "error": "validation_error", "message": "Invalid query parameters",
  "details": [{"field": "limit", "message": "must be between 1 and 50"}] }
```

Error codes: `validation_error` 400 · `csrf_failed` 400 · `unauthorized` 401 ·
`not_found` 404 · `conflict` 409 · `rate_limited` 429 · `internal_error` 500.

Paginated responses use `{ "page", "limit", "total", "results": [...] }`.

### Cards (public)
| Method | Path | Params / body | Response |
|---|---|---|---|
| GET | `/api/cards` | `name`, `type`, `text` (each ≤ 100 chars), `page` ≥ 1, `limit` 1–50 | paginated `Card` |
| GET | `/api/cards/<scryfall_id>` | | `Card` or 404 |

`Card` = `{id (scryfall_id), name, mana_cost, cmc, type_line, oracle_text, power, toughness, loyalty, colors, color_identity, layout, card_faces, image_uri, scryfall_uri}`

### Auth
| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/auth/csrf` | | `{csrf_token}` |
| POST | `/api/auth/register` | `{username, email, password}` | 201 `Me`; 409 on duplicate |
| POST | `/api/auth/login` | `{login (username or email), password, remember?}` | 200 `Me`; 401 generic message |
| POST | `/api/auth/logout` | | 204 |
| GET | `/api/auth/me` | | `Me` or 401 |

`Me` = `{username, email, created_at}`. `PublicUser` = `{username, created_at}`.

### Users (public)
| Method | Path | Response |
|---|---|---|
| GET | `/api/users/<username>` | `PublicUser` |
| GET | `/api/users/<username>/decks` | paginated `DeckSummary` (public only) |

### Decks
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/api/decks/public` | – | `page`, `limit` | paginated `DeckSummary`, most recently updated first |
| GET | `/api/decks/mine` | ✓ | `page`, `limit` | paginated `DeckSummary` |
| POST | `/api/decks` | ✓ | `{name, description?, format?, is_public?}` | 201 `Deck` |
| GET | `/api/decks/<id>` | owner, or anyone if public | | `Deck` |
| PATCH | `/api/decks/<id>` | owner | any of the create fields | `Deck` |
| DELETE | `/api/decks/<id>` | owner | | 204 |
| PUT | `/api/decks/<id>/cards` | owner | `{cards: [{card_id (scryfall_id), quantity, board? = "main"}]}` (replaces the full list) | `Deck` |

`DeckSummary` = `{id, name, format, is_public, owner (username), card_count, created_at, updated_at}`.
`Deck` = `DeckSummary + {description, cards: [{card: CardSummary, quantity, board}]}`. Cards
are ordered by main board first, then side, then by name.
`CardSummary` = `{id, name, mana_cost, type_line}`.

Replacing the full card list (PUT) rather than per-card endpoints keeps the client
simple and makes each edit atomic. Limits: at most 250 entries, quantity 1–99, with no
duplicate (card, board) pairs. Unknown card ids return 400 with per-entry details, and
the deck is left unchanged. Soft-deleted cards (`is_active=false`) stay in decks.

## 10. Testing strategy

- **Fixtures:** `app` (TestConfig), `client`, and `db` (schema created once per session
  via `flask db upgrade` against in-memory SQLite, each test in a rolled-back
  transaction). `cards_sample.json` is roughly 20 curated real cards, loaded through the
  real importer.
- **Layers:**
  - Unit: `normalise_card`, the FTS query builder, the LIKE escaper and the schema
    parsers.
  - Integration: services against the DB.
  - API: Flask test client, one file per blueprint.
- **Network:** `responses` runs in strict mode, so any unmocked HTTP call fails the test.
- **Required cases:** every acceptance bullet in AUDIT. Malformed search input
  (`"`, `AND`, `(`, `*`, unicode, 101 chars). Authorisation matrix (anonymous / owner /
  other user) for each deck route. CSRF missing → 400.
- **CI (M4):** GitHub Actions matrix `{sqlite, postgres:16}` running ruff, pytest and
  `--cov-fail-under=85`.

## 11. Migrations & deployment

- Flask-Migrate, with `migrations/` at the repo root. Each change gets one revision with
  a descriptive message. Search objects use dialect-conditional `op.execute()`:
  ```python
  if op.get_bind().dialect.name == "sqlite":
      op.execute("CREATE VIRTUAL TABLE ...")
  else:
      op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
      ...
  ```
- `env.py` `include_object` excludes any table whose name starts with `cards_fts`.
- Fresh environment: `flask db upgrade && flask sync-cards`. `db.create_all()` is never
  used outside tests.
- Prod runs `gunicorn 'scryapi:create_app()'`, with migrations as a release step and sync
  as a scheduled job (§7).

## 12. Milestones

| Milestone | AUDIT IDs | Exit criteria |
|---|---|---|
| **M0 Foundation** | Q1, Q3, Q6, S3, Q7 pt1, Q8 pt1 | Package installs. Tests run from the root with no network. README and CLAUDE.md are present. |
| **M1 Card catalogue** | C5, C4, S4, S5, E4, C7, C8, E1, E2, E3, E5, E6, C6+Q2, S6, S7 pt1, Q4 | `flask db upgrade && flask sync-cards --file tests/fixtures/cards_sample.json` works on SQLite **and** Postgres. Card API matches §9. Fuzzed search never returns 500. |
| **M2 Accounts** | S1, S2, C1 (users) | Auth endpoints as in §9 with CSRF. The serialiser allow-list is tested. |
| **M3 Decks & sharing** | C9, C1 (decks), C2, C3 | Deck endpoints as in §9 with the full authorisation matrix tested. |
| **M4 Hardening** | S7 pt2, Q7 pt2, Q8 pt2, Q5 | Rate limits, CI matrix green, coverage ≥ 85%, human review, first deploy. |

## 13. Alternatives considered

- **JWT bearer tokens instead of sessions.** Rejected by the owner for v1. Sessions are
  simpler to revoke and fit a same-origin frontend. Revisit if the PRD's open Q1 resolves
  to cross-origin clients.
- **Postgres everywhere, including dev and tests.** This gives the best parity but slows
  the agent feedback loop. Instead we keep SQLite as the default and run Postgres in the
  CI matrix.
- **Elasticsearch / Meilisearch.** Overkill for 35k documents. Database-native full-text
  search meets NFR-1.
- **In-process scheduler in every worker.** This is the current design and causes
  AUDIT C4 and C5. Replaced by a CLI command plus external cron.
- **Proxying Scryfall live.** That violates Scryfall's caching guidance and adds a hard
  runtime dependency.

## 14. Conventions for agent-driven development

- Each PR addresses the AUDIT IDs it names and ticks their boxes. It doesn't refactor
  outside its scope.
- Every behaviour change ships with tests. `ruff check`, `ruff format --check` and
  `pytest` must pass.
- No new dependency without updating `pyproject.toml` and noting why in the PR.
- Schema changes go through `flask db migrate -m "<message>"`, and the agent reviews the
  generated file. Autogenerate must never emit operations on `cards_fts*`.
- Anything not specified here is a decision for the human reviewer: flag it in the PR,
  don't invent it.
