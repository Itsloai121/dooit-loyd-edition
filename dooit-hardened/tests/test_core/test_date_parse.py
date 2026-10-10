from datetime import datetime
import unittest
from dooit.utils.date_parser import parse


class TestDateParse(unittest.TestCase):
    def test_parsers(self):
        # normal format date
        assert parse("2020-01-01") == (datetime(2020, 1, 1), True)

        # invalid date
        assert parse("?????") == (None, False)

        # english date formats
        assert parse("july 1 2034") == (datetime(2034, 7, 1), True)
        assert parse("jan 1") == (datetime(datetime.now().year, 1, 1), True)
