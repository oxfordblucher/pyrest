import json
from pathlib import Path

from sqlalchemy.dialects.sqlite import insert

from scryapi.extensions import db
from scryapi.models import Card


def sync_fts():
    db.session.execute(
        db.text("""
        INSERT INTO cards_fts(cards_fts)
        VALUES('rebuild')
    """)
    )
    db.session.commit()


DEFAULT_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "card_data.json"


def import_cards(json_path=DEFAULT_JSON_PATH):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    BATCH_SIZE = 500

    print("import initiated")

    for i in range(0, len(data), BATCH_SIZE):
        batch = data[i : i + BATCH_SIZE]
        rows = [
            {
                "uuid": item.get("id"),
                "name": item.get("name"),
                "mana_cost": item.get("mana_cost"),
                "type_line": item.get("type_line"),
                "oracle_text": item.get("oracle_text"),
                "power": item.get("power"),
                "toughness": item.get("toughness"),
            }
            for item in batch
        ]
        query = insert(Card).values(rows)
        query = query.on_conflict_do_nothing(index_elements=["uuid"])
        db.session.execute(query)

    db.session.commit()
    sync_fts()


if __name__ == "__main__":
    import_cards()
