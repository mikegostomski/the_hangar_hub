from base.services import date_service
from base.classes.util.log import Log
import arrow
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

log = Log()


class DateHelper:
    # All dates will be UTC

    # Allow formatted dates to be printed in specified timezone
    format_as_timezone = "UTC"

    # The user-entered value
    original_value = None

    # A datetime object to be used as you see fit
    datetime_instance = None

    # An Arrow object to be used as you see fit
    # https://arrow.readthedocs.io/en/latest/
    arrow_instance = None

    # If an error is encountered while converting string to date, save error here
    conversion_error = None

    def get_next_specified_day(self, day_of_week):
        start = self.datetime_instance
        if not start:
            return None

        days = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4, "S": 5, "U": 6}

        if not day_of_week:
            log.warning("Missing day of week")
            return None

        if day_of_week in range(0, 6):
            target = day_of_week

        else:
            target = None
            if day_of_week not in days:
                if str(day_of_week).lower().startswith("m"):
                    day_of_week = "M"
                elif str(day_of_week).lower().startswith("tu"):
                    day_of_week = "T"
                elif str(day_of_week).lower().startswith("w"):
                    day_of_week = "W"
                elif str(day_of_week).lower().startswith("th"):
                    day_of_week = "R"
                elif str(day_of_week).lower().startswith("f"):
                    day_of_week = "F"
                elif str(day_of_week).lower().startswith("sa"):
                    day_of_week = "S"
                elif str(day_of_week).lower().startswith("su"):
                    day_of_week = "U"
                else:
                    log.warning(f"Invalid day of week: {day_of_week}")
                    return None
            target = days.get(day_of_week)

        next_day = start + timedelta((target - start.weekday()) % 7)

        if next_day.date() == start.date():
            next_day = next_day + timedelta(days=7)

        return next_day

    def minus(self, num_days):
        self.datetime_instance = self.datetime_instance - timedelta(days=num_days)
        self.arrow_instance = arrow.get(self.datetime_instance)
        return self

    def plus(self, num_days):
        self.datetime_instance = self.datetime_instance + timedelta(days=num_days)
        self.arrow_instance = arrow.get(self.datetime_instance)
        return self

    def date_field(self):
        """Date to be used as value="" in a date input"""
        return self.format("YYYY-MM-DD")

    def timestamp(self):
        """Unambiguous date string to the second"""
        return self.format("YYYY-MM-DD HH:mm:ss")

    def banner_date(self):
        """The format Banner users expect to see"""
        return self.format("DD-MMM-YYYY").upper()

    def banner_date_time(self):
        """The format Banner users expect to see"""
        return self.format("DD-MMM-YYYY HH:mm").upper()

    def time(self):
        """Time in 12-hour (AM/PM) format"""
        return self.format("h:mm a")

    def time24(self):
        """Time in 24-hour format"""
        return self.format("HH:mm")

    def iso(self):
        """Date/Time in ISO format"""
        if not self.datetime_instance.tzinfo:
            self.localize()
        return self.datetime_instance.isoformat()

    def humanized(self, compared_to="now", granularity="auto"):
        """
        A vague description of a date/time
        granularity: ["second", "minute", "hour", "day", "week", "month" or "year"]
        """
        if self.arrow_instance:
            return self.arrow_instance.humanize(
                DateHelper(compared_to).arrow_instance, granularity=granularity
            )
        else:
            return ""

    def humanize(self, compared_to="now", granularity="auto"):
        return self.humanized(compared_to, granularity)

    def format(self, format_string="MMMM D, YYYY"):
        """
        Format a date using Arrow's formatting patterns, which are more intuitive
        https://arrow.readthedocs.io/en/latest/
        """
        if self.arrow_instance:
            tz_date = self.arrow_instance.to(self.format_as_timezone)
            return tz_date.format(format_string)
        else:
            return ""

    def __init__(self, date_string, source_timezone="UTC", format_as_timezone="UTC"):
        self.format_as_timezone = format_as_timezone
        if date_string:
            self.original_value = date_string

            try:
                # Convert the date string to a datetime instance
                self.datetime_instance = date_service.string_to_date(date_string, source_timezone)
                if self.datetime_instance is None:
                    self.conversion_error = "Unable to convert given date string"

            except Exception as ee:
                self.conversion_error = ee

            if self.datetime_instance:
                self.arrow_instance = arrow.get(self.datetime_instance)

    def __str__(self):
        return self.timestamp()
