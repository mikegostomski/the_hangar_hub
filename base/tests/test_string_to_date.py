from django.test import TestCase
from base.classes.util.env_helper import EnvHelper
from base.services import date_service
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


session = EnvHelper()
est = ZoneInfo("America/New_York")
pst = ZoneInfo("America/Los_Angeles")

class SessionHelperTestCase(TestCase):
    def setUp(self):
        pass

    
    def test_date_strings(self):
        """
        Test string-to-date conversion
        """
        self.assertIsNone(date_service.string_to_date(None))

        test_formats = [
            "31-JAN-2025",
            "2025-01-31",
            "1/31/2025",
            "01/31/25",
            "31/1/25",
            "01/31/25 20:24:45",
            "01/31/25 20:24:45",
            "01/31/25 20:24",
            "01/31/25 8:24 PM",
            "01/31/2025 8:24 pm",
            "January 31, 2025, 8:24 p.m.",
            "Jan 31, 2025, 8:24 p.m.",
            "2025-01-31T20:24:45.498076-05:00",
            "2025-01-31T20:24:45.498076",
            "2025-02-01T01:24:45.498076+00:00",
            "2025-01-31T20:24",
        ]
        for date_string in test_formats:
            dt_utc = date_service.string_to_date(date_string)
            self.assertTrue(type(dt_utc) is datetime, f"Result is not a datetime object: {date_string}")
            self.assertTrue(dt_utc.tzinfo is not None, f"Missing timezone for {date_string}")
            self.assertTrue(dt_utc.tzinfo == timezone.utc, f"Result is not in UTC: {date_string}")

            dt_est = dt_utc.astimezone(est)
            self.assertTrue(dt_est.tzinfo == est, f"Result is not in EST: {date_string}")
            self.assertTrue(dt_est.month == 1, f"Incorrect month for: {date_string}")
            self.assertTrue(dt_est.day == 31, f"Incorrect day for: {date_string}")
            self.assertTrue(dt_est.year == 2025, f"Incorrect year for: {date_string}")
            self.assertTrue(dt_est.hour in [0, 20], f"Incorrect hour ({dt_est.hour}) for: {date_string}")
            self.assertTrue(dt_est.minute in [0, 24], f"Incorrect minute ({dt_est.minute}) for: {date_string}")
            self.assertTrue(dt_est.second in [0, 45], f"Incorrect second ({dt_est.second}) for: {date_string}")

        self.assertTrue(date_service.string_to_date("now").tzinfo == timezone.utc, f"'now' is not in UTC")

        dt = date_service.string_to_date(
            "01/31/2025 5:24 pm", "America/Los_Angeles"
        )
        self.assertTrue(
            dt.astimezone(est).hour == 20,
            f"PST -> EST conversion failed ({dt.astimezone(est).hour} != 20)"
        )

        self.assertIsNone(date_service.string_to_date("garbage"))