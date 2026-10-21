"""End-to-end smoke test against a running scryapi server.

Drives the API the way a browser client would: one cookie-keeping session per user,
the CSRF token fetched once and then taken from each login/register response.

    flask --app scryapi run                         # in one terminal
    python scripts/smoke.py [http://127.0.0.1:5000] # in another

Needs the catalogue loaded (the 21-card sample from tests/fixtures is enough). Creates
two throwaway users with unique names on each run. Exits non-zero on the first failure.
Each run makes 5 requests against the auth rate limit (10/minute by default).
"""

import sys
import time

import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000").rstrip("/")
PASSWORD = "smoke-test-password"


class Client:
    def __init__(self):
        self.http = requests.Session()
        self.csrf = None

    def call(self, method, path, expect, **kwargs):
        headers = kwargs.pop("headers", {})
        if method != "GET" and self.csrf:
            headers["X-CSRFToken"] = self.csrf
        resp = self.http.request(method, BASE + path, headers=headers, timeout=10, **kwargs)
        if resp.status_code != expect:
            fail(f"{method} {path}: expected {expect}, got {resp.status_code}: {resp.text}")
        # Login and register rotate the session, so the token comes back in a header.
        self.csrf = resp.headers.get("X-CSRFToken", self.csrf)
        print(f"  ok  {method:6} {path} -> {resp.status_code}")
        return resp.json() if resp.content else None

    def get(self, path, expect=200, **kw):
        return self.call("GET", path, expect, **kw)

    def post(self, path, expect=200, **kw):
        return self.call("POST", path, expect, **kw)


def fail(message):
    print(f"FAIL {message}")
    sys.exit(1)


def check(condition, message):
    if not condition:
        fail(message)


def signup(name):
    client = Client()
    client.csrf = client.get("/api/auth/csrf")["csrf_token"]
    me = client.post(
        "/api/auth/register",
        201,
        json={"username": name, "email": f"{name}@example.com", "password": PASSWORD},
    )
    check(me["username"] == name, f"register returned {me}")
    return client


def main():
    print(f"Smoke testing {BASE}")
    anon = Client()
    try:
        anon.get("/api/cards?limit=1")
    except requests.ConnectionError:
        fail(f"no server at {BASE}; start one with `flask --app scryapi run`")

    print("cards")
    page = anon.get("/api/cards?name=counterspell")
    check(page["total"] > 0, "no cards loaded; run `flask --app scryapi sync-cards` first")
    card = next((c for c in page["results"] if c["name"] == "Counterspell"), None)
    check(card is not None, "Counterspell not found by name")
    check(anon.get(f"/api/cards/{card['id']}")["name"] == "Counterspell", "card lookup")
    hits = anon.get("/api/cards?text=counter%20target%20spell&type=instant&name=counter")["results"]
    check(any(c["id"] == card["id"] for c in hits), "full-text search missed Counterspell")
    anon.get('/api/cards?text="unbalanced', expect=200)  # odd syntax is not an error
    anon.get("/api/cards?page=0", expect=400)
    anon.get("/api/cards/no-such-card", expect=404)

    print("auth")
    suffix = str(int(time.time() * 1000))[-9:]
    alice = signup(f"alice_{suffix}")
    bob = signup(f"bob_{suffix}")
    me = alice.get("/api/auth/me")
    check(me["username"] == f"alice_{suffix}" and me["unread_notifications"] == 0, "me")
    check(alice.get("/api/notifications")["total"] == 0, "new users have no notifications")
    anon.get("/api/notifications", expect=401)
    anon.get("/api/auth/me", expect=401)
    Client().post("/api/auth/login", 400, json={"login": "x", "password": "y"})  # no CSRF

    print("change password")
    laptop = Client()
    laptop.csrf = laptop.get("/api/auth/csrf")["csrf_token"]
    laptop.post("/api/auth/login", json={"login": f"alice_{suffix}", "password": PASSWORD})
    new_password = PASSWORD + "-changed"
    change = {"current_password": PASSWORD, "new_password": new_password}
    alice.post("/api/auth/password", 400, json={**change, "current_password": "wrong-password!"})
    alice.post("/api/auth/password", json=change)
    alice.get("/api/auth/me")  # still signed in here, with the rotated CSRF token
    laptop.get("/api/auth/me", expect=401)  # signed out everywhere else

    print("decks")
    public = alice.post("/api/decks", 201, json={"name": "Counters", "is_public": True})
    private = alice.post("/api/decks", 201, json={"name": "Secret"})
    deck = alice.call(
        "PUT",
        f"/api/decks/{public['id']}/cards",
        200,
        json={
            "cards": [
                {"card_id": card["id"], "quantity": 4},
                {"card_id": card["id"], "quantity": 1, "board": "side"},
            ]
        },
    )
    check(deck["card_count"] == 5, f"card_count {deck['card_count']}")
    patched = alice.call("PATCH", f"/api/decks/{public['id']}", 200, json={"format": "Modern"})
    problems = [p["code"] for p in patched["legality"]["problems"]]
    check(problems == ["deck_too_small", "too_many_copies"], f"legality {patched['legality']}")
    check(anon.get(f"/api/decks/{public['id']}")["format"] == "modern", "public deck view")
    alice.call("PATCH", f"/api/decks/{public['id']}", 400, json={"format": "kitchen table"})
    formats = {f["key"] for f in anon.get("/api/formats")["results"]}
    check({"modern", "commander"} <= formats, "format list")
    anon.get(f"/api/decks/{private['id']}", expect=404)
    bob.get(f"/api/decks/{private['id']}", expect=404)
    bob.call("PATCH", f"/api/decks/{public['id']}", 403, json={"name": "Mine now"})
    anon.csrf = anon.get("/api/auth/csrf")["csrf_token"]  # else CSRF rejects it first (400)
    anon.post("/api/decks", 401, json={"name": "Nope"})
    mine = alice.get("/api/decks/mine")
    check(mine["total"] == 2, f"alice owns {mine['total']} decks")
    ids = [d["id"] for d in anon.get("/api/decks/public?limit=50")["results"]]
    check(public["id"] in ids and private["id"] not in ids, "public deck listing")

    print("users")
    profile = anon.get(f"/api/users/alice_{suffix}")
    check("email" not in profile, "public profile leaks email")
    decks = anon.get(f"/api/users/alice_{suffix}/decks")["results"]
    check([d["id"] for d in decks] == [public["id"]], "user's public decks")

    print("cleanup")
    alice.call("DELETE", f"/api/decks/{private['id']}", 204)
    alice.call("DELETE", f"/api/decks/{public['id']}", 204)
    alice.post("/api/auth/logout", 204)
    alice.get("/api/auth/me", expect=401)

    print("All smoke checks passed.")


if __name__ == "__main__":
    main()
