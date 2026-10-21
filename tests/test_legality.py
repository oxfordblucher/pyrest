"""Deck legality (AUDIT L1/L2): the rules engine with synthetic cards, then the API."""

import json
from itertools import count
from types import SimpleNamespace

import pytest

from scryapi.formats import FORMATS
from scryapi.models.card import name_key
from scryapi.services.legality import check_deck
from tests.conftest import CARDS_SAMPLE

_ids = count(1)


def card(name, type_line="Instant", text="", colors=(), **statuses):
    legalities = {key: "legal" for key in FORMATS} | statuses
    return SimpleNamespace(
        id=next(_ids),
        scryfall_id=f"id-{name}",
        name=name,
        sort_name=name_key(name),
        type_line=type_line,
        oracle_text=text,
        color_identity=list(colors),
        legalities=legalities,
    )


def entry(card_, quantity=1, board="main"):
    return SimpleNamespace(card=card_, quantity=quantity, board=board)


def codes(report):
    return [p["code"] for p in report["problems"]]


FOREST = card("Forest", "Basic Land — Forest", colors="G")
WASTES = card("Wastes", "Basic Land")
BOLT = card("Lightning Bolt", colors="R")
KINNAN = card("Kinnan", "Legendary Creature — Human Druid", colors="GU")


def forests(n):
    return entry(FOREST, n)


# --- general -------------------------------------------------------------------------


def test_no_format_means_no_report():
    assert check_deck(None, [entry(BOLT)]) is None


def test_unknown_format_is_reported():
    assert codes(check_deck("kitchen", [])) == ["unknown_format"]


def test_report_shape():
    report = check_deck("modern", [forests(56), entry(BOLT, 4)])
    assert report == {"format": "modern", "legal": True, "problems": []}


def test_problem_names_the_card():
    report = check_deck("modern", [forests(60), entry(card("Probe", modern="banned"))])
    assert report["problems"] == [
        {
            "code": "banned",
            "message": "Probe is banned in Modern",
            "card": {"id": "id-Probe", "name": "Probe"},
        }
    ]


def test_cards_without_imported_legalities_are_not_flagged():
    unknown = card("Fresh")
    unknown.legalities = None
    assert check_deck("modern", [forests(59), entry(unknown)])["legal"]


# --- constructed -----------------------------------------------------------------------


def test_constructed_minimum_size():
    assert codes(check_deck("modern", [forests(59)])) == ["deck_too_small"]


def test_constructed_sideboard_limit():
    report = check_deck("modern", [forests(60), entry(FOREST, 16, "side")])
    assert codes(report) == ["sideboard_too_large"]


def test_four_copy_limit_counts_main_and_side():
    report = check_deck("modern", [forests(57), entry(BOLT, 3), entry(BOLT, 2, "side")])
    assert codes(report) == ["too_many_copies"]
    assert report["problems"][0]["message"] == "Modern allows 4 copies of Lightning Bolt (has 5)"


@pytest.mark.parametrize(
    "status,code", [("banned", "banned"), ("not_legal", "not_legal"), ("legal", None)]
)
def test_card_status(status, code):
    report = check_deck("modern", [forests(59), entry(card("X", modern=status))])
    assert codes(report) == ([code] if code else [])


def test_vintage_restricted_list():
    sol_ring = card("Sol Ring", "Artifact", vintage="restricted")
    assert check_deck("vintage", [forests(59), entry(sol_ring)])["legal"]
    report = check_deck("vintage", [forests(58), entry(sol_ring, 2)])
    assert report["problems"][0]["message"] == "Vintage allows 1 copy of Sol Ring (has 2)"


def test_basic_lands_are_unlimited():
    snow = card("Snow-Covered Forest", "Basic Snow Land — Forest", colors="G")
    assert check_deck("modern", [entry(snow, 60)])["legal"]


def test_any_number_cards_are_unlimited():
    rats = card("Relentless Rats", "Creature — Rat", "A deck can have any number of cards named")
    assert check_deck("modern", [forests(30), entry(rats, 30)])["legal"]


def test_up_to_n_cards():
    dwarves = card("Seven Dwarves", "Creature — Dwarf", "A deck can have up to seven cards named")
    assert check_deck("modern", [forests(53), entry(dwarves, 7)])["legal"]
    assert codes(check_deck("modern", [forests(52), entry(dwarves, 8)])) == ["too_many_copies"]


def test_constructed_has_no_commander():
    report = check_deck("modern", [forests(60), entry(KINNAN, board="commander")])
    assert codes(report) == ["commander_not_allowed"]


# --- singleton (gladiator) -----------------------------------------------------------


def test_gladiator():
    assert check_deck("gladiator", [forests(99), entry(BOLT)])["legal"]
    assert codes(check_deck("gladiator", [forests(98), entry(BOLT, 2)])) == ["too_many_copies"]
    report = check_deck("gladiator", [forests(100), entry(BOLT, board="side")])
    assert codes(report) == ["sideboard_not_allowed"]
    assert codes(check_deck("gladiator", [forests(98)])) == ["deck_wrong_size"]


# --- commander -----------------------------------------------------------------------


def commander_deck(*leaders, main=None):
    """Leaders plus colorless basics up to 100 cards, unless `main` is given."""
    main = main if main is not None else [entry(WASTES, 100 - len(leaders))]
    return [entry(c, board="commander") for c in leaders] + main


def test_legal_commander_deck():
    assert check_deck("commander", commander_deck(KINNAN))["legal"]


def test_commander_deck_size_includes_commander():
    report = check_deck("commander", commander_deck(KINNAN, main=[forests(100)]))
    assert codes(report) == ["deck_wrong_size"]
    assert "exactly 100 cards including the commander (has 101)" in report["problems"][0]["message"]


def test_commander_singleton():
    deck = commander_deck(KINNAN, main=[forests(97), entry(card("Elves", colors="G"), 2)])
    assert codes(check_deck("commander", deck)) == ["too_many_copies"]


def test_commander_missing():
    assert codes(check_deck("commander", [forests(100)])) == ["commander_missing"]


def test_too_many_commanders():
    deck = commander_deck(
        KINNAN, KINNAN_2 := card("K2", "Legendary Creature"), card("K3", "Legendary Creature")
    )
    assert "too_many_commanders" in codes(check_deck("commander", deck))
    assert KINNAN_2


def test_non_legendary_commander():
    elf = card("Llanowar Elves", "Creature — Elf Druid", colors="G")
    assert codes(check_deck("commander", commander_deck(elf))) == ["invalid_commander"]


def test_can_be_your_commander_text():
    teferi = card(
        "Teferi", "Legendary Planeswalker — Teferi", "Teferi can be your commander.", colors="U"
    )
    assert check_deck("commander", commander_deck(teferi))["legal"]


def test_planeswalker_commander_only_in_brawl():
    jace = card("Jace", "Legendary Planeswalker — Jace", colors="U")
    assert codes(check_deck("commander", commander_deck(jace))) == ["invalid_commander"]
    assert check_deck("brawl", commander_deck(jace))["legal"]


def test_standard_brawl_is_60_cards():
    assert check_deck("standardbrawl", commander_deck(KINNAN, main=[forests(59)]))["legal"]


def test_pauper_commander_allows_non_legendary_creature():
    elf = card("Llanowar Elves", "Creature — Elf Druid", colors="G")
    assert check_deck("paupercommander", commander_deck(elf))["legal"]


def test_restricted_in_duel_means_not_as_commander():
    banned_leader = card("Oko", "Legendary Creature — Elf", colors="G", duel="restricted")
    report = check_deck("duel", commander_deck(banned_leader))
    assert codes(report) == ["invalid_commander"]
    assert report["problems"][0]["message"] == "Oko can't be a commander in Duel Commander"
    # ...but it may still be played in the 99.
    assert check_deck("duel", commander_deck(KINNAN, main=[forests(98), entry(banned_leader)]))[
        "legal"
    ]


def test_color_identity():
    deck = commander_deck(KINNAN, main=[forests(98), entry(BOLT)])
    report = check_deck("commander", deck)
    assert codes(report) == ["color_identity"]
    assert report["problems"][0]["card"]["name"] == "Lightning Bolt"


def test_colorless_commander_allows_only_colorless_cards():
    emrakul = card("Emrakul", "Legendary Creature — Eldrazi")
    wastes = card("Wastes", "Basic Land")
    assert check_deck("commander", commander_deck(emrakul, main=[entry(wastes, 99)]))["legal"]
    assert "color_identity" in codes(
        check_deck("commander", commander_deck(emrakul, main=[forests(99)]))
    )


def legend(name, text, colors, type_line="Legendary Creature — Human"):
    return card(name, type_line, text, colors=colors)


@pytest.mark.parametrize(
    "a,b,ok",
    [
        (legend("A", "Partner (reminder)", "W"), legend("B", "Partner", "U"), True),
        (legend("A", "Partner", "W"), legend("B", "Flying", "U"), False),
        (
            legend("A", "Partner—Friends forever (reminder)", "W"),
            legend("B", "Partner—Friends forever", "U"),
            True,
        ),
        (legend("A", "Partner—Survivors", "W"), legend("B", "Partner—Father & son", "U"), False),
        (
            legend("Will", "Partner with Rowan", "U"),
            legend("Rowan", "Partner with Will", "R"),
            True,
        ),
        (legend("Will", "Partner with Rowan", "U"), legend("Bob", "Partner with Will", "R"), False),
        (
            legend("Wilson", "Choose a Background (reminder)", "G"),
            legend("Acolyte", "", "B", "Legendary Enchantment — Background"),
            True,
        ),
        (
            legend("Rose", "Doctor's companion", "W"),
            legend("Thirteenth", "", "U", "Legendary Creature — Time Lord Doctor"),
            True,
        ),
    ],
)
def test_partners(a, b, ok):
    report = check_deck("commander", commander_deck(a, b))
    assert codes(report) == ([] if ok else ["invalid_partners"])


def test_partner_color_identity_is_combined():
    a, b = legend("A", "Partner", "W"), legend("B", "Partner", "R")
    assert check_deck("commander", commander_deck(a, b, main=[forests(97), entry(BOLT)])) == {
        "format": "commander",
        "legal": False,
        "problems": [
            {
                "code": "color_identity",
                "message": "Forest is outside the commander's color identity",
                "card": {"id": "id-Forest", "name": "Forest"},
            }
        ],
    }


# --- oathbreaker -----------------------------------------------------------------------


def test_oathbreaker():
    jace = card("Jace", "Legendary Planeswalker — Jace", colors="U")
    brainstorm = card("Brainstorm", "Instant", colors="U")
    islands = entry(card("Island", "Basic Land — Island", colors="U"), 58)
    deck = [entry(jace, board="commander"), entry(brainstorm, board="commander"), islands]
    assert check_deck("oathbreaker", deck)["legal"]

    no_walker = [entry(brainstorm, board="commander"), entry(islands.card, 59)]
    assert codes(check_deck("oathbreaker", no_walker)) == ["commander_missing"]

    off_color = [entry(jace, board="commander"), entry(BOLT, board="commander"), islands]
    assert codes(check_deck("oathbreaker", off_color)) == ["color_identity"]


# --- card pool only ------------------------------------------------------------------


def test_card_pool_format_checks_only_card_legality():
    assert check_deck("tlr", [entry(BOLT, 9)])["legal"]
    assert codes(check_deck("tlr", [entry(card("X", tlr="banned"))])) == ["banned"]


# --- API -------------------------------------------------------------------------------

SAMPLE = {c["name"]: c["id"] for c in json.loads(CARDS_SAMPLE.read_text())}

pytestmark = pytest.mark.usefixtures("cards")


def test_list_formats(client):
    formats = {f["key"]: f for f in client.get("/api/formats").get_json()["results"]}
    assert set(formats) == set(FORMATS)
    assert formats["commander"] == {
        "key": "commander",
        "name": "Commander",
        "kind": "commander",
        "deck_size": 100,
        "sideboard_size": 0,
        "max_copies": 1,
    }


def test_format_is_normalised(alice):
    deck = alice.post("/api/decks", json={"name": "Burn", "format": " Modern "}).get_json()
    assert deck["format"] == "modern"


def test_deck_without_format_has_no_legality(alice):
    assert alice.post("/api/decks", json={"name": "Burn"}).get_json()["legality"] is None


def test_modern_deck_legality(alice):
    deck = alice.post("/api/decks", json={"name": "Burn", "format": "modern"}).get_json()
    cards = [
        {"card_id": SAMPLE["Lightning Bolt"], "quantity": 4},
        {"card_id": SAMPLE["Gitaxian Probe"], "quantity": 1},
    ]
    resp = alice.put(f"/api/decks/{deck['id']}/cards", json={"cards": cards})
    assert resp.status_code == 200  # report, don't block
    assert codes(resp.get_json()["legality"]) == ["deck_too_small", "banned"]


def test_commander_deck_via_api(alice, anon):
    deck = alice.post(
        "/api/decks", json={"name": "Kinnan", "format": "commander", "is_public": True}
    ).get_json()
    cards = [
        {"card_id": SAMPLE["Kinnan, Bonder Prodigy"], "quantity": 1, "board": "commander"},
        {"card_id": SAMPLE["Forest"], "quantity": 97},
        {"card_id": SAMPLE["Lightning Bolt"], "quantity": 1},
        {"card_id": SAMPLE["Emrakul, the Aeons Torn"], "quantity": 1},
    ]
    resp = alice.put(f"/api/decks/{deck['id']}/cards", json={"cards": cards})
    body = resp.get_json()
    assert [c["board"] for c in body["cards"]][0] == "commander"  # listed first
    assert codes(body["legality"]) == ["banned", "color_identity"]
    assert anon.get(f"/api/decks/{deck['id']}").get_json()["legality"] == body["legality"]


def test_changing_format_changes_the_report(alice):
    deck = alice.post("/api/decks", json={"name": "Rings", "format": "vintage"}).get_json()
    cards = [
        {"card_id": SAMPLE["Sol Ring"], "quantity": 2},
        {"card_id": SAMPLE["Forest"], "quantity": 58},
    ]
    body = alice.put(f"/api/decks/{deck['id']}/cards", json={"cards": cards}).get_json()
    assert codes(body["legality"]) == ["too_many_copies"]  # restricted in Vintage
    body = alice.patch(f"/api/decks/{deck['id']}", json={"format": "modern"}).get_json()
    assert codes(body["legality"]) == ["not_legal"]  # 2 copies are fine; the card isn't
