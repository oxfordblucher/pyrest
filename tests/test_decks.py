import json

import pytest

from scryapi.models import Card, Deck, DeckCard, User
from tests.conftest import CARDS_SAMPLE

SAMPLE = {c["name"]: c["id"] for c in json.loads(CARDS_SAMPLE.read_text())}
BOLT = SAMPLE["Lightning Bolt"]
COUNTERSPELL = SAMPLE["Counterspell"]
FOREST = SAMPLE["Forest"]

SUMMARY_KEYS = {
    "id", "name", "format", "is_public", "owner", "card_count", "created_at", "updated_at",
}  # fmt: skip

pytestmark = pytest.mark.usefixtures("cards")


def make_deck(client, **fields):
    resp = client.post("/api/decks", json={"name": "Burn", **fields})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def set_cards(client, deck_id, cards):
    return client.put(f"/api/decks/{deck_id}/cards", json={"cards": cards})


# --- create / read ---------------------------------------------------------------------


def test_create_deck(alice):
    deck = make_deck(alice, description="Go face", format="modern", is_public=True)
    assert set(deck) == SUMMARY_KEYS | {"description", "cards"}
    assert deck["owner"] == "alice"
    assert deck["cards"] == [] and deck["card_count"] == 0
    assert (deck["description"], deck["format"], deck["is_public"]) == (
        "Go face",
        "modern",
        True,
    )


def test_decks_default_to_private(alice):
    assert make_deck(alice)["is_public"] is False


def test_create_requires_auth(anon):
    resp = anon.post("/api/decks", json={"name": "Burn"})
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "body,field",
    [
        ({}, "name"),
        ({"name": "   "}, "name"),
        ({"name": "x" * 101}, "name"),
        ({"name": "Burn", "is_public": "yes"}, "is_public"),
        ({"name": "Burn", "description": 5}, "description"),
        ({"name": "Burn", "format": "f" * 51}, "format"),
        ({"name": "Burn", "owner": "bob"}, "owner"),
    ],
)
def test_create_validation(alice, body, field):
    resp = alice.post("/api/decks", json=body)
    assert resp.status_code == 400
    assert [d["field"] for d in resp.get_json()["details"]] == [field]


# --- authorisation matrix --------------------------------------------------------------


@pytest.fixture
def private_deck(alice):
    return make_deck(alice, name="Secret")["id"]


@pytest.fixture
def public_deck(alice):
    return make_deck(alice, name="Shared", is_public=True)["id"]


@pytest.mark.parametrize("who,status", [("alice", 200), ("bob", 404), ("anon", 404)])
def test_read_private_deck(request, private_deck, who, status):
    assert request.getfixturevalue(who).get(f"/api/decks/{private_deck}").status_code == status


@pytest.mark.parametrize("who", ["alice", "bob", "anon"])
def test_read_public_deck(request, public_deck, who):
    assert request.getfixturevalue(who).get(f"/api/decks/{public_deck}").status_code == 200


@pytest.mark.parametrize(
    "who,deck,status",
    [
        ("alice", "private_deck", 200),
        ("bob", "private_deck", 404),  # existence of private decks isn't revealed
        ("bob", "public_deck", 403),
        ("anon", "public_deck", 401),
    ],
)
def test_update_authorisation(request, who, deck, status):
    deck_id = request.getfixturevalue(deck)
    client = request.getfixturevalue(who)
    assert client.patch(f"/api/decks/{deck_id}", json={"name": "X"}).status_code == status
    assert set_cards(client, deck_id, []).status_code == status


@pytest.mark.parametrize(
    "who,deck,status",
    [
        ("bob", "private_deck", 404),
        ("bob", "public_deck", 403),
        ("anon", "public_deck", 401),
        ("alice", "public_deck", 204),
    ],
)
def test_delete_authorisation(request, who, deck, status):
    deck_id = request.getfixturevalue(deck)
    assert request.getfixturevalue(who).delete(f"/api/decks/{deck_id}").status_code == status


def test_missing_deck_is_404(alice):
    assert alice.get("/api/decks/9999").status_code == 404
    assert alice.patch("/api/decks/9999", json={}).status_code == 404


# --- update / delete -------------------------------------------------------------------


def test_patch_updates_only_given_fields(alice, private_deck):
    resp = alice.patch(f"/api/decks/{private_deck}", json={"is_public": True, "format": None})
    deck = resp.get_json()
    assert resp.status_code == 200
    assert (deck["name"], deck["is_public"], deck["format"]) == ("Secret", True, None)


@pytest.mark.parametrize("name", [None, "", "  "])
def test_patch_rejects_blank_name(alice, private_deck, name):
    assert alice.patch(f"/api/decks/{private_deck}", json={"name": name}).status_code == 400


def test_delete_removes_deck_and_entries(alice, db, private_deck):
    set_cards(alice, private_deck, [{"card_id": BOLT, "quantity": 4}])
    assert alice.delete(f"/api/decks/{private_deck}").status_code == 204
    assert alice.get(f"/api/decks/{private_deck}").status_code == 404
    assert db.session.execute(db.select(db.func.count()).select_from(DeckCard)).scalar() == 0


# --- cards -------------------------------------------------------------------------------


def test_replace_cards(alice, private_deck):
    resp = set_cards(
        alice,
        private_deck,
        [
            {"card_id": BOLT, "quantity": 4},
            {"card_id": FOREST, "quantity": 20, "board": "main"},
            {"card_id": COUNTERSPELL, "quantity": 2, "board": "side"},
        ],
    )
    deck = resp.get_json()
    assert resp.status_code == 200
    assert deck["card_count"] == 26
    assert [(c["card"]["name"], c["quantity"], c["board"]) for c in deck["cards"]] == [
        ("Forest", 20, "main"),
        ("Lightning Bolt", 4, "main"),
        ("Counterspell", 2, "side"),
    ]
    assert set(deck["cards"][0]["card"]) == {"id", "name", "mana_cost", "type_line"}


def test_replace_cards_replaces_whole_list(alice, private_deck):
    set_cards(alice, private_deck, [{"card_id": BOLT, "quantity": 4}])
    deck = set_cards(alice, private_deck, [{"card_id": FOREST, "quantity": 1}]).get_json()
    assert [c["card"]["name"] for c in deck["cards"]] == ["Forest"]
    assert set_cards(alice, private_deck, []).get_json()["cards"] == []


def test_same_card_in_main_and_side(alice, private_deck):
    resp = set_cards(
        alice,
        private_deck,
        [{"card_id": BOLT, "quantity": 3}, {"card_id": BOLT, "quantity": 1, "board": "side"}],
    )
    assert resp.status_code == 200
    assert resp.get_json()["card_count"] == 4


def test_replace_cards_bumps_updated_at(alice, private_deck):
    before = alice.get(f"/api/decks/{private_deck}").get_json()["updated_at"]
    after = set_cards(alice, private_deck, [{"card_id": BOLT, "quantity": 1}]).get_json()
    assert after["updated_at"] > before


@pytest.mark.parametrize(
    "entries,field",
    [
        ([{"card_id": "nope", "quantity": 1}], "cards[0].card_id"),
        ([{"quantity": 1}], "cards[0].card_id"),
        ([{"card_id": BOLT, "quantity": 0}], "cards[0].quantity"),
        ([{"card_id": BOLT, "quantity": 100}], "cards[0].quantity"),
        ([{"card_id": BOLT, "quantity": "4"}], "cards[0].quantity"),
        ([{"card_id": BOLT, "quantity": True}], "cards[0].quantity"),
        ([{"card_id": BOLT, "quantity": 1, "board": "maybe"}], "cards[0].board"),
        (
            [{"card_id": BOLT, "quantity": 1}, {"card_id": BOLT, "quantity": 2}],
            "cards[1]",
        ),
        (["bolt"], "cards[0]"),
        ("bolt", "cards"),
        ([{"card_id": BOLT, "quantity": 1}] * 251, "cards"),
    ],
)
def test_replace_cards_validation(alice, private_deck, entries, field):
    assert set_cards(alice, private_deck, [{"card_id": FOREST, "quantity": 1}]).status_code == 200
    resp = set_cards(alice, private_deck, entries)
    assert resp.status_code == 400
    assert field in [d["field"] for d in resp.get_json()["details"]]
    # Nothing changed.
    deck = alice.get(f"/api/decks/{private_deck}").get_json()
    assert [c["card"]["name"] for c in deck["cards"]] == ["Forest"]


def test_soft_deleted_cards_stay_in_decks(alice, db, private_deck):
    set_cards(alice, private_deck, [{"card_id": BOLT, "quantity": 4}])
    db.session.execute(db.update(Card).where(Card.scryfall_id == BOLT).values(is_active=False))
    db.session.commit()
    deck = alice.get(f"/api/decks/{private_deck}").get_json()
    assert deck["cards"][0]["card"]["id"] == BOLT


# --- listings ----------------------------------------------------------------------------


def test_list_mine(alice, bob):
    make_deck(alice, name="A1")
    make_deck(alice, name="A2", is_public=True)
    make_deck(bob, name="B1")
    body = alice.get("/api/decks/mine").get_json()
    assert body["total"] == 2
    assert [d["name"] for d in body["results"]] == ["A2", "A1"]  # most recently updated first
    assert set(body["results"][0]) == SUMMARY_KEYS


def test_list_mine_requires_auth(anon):
    assert anon.get("/api/decks/mine").status_code == 401


def test_list_public(alice, bob, anon):
    make_deck(alice, name="A-private")
    make_deck(alice, name="A-public", is_public=True)
    deck = make_deck(bob, name="B-public", is_public=True)
    set_cards(bob, deck["id"], [{"card_id": BOLT, "quantity": 4}])

    body = anon.get("/api/decks/public").get_json()
    assert [(d["name"], d["owner"], d["card_count"]) for d in body["results"]] == [
        ("B-public", "bob", 4),
        ("A-public", "alice", 0),
    ]


def test_list_public_paginates(alice, anon):
    for i in range(3):
        make_deck(alice, name=f"D{i}", is_public=True)
    body = anon.get("/api/decks/public?limit=2&page=2").get_json()
    assert (body["total"], len(body["results"])) == (3, 1)
    assert anon.get("/api/decks/public?limit=0").status_code == 400


def test_user_public_decks(alice, bob, anon):
    make_deck(alice, name="A-private")
    make_deck(alice, name="A-public", is_public=True)
    make_deck(bob, name="B-public", is_public=True)
    body = anon.get("/api/users/alice/decks").get_json()
    assert [d["name"] for d in body["results"]] == ["A-public"]
    assert anon.get("/api/users/nobody/decks").status_code == 404


def test_deleting_user_cascades_to_decks(alice, db):
    """Not exposed in the API yet; checks the FK cascade is in place for when it is."""
    make_deck(alice)
    user = db.session.execute(db.select(User).where(User.username == "alice")).scalar_one()
    db.session.execute(db.delete(User).where(User.id == user.id))
    db.session.commit()
    assert db.session.execute(db.select(db.func.count()).select_from(Deck)).scalar() == 0


def test_replace_cards_with_same_card_new_quantity(alice, private_deck):
    set_cards(alice, private_deck, [{"card_id": BOLT, "quantity": 4}])
    deck = set_cards(alice, private_deck, [{"card_id": BOLT, "quantity": 2}]).get_json()
    assert [(c["card"]["name"], c["quantity"]) for c in deck["cards"]] == [("Lightning Bolt", 2)]
    deck = alice.get(f"/api/decks/{private_deck}").get_json()
    assert deck["card_count"] == 2
