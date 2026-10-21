# PRD — scryapi

- **Status:** v0.3 (2026-10-20). M0–M5 are implemented. Items marked **[OPEN]** need the owner's input. See the hand-off list in [AUDIT](AUDIT.md).
- **Owner:** Hiu Chan
- **Companion docs:** [TDD](TDD.md) · [AUDIT](AUDIT.md)

## 1. Summary

scryapi is a JSON REST API for searching Magic: The Gathering cards and managing
decklists. It keeps a local mirror of Scryfall's Oracle card data, refreshed
automatically, so search is fast and does not depend on Scryfall at request time. Users
can register, build decks from the catalogue, and optionally share decks publicly.

## 2. Problem & motivation

- Scryfall's public API is excellent but rate-limited and asks clients to cache. Apps
  that search heavily, or need their own data (decks, users), need a local store.
- Building decks requires joining card data with user-owned data, which Scryfall does
  not provide.
- Secondary goal: a well-engineered portfolio-quality Flask service (clean layering,
  tests, migrations, Postgres in production).

## 3. Users

| Persona | Needs |
|---|---|
| **Anonymous visitor / client app** | Search cards by name, type, rules text; view a card; browse public decks. |
| **Registered deck builder** | Everything above + create, edit, delete own decks; mark decks public/private. |
| **Operator (owner)** | Deploy, keep card data fresh with no manual steps, observe sync health. |

## 4. Goals

1. **G1 — Card search:** Search the full Oracle catalogue (~35k cards) by name, type
   line, and rules text, with pagination.
2. **G2 — Fresh data:** Catalogue stays within 7 days of Scryfall's Oracle bulk data
   with zero manual intervention, including errata to existing cards.
3. **G3 — Accounts:** Users can register, log in, and log out securely.
4. **G4 — Decks:** Authenticated users can manage decks (name, description, format,
   card + quantity, main/sideboard) and choose visibility.
5. **G5 — Sharing:** Anyone can view public decks and a user's public profile.

## 5. Non-goals (v1)

- Card prices, printings/sets, images hosting (link to Scryfall image URIs instead).
- Social features (likes, comments, follows).
- A frontend. The API is consumed by a separate browser client, same-origin or not
  (decided 2026-10-20: configurable, see TDD §8).
- OAuth / third-party login, password reset by email, email verification (decided
  2026-10-20: not in v1).
- Admin UI.

## 6. Functional requirements

### Cards
- **FR-C1** List/search cards with filters: `name` (substring, case-insensitive),
  `type` (substring), `text` (full-text over rules text). Filters combine with AND.
- **FR-C2** Pagination: `page` ≥ 1, `limit` 1–50 (default 20). Invalid values return
  400 with a field-level message, not silent defaults.
- **FR-C3** Results sorted by name ascending. When filtering by `name`, exact name
  matches come first, then names starting with the term, then the rest (each group by name).
- **FR-C4** Get a single card by stable Scryfall ID.
- **FR-C5** Multi-face cards (transform, MDFC, split, adventure) are searchable by all
  faces' text and expose face details.
- **FR-C6** Any user input — including malformed search syntax — never produces a 500.

### Data sync
- **FR-S1** Weekly (configurable) sync from Scryfall `oracle_cards` bulk data.
- **FR-S2** Sync updates changed cards and inserts new ones.
- **FR-S3** Manual trigger via CLI for the operator.
- **FR-S4** A failed sync leaves the existing catalogue intact and serving.
- **FR-S5** Sync respects Scryfall's API guidelines (User-Agent, rate limits).

### Accounts
- **FR-A1** Register with username, email, password (12–128 characters).
- **FR-A2** Log in / log out; session cookie auth.
- **FR-A3** `me` endpoint returns the current user.
- **FR-A5** Change password (requires the current one). This signs out every other
  session, including remember-me cookies.
- **FR-A4** Public profile by username exposes username and public decks only — never email.

### Decks
- **FR-D1** CRUD on own decks.
- **FR-D2** Add/remove/set quantity of cards: main, sideboard or commander.
- **FR-D3** Visibility flag; private decks are invisible (404) to others.
- **FR-D4** Browse recent public decks; list a user's public decks.
- **FR-D5** A deck's format is one of Scryfall's formats. Viewing a deck reports whether
  it's legal in that format and lists every problem (banned or illegal cards, copy
  limits, deck size, commander and color identity). Illegal decks still save.

## 7. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | p95 latency < 200 ms for card search on prod hardware with full catalogue. |
| NFR-2 | App boot performs no network I/O; boots even if Scryfall is down. |
| NFR-3 | Passwords hashed with a modern KDF; cookies `HttpOnly`/`Secure`/`SameSite`; CSRF protection on mutations. |
| NFR-4 | All responses JSON, including errors, with a consistent error envelope. |
| NFR-5 | Rate limiting on search and auth endpoints. |
| NFR-6 | Runs on SQLite (dev/test) and Postgres (prod) from one codebase; schema managed by migrations. |
| NFR-7 | ≥ 85% test coverage; CI on both databases. |
| NFR-8 | Respect Scryfall's terms: attribute data, don't present it as first-party. |

## 8. Success metrics

- Sync success rate ≥ 99% of scheduled runs; data age never > 8 days.
- Zero 5xx responses caused by client input (tracked in logs).
- Search p95 latency meets NFR-1.
- All AUDIT P0/P1 items closed before first public deployment.

## 9. Milestones

Mirrors [AUDIT](AUDIT.md) milestones; details in [TDD §12](TDD.md#12-milestones).

| Milestone | Outcome |
|---|---|
| M0 Foundation | Installable package, config, test harness, docs. |
| M1 Card catalogue | G1, G2 complete and robust; works on Postgres. |
| M2 Accounts | G3. |
| M3 Decks & sharing | G4, G5. |
| M4 Hardening | Rate limits, CI matrix, typing; human review pass; first deployment. |

## 10. Open questions

1. **Decided 2026-10-20:** frontend origin still unknown, so CORS and cookie SameSite are
   configuration (`SCRYAPI_CORS_ORIGINS`, `SCRYAPI_COOKIE_SAMESITE`), not code.
2. **Decided 2026-10-20:** keep 12–128 characters, add change-password, no email reset
   or verification in v1.
3. **Decided 2026-10-20:** full deck legality in v1, reported rather than enforced (FR-D5).
4. **[OPEN]** Hosting target (Fly.io / Render / VPS) — affects how the sync job is scheduled (TDD §7).
5. **[OPEN]** Should cards removed from Scryfall's Oracle file be deleted, or soft-deleted to protect existing decks? (TDD assumes soft-delete.)
