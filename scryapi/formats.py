"""Deck formats: Scryfall's legality keys plus each format's construction rules.

`Deck.format` must be one of these keys (or null). Per-card legality comes from the
card's Scryfall `legalities`; the rest of each format's rules are described here and
enforced by scryapi/services/legality.py (docs/TDD.md §9, "Deck legality").
"""

from dataclasses import dataclass
from enum import StrEnum


class Kind(StrEnum):
    CONSTRUCTED = "constructed"  # 60+ main deck, 15-card sideboard, 4 copies
    SINGLETON = "singleton"  # exact size, 1 copy, no sideboard or commander
    COMMANDER = "commander"  # exact size including 1-2 commanders, singleton
    OATHBREAKER = "oathbreaker"  # exact size including a planeswalker + signature spell
    CARD_POOL = "card_pool"  # rules unknown to us: only per-card legality is checked


# What may lead a commander-kind deck (besides cards saying "can be your commander").
LEGENDARY_CREATURE = frozenset({"Creature"})
BRAWL_COMMANDER = frozenset({"Creature", "Planeswalker", "Vehicle", "Spacecraft"})


@dataclass(frozen=True)
class Format:
    key: str
    name: str
    kind: Kind
    deck_size: int | None = None  # exact size (singleton/commander kinds) or minimum
    sideboard_size: int = 0
    max_copies: int | None = None
    commander_types: frozenset[str] = frozenset()  # types a commander needs
    commander_must_be_legendary: bool = True


def _constructed(key: str, name: str) -> Format:
    return Format(key, name, Kind.CONSTRUCTED, deck_size=60, sideboard_size=15, max_copies=4)


def _commander(
    key: str,
    name: str,
    deck_size: int = 100,
    types: frozenset[str] = LEGENDARY_CREATURE,
    legendary: bool = True,
) -> Format:
    return Format(
        key,
        name,
        Kind.COMMANDER,
        deck_size=deck_size,
        max_copies=1,
        commander_types=types,
        commander_must_be_legendary=legendary,
    )


FORMATS = {
    f.key: f
    for f in (
        _constructed("standard", "Standard"),
        _constructed("future", "Future Standard"),
        _constructed("alchemy", "Alchemy"),
        _constructed("historic", "Historic"),
        _constructed("timeless", "Timeless"),
        _constructed("pioneer", "Pioneer"),
        _constructed("modern", "Modern"),
        _constructed("premodern", "Premodern"),
        _constructed("legacy", "Legacy"),
        _constructed("vintage", "Vintage"),
        _constructed("pauper", "Pauper"),
        _constructed("penny", "Penny Dreadful"),
        _constructed("oldschool", "Old School"),
        Format("gladiator", "Gladiator", Kind.SINGLETON, deck_size=100, max_copies=1),
        _commander("commander", "Commander"),
        _commander("duel", "Duel Commander"),
        _commander("predh", "PreDH"),
        # The commander must be an uncommon creature; we have no per-printing rarity, so
        # only "creature" is checked.
        _commander("paupercommander", "Pauper Commander", legendary=False),
        _commander("brawl", "Brawl", types=BRAWL_COMMANDER),
        _commander("competitivebrawl", "Competitive Brawl", types=BRAWL_COMMANDER),
        _commander("standardbrawl", "Standard Brawl", deck_size=60, types=BRAWL_COMMANDER),
        Format(
            "oathbreaker",
            "Oathbreaker",
            Kind.OATHBREAKER,
            deck_size=60,
            max_copies=1,
            commander_types=frozenset({"Planeswalker"}),
            commander_must_be_legendary=False,
        ),
        # Listed by Scryfall without published rules we could confirm.
        Format("tlr", "TLR", Kind.CARD_POOL),
    )
}
