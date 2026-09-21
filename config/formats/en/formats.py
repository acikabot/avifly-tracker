"""Date/number formats: English text with the day-first dates used in Macedonia."""

DATE_FORMAT = "d.m.Y"
SHORT_DATE_FORMAT = "d.m.Y"
DATETIME_FORMAT = "d.m.Y H:i"
SHORT_DATETIME_FORMAT = "d.m.Y H:i"
TIME_FORMAT = "H:i"
MONTH_DAY_FORMAT = "j F"
YEAR_MONTH_FORMAT = "F Y"
FIRST_DAY_OF_WEEK = 1  # Monday

DATE_INPUT_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"]
TIME_INPUT_FORMATS = ["%H:%M", "%H:%M:%S"]
DATETIME_INPUT_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%d.%m.%Y %H:%M"]

DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","
NUMBER_GROUPING = 3
