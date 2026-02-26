from ..extensions import db
from pathlib import Path
from sqlalchemy.dialects.sqlite import insert

import json
from app import create_app
from ..models import Card

app = create_app()

def import_cards():
    json_path = Path(__file__).resolve().parent.parent / "data" / "card_data.json"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    BATCH_SIZE = 500

    with app.app_context():

        for i in range(0, len(data), BATCH_SIZE):
            batch = data[i:i + BATCH_SIZE]
            rows = [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "mana_cost": item.get("mana_cost"),
                    "type_line": item.get("type_line"),
                    "oracle_text": item.get("oracle_text"),
                    "power": item.get("power"),
                    "toughness": item.get("toughness")
                }
                for item in batch
            ]
            query = insert(Card).values(rows)
            query = query.on_conflict_do_update(index_elements=['id'])
            db.session.execute(query)

        db.session.commit()


if __name__ == "__main__":
    import_cards()