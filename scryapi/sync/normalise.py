"""Map Scryfall card objects to `cards` table rows."""

from scryapi.models.card import name_key

# Not real cards: Scryfall's own search hides these by default.
SKIPPED_LAYOUTS = frozenset({"art_series"})

FACE_FIELDS = ("name", "mana_cost", "type_line", "oracle_text", "power", "toughness", "loyalty")


def _image_uri(obj):
    return (obj.get("image_uris") or {}).get("normal")


def _first_face_value(faces, key):
    return next((f[key] for f in faces if f.get(key)), None)


def _join_faces(faces, key, sep):
    values = [f[key] for f in faces if f.get(key)]
    return sep.join(values) if values else None


def should_import(raw):
    return raw.get("object") == "card" and raw.get("layout") not in SKIPPED_LAYOUTS


def normalise_card(raw):
    """Flatten one Scryfall card object into a row dict.

    Multi-face cards (transform, modal DFC, split, adventure, ...) keep some fields only
    on their faces. Text fields are joined across faces so every face is searchable;
    stats (power/toughness/loyalty) fall back to the first face that has them. The
    per-face details are kept in `card_faces`.
    """
    faces = raw.get("card_faces") or []

    def text_field(key, sep):
        return raw.get(key) or _join_faces(faces, key, sep)

    return {
        "scryfall_id": raw["id"],
        "oracle_id": raw.get("oracle_id") or _first_face_value(faces, "oracle_id"),
        "name": raw["name"],
        "sort_name": name_key(raw["name"]),
        "mana_cost": text_field("mana_cost", " // "),
        "cmc": raw.get("cmc"),
        "type_line": text_field("type_line", " // "),
        "oracle_text": text_field("oracle_text", "\n//\n"),
        "power": raw.get("power") or _first_face_value(faces, "power"),
        "toughness": raw.get("toughness") or _first_face_value(faces, "toughness"),
        "loyalty": raw.get("loyalty") or _first_face_value(faces, "loyalty"),
        "colors": raw.get("colors") if "colors" in raw else _face_colors(faces),
        "color_identity": raw.get("color_identity"),
        "layout": raw.get("layout"),
        "card_faces": [
            {**{k: f.get(k) for k in FACE_FIELDS}, "image_uri": _image_uri(f)} for f in faces
        ]
        or None,
        "image_uri": _image_uri(raw) or (_image_uri(faces[0]) if faces else None),
        "scryfall_uri": raw.get("scryfall_uri"),
    }


def _face_colors(faces):
    colors = {c for f in faces for c in f.get("colors") or []}
    return sorted(colors) if faces else None
