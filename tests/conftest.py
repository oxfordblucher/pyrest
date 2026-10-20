from pathlib import Path

import pytest
import responses

from scryapi import create_app, create_tables
from scryapi.config import TestConfig
from scryapi.extensions import db as _db
from scryapi.helpers.populate import import_cards

FIXTURES = Path(__file__).parent / "fixtures"
CARDS_SAMPLE = FIXTURES / "cards_sample.json"


@pytest.fixture(autouse=True)
def no_network():
    """Fail any test that makes an HTTP call through `requests` without mocking it."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        create_tables()
        yield app
        _db.session.remove()
        _db.engine.dispose()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def cards(db):
    """Load the sample Scryfall cards through the real importer."""
    import_cards(CARDS_SAMPLE)
