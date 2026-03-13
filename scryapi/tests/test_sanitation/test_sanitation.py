import pytest
from sanitation.req_sani import PageSanitizer


class MockRequestObj:
    def __init__(self, data):
        self.args = data

class TestSanitation:
    @pytest.mark.parametrize("data,expected", [
        ({
            "page": 3,
            "limit": -45,
            "text": "kinnan"
        }, "Limit needs to be greater than 0"),
        ({
            "page": "two",
            "text": "search your library",
            "limit": -10
        }, "Page needs to be a number, Limit needs to be greater than 0"),
        ({
            "page": 2,
            "limit": "string"
        }, "Limit needs to be a number")
    ])
    def test_fail_pagi(self, data, expected):
        mock_obj = MockRequestObj(data)
        pg_sani = PageSanitizer(req=mock_obj)
        pg_sani.check_pagination()
        errorcode, errorstring = pg_sani.throw_errors()
        assert errorcode == 400 and errorstring == expected

    @pytest.mark.parametrize("data", [
        {
            "page": 1,
            "limit": 20,
            "name": "jhoira"
        },
        {
            "page": 3,
            "limit": 45,
            "text": "search your library"
        },
        {
            "page": 2,
            "text": "cannot be countered"
        }
    ])
    def test_pagi(self, data):
        mock_obj = MockRequestObj(data)
        pg_sani = PageSanitizer(req=mock_obj)
        pg_sani.check_pagination()
        pg_sani.throw_errors()



