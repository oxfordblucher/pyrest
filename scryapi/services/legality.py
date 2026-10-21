"""Deck legality report (AUDIT L2, docs/TDD.md §9 "Deck legality").

Report, don't block: decks are built a few cards at a time, so an illegal deck still
saves and this report is returned alongside it. Everything here is a pure function of
the deck's format and entries (objects with `card`, `quantity` and `board`).
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from scryapi.formats import FORMATS, Format, Kind

ANY_NUMBER_RE = re.compile(r"A deck can have any number of cards named")
UP_TO_RE = re.compile(r"A deck can have up to (\w+) cards named")
NUMBER_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10,
}  # fmt: skip
# "Partner", "Partner—Friends forever", "Partner with Ley Weaver" (reminder text follows)
PARTNER_RE = re.compile(
    r"^Partner(?:—(?P<group>[^(\n]+?)| with (?P<with>[^(\n]+?))?\s*(?:\(|$)", re.MULTILINE
)
CAN_BE_COMMANDER = "can be your commander"

type Report = dict[str, Any]
type Boards = defaultdict[str, list["EntryLike"]]


class CardLike(Protocol):
    """The Card attributes the rules read (scryapi.models.Card satisfies it)."""

    @property
    def id(self) -> int: ...
    @property
    def scryfall_id(self) -> str: ...
    @property
    def name(self) -> str: ...
    @property
    def sort_name(self) -> str: ...
    @property
    def type_line(self) -> str | None: ...
    @property
    def oracle_text(self) -> str | None: ...
    @property
    def color_identity(self) -> list[str] | None: ...
    @property
    def legalities(self) -> dict[str, str] | None: ...


class EntryLike(Protocol):
    """A deck entry (scryapi.models.DeckCard satisfies it)."""

    @property
    def card(self) -> CardLike: ...
    @property
    def quantity(self) -> int: ...
    @property
    def board(self) -> str: ...


# --- card facts ----------------------------------------------------------------------


def _front_type_line(card: CardLike) -> str:
    return (card.type_line or "").split(" // ")[0]


def _supertypes(card: CardLike) -> set[str]:
    return set(_front_type_line(card).split("—")[0].split())


def _type_words(card: CardLike) -> set[str]:
    return set(_front_type_line(card).replace("—", " ").split())


def _text(card: CardLike) -> str:
    return card.oracle_text or ""


def is_basic(card: CardLike) -> bool:
    return "Basic" in _supertypes(card)


def copy_limit(card: CardLike, default: int | None) -> int | None:
    """How many copies a deck may hold: None means unlimited."""
    if is_basic(card) or ANY_NUMBER_RE.search(_text(card)):
        return None
    if match := UP_TO_RE.search(_text(card)):
        return NUMBER_WORDS.get(match.group(1).lower(), default)
    return default


def _partner_tags(card: CardLike) -> set[tuple[str, ...]]:
    tags: set[tuple[str, ...]] = set()
    for match in PARTNER_RE.finditer(_text(card)):
        if match.group("group"):
            tags.add(("group", match.group("group").strip()))
        elif match.group("with"):
            tags.add(("with", match.group("with").strip()))
        else:
            tags.add(("plain",))
    return tags


def _pairs_with(a: CardLike, b: CardLike) -> bool:
    """True if `a` and `b` may lead a deck together."""
    ta, tb = _partner_tags(a), _partner_tags(b)
    if ("plain",) in ta and ("plain",) in tb:
        return True
    if any(tag[0] == "group" for tag in ta & tb):
        return True
    if ("with", b.name) in ta and ("with", a.name) in tb:
        return True
    for x, y in ((a, b), (b, a)):
        if "Choose a Background" in _text(x) and "Background" in _type_words(y):
            return True
        if "Doctor's companion" in _text(x) and {"Time", "Lord", "Doctor"} <= _type_words(y):
            return True
    return False


def _can_lead(card: CardLike, fmt: Format) -> bool:
    if CAN_BE_COMMANDER in _text(card):
        return True
    if fmt.commander_must_be_legendary and "Legendary" not in _supertypes(card):
        return False
    return bool(fmt.commander_types & _type_words(card))


# --- report ----------------------------------------------------------------------------


def _card_ref(card: CardLike) -> dict[str, str]:
    return {"id": card.scryfall_id, "name": card.name}


class _Report:
    def __init__(self, fmt: Format) -> None:
        self.fmt = fmt
        self.problems: list[dict[str, Any]] = []

    def add(self, code: str, message: str, card: CardLike | None = None) -> None:
        problem: dict[str, Any] = {"code": code, "message": message}
        if card is not None:
            problem["card"] = _card_ref(card)
        self.problems.append(problem)


def check_deck(format_key: str | None, entries: Sequence[EntryLike]) -> Report | None:
    """Return `{format, legal, problems}` for a deck, or None if it has no format."""
    if format_key is None:
        return None
    fmt = FORMATS.get(format_key)
    if fmt is None:
        problem = {"code": "unknown_format", "message": f"Unknown format {format_key!r}"}
        return {"format": format_key, "legal": False, "problems": [problem]}

    report = _Report(fmt)
    boards: Boards = defaultdict(list)
    for entry in entries:
        boards[entry.board].append(entry)
    count = {board: sum(e.quantity for e in items) for board, items in boards.items()}

    _check_structure(report, boards, count)
    _check_cards(report, entries)
    if fmt.kind is Kind.COMMANDER:
        _check_commanders(report, boards)
    elif fmt.kind is Kind.OATHBREAKER:
        _check_oathbreaker(report, boards)

    return {"format": fmt.key, "legal": not report.problems, "problems": report.problems}


def _check_structure(report: _Report, boards: Boards, count: dict[str, int]) -> None:
    fmt = report.fmt
    main, side, commanders = (count.get(b, 0) for b in ("main", "side", "commander"))
    if fmt.kind is Kind.CARD_POOL:
        return
    assert fmt.deck_size is not None  # every other kind has a size rule
    if fmt.kind is Kind.CONSTRUCTED:
        if main < fmt.deck_size:
            report.add(
                "deck_too_small",
                f"{fmt.name} decks need at least {fmt.deck_size} main-deck cards (has {main})",
            )
        if side > fmt.sideboard_size:
            report.add(
                "sideboard_too_large",
                f"{fmt.name} sideboards hold at most {fmt.sideboard_size} cards (has {side})",
            )
    else:
        size = main + commanders
        if size != fmt.deck_size:
            including = " including the commander" if fmt.kind is not Kind.SINGLETON else ""
            report.add(
                "deck_wrong_size",
                f"{fmt.name} decks have exactly {fmt.deck_size} cards{including} (has {size})",
            )
        if side:
            report.add("sideboard_not_allowed", f"{fmt.name} decks don't use a sideboard")
    if commanders and fmt.kind in (Kind.CONSTRUCTED, Kind.SINGLETON):
        report.add("commander_not_allowed", f"{fmt.name} decks don't have a commander")


def _check_cards(report: _Report, entries: Sequence[EntryLike]) -> None:
    fmt = report.fmt
    totals: dict[int, tuple[CardLike, int]] = {}
    for entry in entries:
        card, quantity = entry.card, entry.quantity
        totals[card.id] = (card, totals.get(card.id, (card, 0))[1] + quantity)

    for card, quantity in sorted(totals.values(), key=lambda pair: pair[0].sort_name):
        status = (card.legalities or {}).get(fmt.key)  # None: legalities not imported yet
        if status == "banned":
            report.add("banned", f"{card.name} is banned in {fmt.name}", card)
        elif status == "not_legal":
            report.add("not_legal", f"{card.name} is not legal in {fmt.name}", card)

        limit = copy_limit(card, fmt.max_copies)
        if status == "restricted" and fmt.kind in (Kind.CONSTRUCTED, Kind.CARD_POOL):
            limit = 1
        if limit is not None and quantity > limit:
            report.add(
                "too_many_copies",
                f"{fmt.name} allows {limit} {'copy' if limit == 1 else 'copies'} of "
                f"{card.name} (has {quantity})",
                card,
            )


def _check_color_identity(
    report: _Report, leaders: Iterable[CardLike], cards: Iterable[CardLike]
) -> None:
    allowed = {color for leader in leaders for color in leader.color_identity or []}
    for card in sorted(cards, key=lambda c: c.sort_name):
        if not set(card.color_identity or []) <= allowed:
            report.add(
                "color_identity",
                f"{card.name} is outside the commander's color identity",
                card,
            )


def _check_commanders(report: _Report, boards: Boards) -> None:
    fmt = report.fmt
    commanders = [e.card for e in boards["commander"]]
    if not commanders:
        report.add("commander_missing", f"{fmt.name} decks need a commander")
        return
    if len(commanders) > 2:
        report.add("too_many_commanders", "A deck has at most two commanders")
        return

    paired = len(commanders) == 2 and _pairs_with(*commanders)
    if len(commanders) == 2 and not paired:
        names = " and ".join(c.name for c in commanders)
        report.add("invalid_partners", f"{names} can't be commanders together")
    for card in commanders:
        background = paired and "Background" in _type_words(card)
        if (card.legalities or {}).get(fmt.key) == "restricted":
            report.add("invalid_commander", f"{card.name} can't be a commander in {fmt.name}", card)
        elif not (background or _can_lead(card, fmt)):
            report.add("invalid_commander", f"{card.name} can't be a commander", card)

    _check_color_identity(report, commanders, [e.card for e in boards["main"]])


def _check_oathbreaker(report: _Report, boards: Boards) -> None:
    leaders = [e.card for e in boards["commander"]]
    walkers = [c for c in leaders if "Planeswalker" in _type_words(c)]
    spells = [c for c in leaders if {"Instant", "Sorcery"} & _type_words(c)]
    if len(walkers) != 1:
        report.add(
            "commander_missing" if not walkers else "too_many_commanders",
            "Oathbreaker decks need exactly one planeswalker as their oathbreaker",
        )
    if len(spells) > 1:
        report.add("too_many_commanders", "Oathbreaker decks have one signature spell")
    for card in leaders:
        if card not in walkers and card not in spells:
            report.add(
                "invalid_commander",
                f"{card.name} can't be an oathbreaker or signature spell",
                card,
            )
    if len(walkers) == 1:
        _check_color_identity(report, walkers, spells + [e.card for e in boards["main"]])
