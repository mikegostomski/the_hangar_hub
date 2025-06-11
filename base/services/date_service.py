import math
from datetime import datetime, timezone
from base.fixtures.timezones import timezones
from base.classes.util.log import Log
from zoneinfo import ZoneInfo
import pandas
import arrow

log = Log()


def string_to_date(date_string, source_timezone=None):
    """
    Convert any reasonable date string into a date.
    The resulting dates will be UTC
    If no source timezone is given, and date string has no offset, assume New York
    """
    if date_string is None:
        return None

    if str(date_string).lower() == "now":
        return datetime.now(timezone.utc)

    dt = None
    try:
        # Use pandas to convert date string
        if isinstance(date_string, str):
            try:
                dt = pandas.to_datetime(date_string).to_pydatetime()
            except Exception as ee:
                log.warning(f"Pandas cannot convert string to date ({ee})")

        elif isinstance(date_string, datetime):
            dt = date_string

        else:
            log.warning(f"String to date received a non-string: {type(date_string)}")

        if dt and dt.tzinfo is None:
            tz = ZoneInfo(source_timezone or "America/New_York")
            dt = dt.replace(tzinfo=tz)

        return dt.astimezone(timezone.utc) if dt else None
    except Exception as ee:
        log.error(f"Error converting string to date: {ee}")
        return None


def humanize(datetime_instance):
    return arrow.get(datetime_instance).humanize()


def seconds_to_duration_description(num_seconds):
    """Given a number of seconds, return a text description of how long it is"""
    # Pull out days
    num_days = math.floor(num_seconds / 60 / 60 / 24)
    num_seconds -= (num_days * 60 * 60 * 24)
    # Pull out hours
    num_hours = math.floor(num_seconds / 60 / 60)
    num_seconds = num_seconds - (num_hours * 60 * 60)
    # Pull out minutes
    num_mins = math.floor(num_seconds / 60)
    num_seconds = num_seconds - (num_mins * 60)

    # Build a descriptive string
    description = []
    if num_days:
        description.append(f"{num_days} day{'s' if num_days != 1 else ''},")
    if num_hours:
        description.append(f"{num_hours} hour{'s' if num_hours != 1 else ''},")
    if num_mins:
        description.append(f"{num_mins} minute{'s' if num_mins != 1 else ''}")
    if num_seconds or not description:
        if description:
            description.append("and")
        description.append(f"{num_seconds} second{'s' if num_seconds != 1 else ''}")
    return ' '.join(description).strip(' ,')

def timezone_options():
    return {x:x for x in timezones}