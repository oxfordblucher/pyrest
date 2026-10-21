import pytest

from scryapi.models import User
from tests.conftest import PASSWORD, ApiClient, csrf_headers, register

ME_KEYS = {"username", "email", "created_at"}


def login(client, login_value="alice", password=PASSWORD, **extra):
    return client.post(
        "/api/auth/login",
        json={"login": login_value, "password": password, **extra},
        headers=csrf_headers(client),
    )


# --- register ----------------------------------------------------------------------


def test_register_creates_user_and_logs_in(client, db):
    resp = register(client, "Alice", email="Alice@Example.com")
    body = resp.get_json()
    assert set(body) == ME_KEYS
    assert body["username"] == "alice"  # normalised
    assert body["email"] == "alice@example.com"
    assert body["created_at"].endswith("Z")
    assert client.get("/api/auth/me").get_json()["username"] == "alice"


def test_password_is_hashed(client, db):
    register(client)
    user = db.session.execute(db.select(User)).scalar_one()
    assert PASSWORD not in user.password_hash
    assert user.password_hash.startswith(("scrypt:", "pbkdf2:"))


@pytest.mark.parametrize(
    "body,fields",
    [
        ({}, {"username", "email", "password"}),
        ({"username": "al", "email": "a@b.co", "password": PASSWORD}, {"username"}),
        ({"username": "has space", "email": "a@b.co", "password": PASSWORD}, {"username"}),
        ({"username": "alice", "email": "not-an-email", "password": PASSWORD}, {"email"}),
        ({"username": "alice", "email": "a@b.co", "password": "short"}, {"password"}),
        ({"username": "alice", "email": "a@b.co", "password": "x" * 129}, {"password"}),
        ({"username": 5, "email": "a@b.co", "password": PASSWORD}, {"username"}),
    ],
)
def test_register_validation(client, body, fields):
    resp = client.post("/api/auth/register", json=body, headers=csrf_headers(client))
    assert resp.status_code == 400
    assert {d["field"] for d in resp.get_json()["details"]} == fields


def test_register_requires_json_object(client):
    resp = client.post("/api/auth/register", data="nope", headers=csrf_headers(client))
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "validation_error"


@pytest.mark.parametrize(
    "username,email,field",
    [("ALICE", "other@example.com", "username"), ("other", "ALICE@example.com", "email")],
)
def test_register_duplicate_is_409(app, username, email, field):
    register(app.test_client(), "alice")
    client = app.test_client()
    resp = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": PASSWORD},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "conflict"
    assert [d["field"] for d in resp.get_json()["details"]] == [field]


# --- login / logout / me --------------------------------------------------------------


@pytest.fixture
def registered(app):
    register(app.test_client(), "alice")


@pytest.mark.parametrize("login_value", ["alice", "ALICE", "alice@example.com"])
def test_login_by_username_or_email(client, registered, login_value):
    resp = login(client, login_value)
    assert resp.status_code == 200
    assert set(resp.get_json()) == ME_KEYS
    assert client.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize(
    "login_value,password", [("alice", "wrong password!"), ("nobody", PASSWORD)]
)
def test_login_failure_is_generic_401(client, registered, login_value, password):
    resp = login(client, login_value, password)
    assert resp.status_code == 401
    assert resp.get_json()["message"] == "Invalid username/email or password"
    assert client.get("/api/auth/me").status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "unauthorized"


def test_logout(client, registered):
    login(client)
    resp = client.post("/api/auth/logout", headers=csrf_headers(client))
    assert resp.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_login_rotates_session_and_returns_new_csrf_token(client, registered):
    before = csrf_headers(client)["X-CSRFToken"]
    resp = login(client)
    after = resp.headers["X-CSRFToken"]
    assert after and after != before
    # The new token works; the pre-login one doesn't.
    stale = client.post("/api/auth/logout", headers={"X-CSRFToken": before})
    assert stale.get_json()["error"] == "csrf_failed"
    ok = client.post("/api/auth/logout", headers={"X-CSRFToken": after})
    assert ok.status_code == 204


def test_remember_me_sets_cookie(client, registered):
    login(client, remember=True)
    assert client.get_cookie("remember_token") is not None


def test_session_cookie_flags(client, registered):
    login(client)
    cookie = client.get_cookie("session")
    assert cookie.http_only
    assert cookie.same_site == "Lax"


# --- CSRF ----------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/auth/register", "/api/auth/login", "/api/auth/logout"])
def test_mutations_without_csrf_token_are_rejected(client, path):
    resp = client.post(path, json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "csrf_failed"


def test_csrf_token_from_other_session_is_rejected(app):
    token = csrf_headers(app.test_client())
    resp = app.test_client().post("/api/auth/login", json={}, headers=token)
    assert resp.get_json()["error"] == "csrf_failed"


# --- public profiles -------------------------------------------------------------------


def test_public_profile_hides_email(client, registered):
    resp = client.get("/api/users/ALICE")
    assert resp.status_code == 200
    assert set(resp.get_json()) == {"username", "created_at"}


def test_unknown_profile_is_404(client):
    assert client.get("/api/users/nobody").status_code == 404


def test_no_user_directory(client, registered):
    assert client.get("/api/users").status_code == 404


# --- change password ---------------------------------------------------------------

NEW_PASSWORD = "a brand new passphrase"


def change_password(api, current=PASSWORD, new=NEW_PASSWORD):
    return api.post("/api/auth/password", json={"current_password": current, "new_password": new})


def test_change_password(app, alice):
    resp = change_password(alice)
    assert resp.status_code == 200
    assert set(resp.get_json()) == ME_KEYS
    assert resp.headers["X-CSRFToken"]
    assert alice.get("/api/auth/me").status_code == 200  # this device stays signed in
    fresh = app.test_client()
    assert login(fresh, password=PASSWORD).status_code == 401
    assert login(fresh, password=NEW_PASSWORD).status_code == 200


def test_change_password_wrong_current_password(app, alice):
    resp = change_password(alice, current="not my password at all")
    assert resp.status_code == 400
    assert resp.get_json()["details"] == [{"field": "current_password", "message": "is incorrect"}]
    assert login(app.test_client(), password=PASSWORD).status_code == 200


@pytest.mark.parametrize(
    "body,field",
    [
        ({"current_password": PASSWORD, "new_password": "short"}, "new_password"),
        ({"current_password": PASSWORD, "new_password": "x" * 129}, "new_password"),
        ({"new_password": NEW_PASSWORD}, "current_password"),
        ({"current_password": PASSWORD, "new_password": 123}, "new_password"),
    ],
)
def test_change_password_validation(alice, body, field):
    resp = alice.post("/api/auth/password", json=body)
    assert resp.status_code == 400
    assert field in {d["field"] for d in resp.get_json()["details"]}


def test_change_password_requires_login(anon):
    assert change_password(anon).status_code == 401


def test_change_password_signs_out_other_sessions(app, alice):
    other = app.test_client()
    login(other)
    assert other.get("/api/auth/me").status_code == 200
    change_password(alice)
    assert other.get("/api/auth/me").status_code == 401


def test_change_password_invalidates_other_remember_cookies(app, alice):
    other = app.test_client()
    login(other, remember=True)
    other.delete_cookie("session")
    assert other.get("/api/auth/me").status_code == 200  # restored from remember cookie
    other.delete_cookie("session")
    change_password(alice)
    assert other.get("/api/auth/me").status_code == 401


def test_change_password_reissues_remember_cookie(client, registered):
    login(client, remember=True)
    before = client.get_cookie("remember_token").value
    change_password(ApiClient(client))
    after = client.get_cookie("remember_token").value
    assert after != before
    client.delete_cookie("session")
    assert client.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize("login_id", ["1", "1:x", "x:1", "", "999:1"])
def test_malformed_or_unknown_login_ids_are_signed_out(app, db, login_id):
    from scryapi import load_user

    assert load_user(login_id) is None
