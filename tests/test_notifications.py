"""Cards Scryfall drops leave decks, and owners are notified (AUDIT R1, PRD FR-S6)."""

import json

import pytest

from scryapi.models import Notification
from scryapi.sync import run_sync
from scryapi.sync.download import SyncError
from tests.conftest import CARDS_SAMPLE

RAW = json.loads(CARDS_SAMPLE.read_text())
ID = {c["name"]: c["id"] for c in RAW}
BOLT, COUNTERSPELL, FOREST = ID["Lightning Bolt"], ID["Counterspell"], ID["Forest"]

pytestmark = pytest.mark.usefixtures("cards")


def make_deck(api, name, entries, **fields):
    deck = api.post("/api/decks", json={"name": name, **fields}).get_json()
    cards = [{"card_id": cid, "quantity": q, "board": b} for cid, q, b in entries]
    resp = api.put(f"/api/decks/{deck['id']}/cards", json={"cards": cards})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def sync_without(tmp_path, *removed, **kwargs):
    path = tmp_path / "oracle.json"
    path.write_text(json.dumps([c for c in RAW if c["id"] not in removed]))
    return run_sync(file=path, **kwargs)


def notifications(api, **params):
    return api.get("/api/notifications", query_string=params).get_json()


@pytest.fixture
def burn(alice):
    return make_deck(
        alice,
        "Burn",
        [(BOLT, 4, "main"), (COUNTERSPELL, 2, "main"), (BOLT, 1, "side")],
        is_public=True,
    )


def test_dropped_card_leaves_deck(tmp_path, alice, burn):
    result = sync_without(tmp_path, BOLT)
    assert (result.imported.dropped, result.imported.decks_changed) == (1, 1)

    deck = alice.get(f"/api/decks/{burn['id']}").get_json()
    assert [(c["card"]["name"], c["quantity"]) for c in deck["cards"]] == [("Counterspell", 2)]
    assert deck["updated_at"] > burn["updated_at"]


def test_owner_is_notified(tmp_path, alice, burn):
    sync_without(tmp_path, BOLT)

    page = notifications(alice)
    assert page["total"] == 1
    note = page["results"][0]
    assert note["kind"] == "cards_removed"
    assert note["read"] is False
    assert note["data"] == {
        "deck": {"id": burn["id"], "name": "Burn"},
        "cards": [
            {"id": BOLT, "name": "Lightning Bolt", "quantity": 4, "board": "main"},
            {"id": BOLT, "name": "Lightning Bolt", "quantity": 1, "board": "side"},
        ],
    }
    assert note["message"] == (
        "Scryfall no longer lists 2 cards from your deck “Burn”, so they were "
        "removed: Lightning Bolt ×4, Lightning Bolt ×1 (side)."
    )
    assert alice.get("/api/auth/me").get_json()["unread_notifications"] == 1


def test_one_notification_per_affected_deck(tmp_path, alice, bob, burn):
    make_deck(alice, "Bolts", [(BOLT, 1, "main")])
    make_deck(alice, "Forests", [(FOREST, 60, "main")])
    make_deck(bob, "Counters", [(COUNTERSPELL, 4, "main")])
    result = sync_without(tmp_path, BOLT)

    assert result.imported.decks_changed == 2
    assert sorted(n["data"]["deck"]["name"] for n in notifications(alice)["results"]) == [
        "Bolts",
        "Burn",
    ]
    assert notifications(bob)["total"] == 0


def test_unchanged_sync_notifies_nobody(tmp_path, alice, burn):
    result = sync_without(tmp_path)
    assert (result.imported.dropped, result.imported.decks_changed) == (0, 0)
    assert notifications(alice)["total"] == 0


def test_removed_cards_cannot_be_added_back(tmp_path, alice, burn):
    sync_without(tmp_path, BOLT)
    resp = alice.put(
        f"/api/decks/{burn['id']}/cards", json={"cards": [{"card_id": BOLT, "quantity": 1}]}
    )
    assert resp.status_code == 400
    assert resp.get_json()["details"] == [
        {"field": "cards[0].card_id", "message": "is not a known card"}
    ]


def test_failed_sync_keeps_decks_and_sends_nothing(tmp_path, db, alice, burn, monkeypatch):
    def explode(self):
        raise RuntimeError("index rebuild failed")

    # Fails after the deck entries are deleted and the notifications are written.
    for backend in ("sqlite_fts.SqliteFtsBackend", "postgres_fts.PostgresFtsBackend"):
        monkeypatch.setattr(f"scryapi.search.{backend}.rebuild", explode)
    with pytest.raises(RuntimeError):
        sync_without(tmp_path, BOLT)

    assert db.session.execute(db.select(db.func.count()).select_from(Notification)).scalar() == 0
    deck = alice.get(f"/api/decks/{burn['id']}").get_json()
    assert len(deck["cards"]) == 3


# --- the mass-removal guard ------------------------------------------------------------


@pytest.fixture
def small_guard(monkeypatch):
    # The real threshold (> 50 cards and > 2%) can't be reached with 21 sample cards.
    monkeypatch.setattr("scryapi.sync.importer.MIN_GUARDED_DROPS", 1)


def test_mass_removal_is_refused(tmp_path, db, alice, burn, small_guard):
    with pytest.raises(SyncError, match="would remove 2 of 21 cards"):
        sync_without(tmp_path, BOLT, COUNTERSPELL)
    assert len(alice.get(f"/api/decks/{burn['id']}").get_json()["cards"]) == 3
    assert notifications(alice)["total"] == 0


def test_mass_removal_can_be_allowed(tmp_path, alice, burn, small_guard):
    result = sync_without(tmp_path, BOLT, COUNTERSPELL, allow_removals=True)
    assert result.imported.dropped == 2
    assert alice.get(f"/api/decks/{burn['id']}").get_json()["cards"] == []


def test_cli_reports_refusal_without_traceback(app, tmp_path, small_guard):
    path = tmp_path / "oracle.json"
    path.write_text(json.dumps([c for c in RAW if c["id"] not in (BOLT, COUNTERSPELL)]))
    runner = app.test_cli_runner()
    result = runner.invoke(args=["sync-cards", "--file", str(path)])
    assert result.exit_code == 1
    assert "--allow-removals" in result.output
    assert "Traceback" not in result.output

    result = runner.invoke(args=["sync-cards", "--file", str(path), "--allow-removals"])
    assert result.exit_code == 0, result.output
    assert "2 cards were removed by Scryfall" in result.output


# --- notifications API -----------------------------------------------------------------


@pytest.fixture
def notified(tmp_path, alice, burn):
    make_deck(alice, "Bolts", [(BOLT, 1, "main")])
    sync_without(tmp_path, BOLT)
    return notifications(alice)["results"]


def test_notifications_require_login(anon):
    assert anon.get("/api/notifications").status_code == 401
    assert anon.post("/api/notifications/read-all").status_code == 401


def test_notifications_are_newest_first(notified):
    assert [n["id"] for n in notified] == sorted((n["id"] for n in notified), reverse=True)


def test_mark_one_read(alice, notified):
    first = notified[0]
    resp = alice.post(f"/api/notifications/{first['id']}/read")
    assert resp.status_code == 200
    assert resp.get_json()["read"] is True
    assert alice.post(f"/api/notifications/{first['id']}/read").status_code == 200  # idempotent
    assert [n["id"] for n in notifications(alice, unread="true")["results"]] == [notified[1]["id"]]
    assert alice.get("/api/auth/me").get_json()["unread_notifications"] == 1


def test_mark_all_read(alice, notified):
    assert alice.post("/api/notifications/read-all").status_code == 204
    assert notifications(alice, unread="true")["total"] == 0
    assert notifications(alice)["total"] == 2  # still listed, just read


def test_cannot_read_someone_elses_notification(bob, notified):
    resp = bob.post(f"/api/notifications/{notified[0]['id']}/read")
    assert resp.status_code == 404


@pytest.mark.parametrize("params", [{"unread": "maybe"}, {"page": "0"}])
def test_list_validation(alice, params):
    assert alice.get("/api/notifications", query_string=params).status_code == 400


def test_deleting_user_deletes_notifications(db, notified):
    db.session.execute(db.text("DELETE FROM users"))  # ON DELETE CASCADE, as in TDD §5
    db.session.commit()
    assert db.session.execute(db.select(db.func.count()).select_from(Notification)).scalar() == 0
