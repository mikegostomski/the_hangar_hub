from django.test import TestCase
from base.classes.util.env_helper import EnvHelper
from base.classes.util.date_helper import DateHelper
from base.services import date_service
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


session = EnvHelper()
est = ZoneInfo("America/New_York")
pst = ZoneInfo("America/Los_Angeles")

class DateHelperTestCase(TestCase):
    def setUp(self):
        pass

    
    def test_date_strings(self):
        """
        Test string-to-date conversion
        """
        # Null date is not an error, just an empty date helper
        self.assertIsNone(DateHelper(None).conversion_error)
        self.assertIsNone(DateHelper(None).datetime_instance)

        dh = DateHelper("01-31-2025", "UTC")
        self.assertIsNone(dh.conversion_error)
        self.assertIsNotNone(dh.datetime_instance)
        self.assertIsNotNone(dh.arrow_instance)
        self.assertEqual(dh.date_field(), "2025-01-31")
        self.assertEqual(dh.banner_date(), "31-JAN-2025")
        self.assertEqual(dh.timestamp(), "2025-01-31 00:00:00")
        self.assertEqual(DateHelper("yesterday").humanized(), "a day ago")