import gzip
import json
from pathlib import Path

import pytest
import requests

from scryapi import create_app
from scryapi.config import TestConfig
from scryapi.models import Card, SyncState
from scryapi.sync import run_sync
from scryapi.sync.download import BULK_FILENAME, BULK_INFO_URL, SyncError
from scryapi.sync.importer import import_cards, iter_cards
from scryapi.sync.normalise import normalise_card, should_import
from scryapi.sync.scheduler import sync_job
from tests.conftest import CARDS_SAMPLE

DOWNLOAD_URI = "https://data.scryfall.io/oracle-cards/oracle-cards-1.jsonl.gz"
UPDATED_AT = "2026-10-20T09:01:59.775+00:00"


@pytest.fixture
def raw_cards():
    return json.loads(CARDS_SAMPLE.read_text())


def by_name(raw_cards, name):
    return next(c for c in raw_cards if c["name"] == name)


def jsonl_gz(cards):
    return gzip.compress("".join(json.dumps(c) + "\n" for c in cards).encode())


def mock_scryfall(rsps, body, updated_at=UPDATED_AT, size=None):
    rsps.get(
        BULK_INFO_URL,
        json={
            "object": "bulk_data",
            "type": "oracle_cards",
            "updated_at": updated_at,
            "jsonl_download_uri": DOWNLOAD_URI,
            "compressed_size": len(body) if size is None else size,
        },
    )
    rsps.get(DOWNLOAD_URI, body=body, content_type="application/gzip")


def card_count(db, active_only=True):
    stmt = db.select(db.func.count()).select_from(Card)
    if active_only:
        stmt = stmt.where(Card.is_active)
    return db.session.execute(stmt).scalar_one()


# --- normalise ---------------------------------------------------------------------


def test_normalise_single_faced(raw_cards):
    row = normalise_card(by_name(raw_cards, "Tarmogoyf"))
    assert row["power"] == "*" and row["toughness"] == "1+*"
    assert row["card_faces"] is None
    assert row["image_uri"].startswith("https://")


def test_normalise_transform_joins_face_text(raw_cards):
    row = normalise_card(by_name(raw_cards, "Delver of Secrets // Insectile Aberration"))
    assert row["oracle_text"].endswith("transform this creature.\n//\nFlying")
    assert (row["power"], row["toughness"]) == ("1", "1")  # front face
    assert row["mana_cost"] == "{U}"  # back face has no cost
    assert [f["name"] for f in row["card_faces"]] == ["Delver of Secrets", "Insectile Aberration"]
    assert row["image_uri"] == row["card_faces"][0]["image_uri"]


def test_normalise_split_joins_costs(raw_cards):
    row = normalise_card(by_name(raw_cards, "Fire // Ice"))
    assert row["mana_cost"] == "{1}{R} // {1}{U}"


def test_normalise_planeswalker_loyalty(raw_cards):
    assert normalise_card(by_name(raw_cards, "Jace, the Mind Sculptor"))["loyalty"] == "3"


def test_should_import_skips_non_cards_and_art_series():
    assert not should_import({"object": "card", "layout": "art_series"})
    assert not should_import({"object": "bulk_data"})
    assert should_import({"object": "card", "layout": "normal"})


# --- import ------------------------------------------------------------------------


def test_iter_cards_reads_jsonl_and_gz(tmp_path, raw_cards):
    plain = tmp_path / "cards.jsonl"
    plain.write_text("\n".join(json.dumps(c) for c in raw_cards[:3]) + "\n\n")
    packed = tmp_path / "cards.jsonl.gz"
    packed.write_bytes(jsonl_gz(raw_cards[:3]))
    assert [c["id"] for c in iter_cards(plain)] == [c["id"] for c in raw_cards[:3]]
    assert [c["id"] for c in iter_cards(packed)] == [c["id"] for c in raw_cards[:3]]


def test_reimport_updates_changed_cards(db, raw_cards):
    import_cards(raw_cards)
    db.session.commit()
    by_name(raw_cards, "Lightning Bolt")["oracle_text"] = "Errata'd text."
    import_cards(raw_cards)
    db.session.commit()
    bolt = db.session.execute(db.select(Card).where(Card.name == "Lightning Bolt")).scalar_one()
    assert bolt.oracle_text == "Errata'd text."
    assert card_count(db) == len(raw_cards)


def test_reimport_updates_search_index(client, db, raw_cards):
    import_cards(raw_cards)
    by_name(raw_cards, "Lightning Bolt")["oracle_text"] = "Zorbulate any target."
    import_cards(raw_cards)
    db.session.commit()
    body = client.get("/api/cards?text=zorbulate").get_json()
    assert [c["name"] for c in body["results"]] == ["Lightning Bolt"]


def test_cards_missing_from_import_are_soft_deleted(client, db, raw_cards):
    import_cards(raw_cards)
    db.session.commit()
    goyf_id = by_name(raw_cards, "Tarmogoyf")["id"]
    import_cards([c for c in raw_cards if c["id"] != goyf_id])
    db.session.commit()

    assert card_count(db) == len(raw_cards) - 1
    assert card_count(db, active_only=False) == len(raw_cards)
    assert client.get("/api/cards?name=Tarmogoyf").get_json()["results"] == []
    assert client.get(f"/api/cards/{goyf_id}").status_code == 200  # decks may reference it


def test_import_batches(db, raw_cards, monkeypatch):
    monkeypatch.setattr("scryapi.sync.importer.BATCH_SIZE", 4)
    result = import_cards(raw_cards)
    assert result.imported == len(raw_cards)
    assert card_count(db) == len(raw_cards)


# --- run_sync / download -------------------------------------------------------------


def test_run_sync_from_file(db):
    result = run_sync(file=CARDS_SAMPLE)
    assert result.status == "imported"
    assert card_count(db) == 21
    state = db.session.get(SyncState, "oracle_cards")
    assert state.last_success_at is not None and state.last_error is None


def test_run_sync_downloads_and_imports(app, db, no_network, raw_cards):
    mock_scryfall(no_network, jsonl_gz(raw_cards))
    result = run_sync()

    assert result.status == "imported"
    assert card_count(db) == len(raw_cards)
    assert db.session.get(SyncState, "oracle_cards").source_updated_at == UPDATED_AT
    headers = no_network.calls[0].request.headers
    assert headers["User-Agent"].startswith("scryapi")
    assert "application/json" in headers["Accept"]
    assert (Path(app.config["SCRYAPI_DATA_DIR"]) / BULK_FILENAME).exists()


def test_run_sync_skips_when_up_to_date(db, no_network, raw_cards):
    mock_scryfall(no_network, jsonl_gz(raw_cards))
    run_sync()
    assert run_sync().status == "up_to_date"
    assert run_sync(force=True).status == "imported"


def test_truncated_download_keeps_previous_file_and_data(app, db, no_network, raw_cards):
    body = jsonl_gz(raw_cards)
    mock_scryfall(no_network, body)
    run_sync()
    bulk_file = Path(app.config["SCRYAPI_DATA_DIR"]) / BULK_FILENAME
    before = bulk_file.read_bytes()

    no_network.reset()
    mock_scryfall(no_network, body[:100], updated_at="2026-10-27T00:00:00+00:00", size=len(body))
    with pytest.raises(SyncError, match="Truncated"):
        run_sync()

    assert bulk_file.read_bytes() == before
    assert not list(bulk_file.parent.glob("*.part"))
    assert card_count(db) == len(raw_cards)
    state = db.session.get(SyncState, "oracle_cards")
    assert "Truncated" in state.last_error
    assert state.source_updated_at == UPDATED_AT


def test_failed_import_rolls_back(db, tmp_path, raw_cards):
    run_sync(file=CARDS_SAMPLE)
    broken = tmp_path / "broken.jsonl"
    broken.write_text(json.dumps(raw_cards[0]) + "\n{not json\n")
    with pytest.raises(json.JSONDecodeError):
        run_sync(file=broken)
    assert card_count(db) == len(raw_cards)  # the deactivate-all step was rolled back
    assert "JSONDecodeError" in db.session.get(SyncState, "oracle_cards").last_error


def test_network_error_surfaces(db, no_network):
    no_network.get(BULK_INFO_URL, body=requests.ConnectionError("down"))
    with pytest.raises(requests.ConnectionError):
        run_sync()


def test_missing_download_uri_is_a_sync_error(db, no_network):
    no_network.get(BULK_INFO_URL, json={"updated_at": UPDATED_AT, "download_uri": "old-api"})
    with pytest.raises(SyncError, match="jsonl_download_uri"):
        run_sync()


# --- entry points ------------------------------------------------------------------


def test_app_factory_has_no_side_effects(no_network):
    create_app(TestConfig)
    assert len(no_network.calls) == 0


def test_scheduler_job_pushes_its_own_app_context(app, db, no_network, raw_cards):
    mock_scryfall(no_network, jsonl_gz(raw_cards))
    sync_job(app)  # called the way APScheduler calls it
    assert card_count(db) == len(raw_cards)


def test_scheduler_job_survives_failures(app, no_network):
    no_network.get(BULK_INFO_URL, status=500)
    sync_job(app)  # must not raise


def test_sync_cards_cli(app, db):
    result = app.test_cli_runner().invoke(args=["sync-cards", "--file", str(CARDS_SAMPLE)])
    assert result.exit_code == 0, result.output
    assert "Imported 21 cards" in result.output
    assert card_count(db) == 21


def test_cli_lists_commands(app):
    result = app.test_cli_runner().invoke(args=["--help"])
    for command in ("sync-cards", "run-scheduler", "db"):
        assert command in result.output
