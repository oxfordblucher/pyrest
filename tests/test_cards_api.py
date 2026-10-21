"""Request-level tests for /api/cards (docs/TDD.md §9)."""

import pytest

from scryapi.models import Card
from scryapi.models.card import name_key

pytestmark = pytest.mark.usefixtures("cards")

SAMPLE_SIZE = 21


def names(resp):
    return [c["name"] for c in resp.get_json()["results"]]


def test_list_cards_defaults(client):
    resp = client.get("/api/cards")
    body = resp.get_json()
    assert resp.status_code == 200
    assert (body["page"], body["limit"], body["total"]) == (1, 20, SAMPLE_SIZE)
    assert len(body["results"]) == 20
    assert names(resp) == sorted(names(resp), key=name_key)


def test_trailing_slash_is_accepted(client):
    assert client.get("/api/cards/").status_code == 200


def test_list_cards_second_page(client):
    resp = client.get("/api/cards?page=2&limit=20")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) == SAMPLE_SIZE - 20


def test_page_past_the_end_is_empty(client):
    body = client.get("/api/cards?page=99").get_json()
    assert body["results"] == []
    assert body["total"] == SAMPLE_SIZE


def test_card_shape(client):
    card = client.get("/api/cards", query_string={"name": "Tarmogoyf"}).get_json()["results"][0]
    assert set(card) == {
        "id", "name", "mana_cost", "cmc", "type_line", "oracle_text", "power", "toughness",
        "loyalty", "colors", "color_identity", "layout", "card_faces", "image_uri",
        "scryfall_uri",
    }  # fmt: skip
    assert (card["power"], card["toughness"]) == ("*", "1+*")
    assert len(card["id"]) == 36  # Scryfall UUID, not the internal integer id


@pytest.mark.parametrize(
    "query,expected",
    [
        ("name=kinnan", ["Kinnan, Bonder Prodigy"]),
        ("name=JHOIRA", ["Jhoira, Weatherlight Captain"]),
        ("type=sorcery", ["Demonic Tutor", "Gitaxian Probe"]),
    ],
)
def test_substring_filters(client, query, expected):
    resp = client.get(f"/api/cards?{query}")
    assert resp.status_code == 200
    assert names(resp) == expected


def test_full_text_search(client):
    resp = client.get("/api/cards?text=search your library")
    assert resp.status_code == 200
    assert "Demonic Tutor" in names(resp)


def test_full_text_search_stems(client):
    # "countered" in the query matches "can't be countered" and "counter target spell".
    assert {"Carnage Tyrant", "Counterspell"} <= set(names(client.get("/api/cards?text=counter")))


def test_filters_combine(client):
    resp = client.get("/api/cards?text=countered&type=dinosaur")
    assert names(resp) == ["Carnage Tyrant"]


def test_total_reflects_filters(client):
    assert client.get("/api/cards?type=sorcery&limit=1").get_json()["total"] == 2


def test_get_card_by_id(client):
    first = client.get("/api/cards?limit=1").get_json()["results"][0]
    resp = client.get(f"/api/cards/{first['id']}")
    assert resp.status_code == 200
    assert resp.get_json() == first


def test_get_card_by_id_not_found(client):
    resp = client.get("/api/cards/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not_found"


@pytest.mark.parametrize(
    "query,field",
    [
        ("page=0", "page"),
        ("limit=0", "limit"),
        ("limit=51", "limit"),
        ("page=two", "page"),
        ("limit=-45", "limit"),
        ("name=" + "x" * 101, "name"),
        ("text=" + "x" * 101, "text"),
    ],
)
def test_invalid_query_returns_400(client, query, field):
    resp = client.get(f"/api/cards?{query}")
    body = resp.get_json()
    assert resp.status_code == 400
    assert body["error"] == "validation_error"
    assert [d["field"] for d in body["details"]] == [field]


def test_all_validation_errors_reported_together(client):
    body = client.get("/api/cards?page=two&limit=0").get_json()
    assert {d["field"] for d in body["details"]} == {"page", "limit"}


@pytest.mark.parametrize("text", ['"', "AND", "foo(", "*", "NEAR(a b)", "col:x", "^", "ñ€😀"])
def test_malformed_search_text_never_errors(client, text):
    assert client.get("/api/cards", query_string={"text": text}).status_code == 200


def test_blank_search_text_is_ignored(client):
    assert client.get("/api/cards?text=%20%20").get_json()["total"] == SAMPLE_SIZE


@pytest.mark.parametrize(
    "text,expected",
    [
        ("transform", "Delver of Secrets // Insectile Aberration"),  # transform front face
        ("Tibalt", "Valki, God of Lies // Tibalt, Cosmic Impostor"),  # MDFC back face
        ("damage can't be prevented", "Bonecrusher Giant // Stomp"),  # adventure face text
        ("draw a card", "Fire // Ice"),  # split card second half
    ],
)
def test_multi_face_cards_are_searchable(client, text, expected):
    assert expected in names(client.get("/api/cards", query_string={"text": text}))


@pytest.mark.parametrize("value", ["%", "_", "\\"])
def test_like_wildcards_are_literal(client, value):
    resp = client.get("/api/cards", query_string={"name": value})
    assert names(resp) == []


def test_name_search_ranks_prefix_matches_first(client):
    resp = client.get("/api/cards", query_string={"name": "d", "limit": 50})
    prefix = ["Delver of Secrets // Insectile Aberration", "Demonic Tutor", "Dryad Arbor"]
    assert names(resp)[:3] == prefix
    assert names(resp)[3:] == sorted(names(resp)[3:])


def test_name_search_ranks_exact_match_first(client, db):
    db.session.add_all(
        [
            Card(scryfall_id="00000000-0000-0000-0000-000000000001", name="A Lightning Bolt"),
            Card(scryfall_id="00000000-0000-0000-0000-000000000002", name="Lightning Bolter"),
        ]
    )
    db.session.commit()
    resp = client.get("/api/cards", query_string={"name": "LIGHTNING BOLT"})
    assert names(resp) == ["Lightning Bolt", "Lightning Bolter", "A Lightning Bolt"]


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Lightning Bolt", "lightning bolt"),
        ("Jötun Grunt", "jotun grunt"),
        ("Æther Vial", "aether vial"),
        ("Lim-Dûl's Vault", "lim-dul's vault"),
    ],
)
def test_name_key(name, key):
    assert name_key(name) == key


def test_name_search_ignores_accents_and_ligatures(client, db):
    db.session.add_all(
        [
            Card(scryfall_id="00000000-0000-0000-0000-000000000003", name="Jötun Grunt"),
            Card(scryfall_id="00000000-0000-0000-0000-000000000004", name="Æther Vial"),
        ]
    )
    db.session.commit()
    assert names(client.get("/api/cards?name=jotun")) == ["Jötun Grunt"]
    assert names(client.get("/api/cards?name=aether")) == ["Æther Vial"]
    assert names(client.get("/api/cards?name=JÖTUN")) == ["Jötun Grunt"]


def test_ordering_is_bytewise_on_sort_name(client, db):
    """The same order on SQLite and Postgres, regardless of the database locale."""
    db.session.add_all(
        [
            Card(scryfall_id="00000000-0000-0000-0000-000000000005", name="_____ Goblin"),
            Card(scryfall_id="00000000-0000-0000-0000-000000000006", name="Island of Wak-Wak"),
            Card(scryfall_id="00000000-0000-0000-0000-000000000007", name="Island Sanctuary"),
        ]
    )
    db.session.commit()
    resp = client.get("/api/cards", query_string={"limit": 50})
    assert names(resp) == sorted(names(resp), key=lambda n: name_key(n).encode())
