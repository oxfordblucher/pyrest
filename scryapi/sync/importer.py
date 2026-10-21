import gzip
import json
import logging
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import batched
from pathlib import Path
from typing import Any

from sqlalchemy.dialects import postgresql, sqlite

from scryapi.extensions import db
from scryapi.models import Card
from scryapi.search import get_backend
from scryapi.services.decks import remove_inactive_cards
from scryapi.sync.download import SyncError
from scryapi.sync.normalise import RawCard, normalise_card, should_import

logger = logging.getLogger(__name__)

# 500 rows x ~17 columns stays well under SQLite's and Postgres's bound-parameter limits.
BATCH_SIZE = 500

# Removed cards are deleted from decks, which can't be undone, so an import that would
# drop more than this share of the catalogue (and more than MIN_GUARDED_DROPS cards) is
# refused unless explicitly allowed: it's far more likely a bad or wrong file than a
# real Scryfall change, which is a handful of cards at a time.
MAX_DROPPED_FRACTION = 0.02
MIN_GUARDED_DROPS = 50

# Dialect inserts with ON CONFLICT support; the generic sqlalchemy.insert has none.
_INSERTS: dict[str, Callable[..., Any]] = {"sqlite": sqlite.insert, "postgresql": postgresql.insert}


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: int
    dropped: int = 0  # cards that were active before this import and aren't now
    decks_changed: int = 0  # decks those cards were removed from


def iter_cards(path: str | Path) -> Iterator[RawCard]:
    """Stream card objects from a `.jsonl` / `.jsonl.gz` file, or a small `.json` array."""
    path = str(path)
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            yield from json.load(f)
        return
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def upsert_cards(rows: list[dict[str, Any]]) -> None:
    insert = _INSERTS[db.engine.dialect.name]
    stmt = insert(Card).values(rows)
    updatable = {c: stmt.excluded[c] for c in rows[0] if c != "scryfall_id"}
    stmt = stmt.on_conflict_do_update(index_elements=["scryfall_id"], set_=updatable)
    db.session.execute(stmt)


def import_cards(raw_cards: Iterable[RawCard], allow_removals: bool = False) -> ImportResult:
    """Upsert cards; cards not present in `raw_cards` are deactivated and removed from
    every deck, and the decks' owners are notified (PRD FR-S6).

    Runs inside the caller's transaction and does not commit; on error the caller rolls
    back and the existing catalogue and decks are untouched.
    """
    now = datetime.now(UTC)
    imported = skipped = 0
    active_before = set(db.session.execute(db.select(Card.id).where(Card.is_active)).scalars())

    # Everything starts inactive; cards present in this import are re-activated by the
    # upsert. Cards dropped by Scryfall stay in the catalogue, hidden, so their ids stay
    # stable if Scryfall brings them back.
    db.session.execute(db.update(Card).values(is_active=False))

    for batch in batched(raw_cards, BATCH_SIZE):
        rows = []
        for raw in batch:
            if should_import(raw):
                rows.append({**normalise_card(raw), "is_active": True, "updated_at": now})
            else:
                skipped += 1
        if rows:
            upsert_cards(rows)
            imported += len(rows)

    inactive = set(db.session.execute(db.select(Card.id).where(~Card.is_active)).scalars())
    dropped = len(active_before & inactive)
    if (
        not allow_removals
        and dropped > MIN_GUARDED_DROPS
        and dropped > MAX_DROPPED_FRACTION * len(active_before)
    ):
        raise SyncError(
            f"Import would remove {dropped} of {len(active_before)} cards; refusing. If "
            "this is intended, rerun with --allow-removals."
        )

    decks_changed = remove_inactive_cards()
    get_backend().rebuild()
    logger.info(
        "Imported %d cards (%d skipped); %d dropped, removed from %d decks",
        imported, skipped, dropped, decks_changed,
    )  # fmt: skip
    return ImportResult(
        imported=imported, skipped=skipped, dropped=dropped, decks_changed=decks_changed
    )
