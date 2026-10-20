import pytest

@pytest.fixture(scope="class")
def my_fix():
    return "3"