from scryapi.models import Notification
from scryapi.models.notification import CARDS_REMOVED
from scryapi.schemas import Json, iso


def _cards_removed_message(data: Json) -> str:
    cards = data["cards"]
    listed = ", ".join(
        f"{c['name']} ×{c['quantity']}" + (f" ({c['board']})" if c["board"] != "main" else "")
        for c in cards
    )
    noun = "card" if len(cards) == 1 else "cards"
    return (
        f"Scryfall no longer lists {len(cards)} {noun} from your deck "
        f"“{data['deck']['name']}”, so {'it was' if len(cards) == 1 else 'they were'} "
        f"removed: {listed}."
    )


_MESSAGES = {CARDS_REMOVED: _cards_removed_message}


def dump_notification(notification: Notification) -> Json:
    return {
        "id": notification.id,
        "kind": notification.kind,
        "message": _MESSAGES[notification.kind](notification.data),
        "data": notification.data,
        "created_at": iso(notification.created_at),
        "read": notification.read_at is not None,
    }
