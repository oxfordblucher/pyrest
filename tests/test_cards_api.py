"""Request-level tests for /api/cards.

Tests marked `xfail(strict=True)` describe the *target* behaviour from docs/AUDIT.md.
They currently fail; when the referenced AUDIT item is fixed they start passing, strict
mode turns that into a failure, and the fixing PR must remove the marker.
"""

import pytest

pytestmark = pytest.mark.usefixtures("cards")

SAMPLE_SIZE = 21


def names(resp):
    return [c["name"] for c in resp.get_json()["results"]]


def test_list_cards_defaults(client):
    resp = client.get("/api/cards/")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["page"] == 1
    assert body["limit"] == 20
    assert len(body["results"]) == 20
    assert names(resp) == sorted(names(resp))


def test_list_cards_second_page(client):
    resp = client.get("/api/cards/?page=2&limit=20")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) == SAMPLE_SIZE - 20


def test_limit_is_capped_at_50(client):
    resp = client.get("/api/cards/?limit=45")
    assert resp.get_json()["limit"] == 45
    assert len(resp.get_json()["results"]) == SAMPLE_SIZE


@pytest.mark.parametrize(
    "query,expected",
    [
        ("name=kinnan", ["Kinnan, Bonder Prodigy"]),
        ("name=JHOIRA", ["Jhoira, Weatherlight Captain"]),
        ("type=sorcery", ["Demonic Tutor", "Gitaxian Probe"]),
    ],
)
def test_substring_filters(client, query, expected):
    resp = client.get(f"/api/cards/?{query}")
    assert resp.status_code == 200
    assert names(resp) == expected


def test_full_text_search(client):
    resp = client.get("/api/cards/?text=search your library")
    assert resp.status_code == 200
    assert "Demonic Tutor" in names(resp)


def test_filters_combine(client):
    resp = client.get("/api/cards/?text=countered&type=dinosaur")
    assert names(resp) == ["Carnage Tyrant"]


def test_get_card_by_id(client):
    first = client.get("/api/cards/?limit=1").get_json()["results"][0]
    resp = client.get(f"/api/cards/{first['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["name"] == first["name"]


def test_get_card_by_id_not_found(client):
    assert client.get("/api/cards/999999").status_code == 404


# --- Target behaviour (see docs/AUDIT.md) -------------------------------------------


@pytest.mark.xfail(strict=True, reason="AUDIT C6: invalid pagination is silently defaulted")
@pytest.mark.parametrize("query", ["page=0", "limit=0", "limit=51", "page=two", "limit=-45"])
def test_invalid_pagination_returns_400(client, query):
    resp = client.get(f"/api/cards/?{query}")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "validation_error"


@pytest.mark.xfail(strict=True, reason="AUDIT C7: raw user input reaches FTS5 MATCH")
@pytest.mark.parametrize("text", ['"', "AND", "foo(", "*"])
def test_malformed_search_text_never_errors(client, text):
    assert client.get("/api/cards/", query_string={"text": text}).status_code == 200


@pytest.mark.xfail(strict=True, reason="AUDIT E3: multi-face cards import with NULL text")
def test_multi_face_cards_are_searchable(client):
    resp = client.get("/api/cards/?text=transform")
    assert "Delver of Secrets // Insectile Aberration" in names(resp)


@pytest.mark.xfail(strict=True, reason="AUDIT S6: LIKE wildcards in filters are not escaped")
def test_like_wildcards_are_literal(client):
    resp = client.get("/api/cards/", query_string={"name": "%"})
    assert names(resp) == []
