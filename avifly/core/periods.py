"""Named date ranges ("this month", "last season", …) used by filters and reports.

A *season* is a calendar year.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

PRESETS = {
    "this_month": _("This month"),
    "last_month": _("Last month"),
    "this_season": _("This season"),
    "last_season": _("Last season"),
    "last_12_months": _("Last 12 months"),
    "all": _("All time"),
    "custom": _("Custom"),
}


@dataclass(frozen=True)
class Period:
    start: date | None
    end: date | None
    label: str

    def contains(self, day: date) -> bool:
        return (self.start is None or day >= self.start) and (self.end is None or day <= self.end)

    def previous(self) -> Period | None:
        """The equally long period just before this one (for comparisons)."""
        if self.start is None or self.end is None:
            return None
        if (
            self.start.month == 1
            and self.start.day == 1
            and self.end == date(self.start.year, 12, 31)
        ):
            year = self.start.year - 1
            return Period(date(year, 1, 1), date(year, 12, 31), str(year))
        length = self.end - self.start
        end = self.start - timedelta(days=1)
        return Period(end - length, end, "")


def month_bounds(day: date) -> tuple[date, date]:
    first = day.replace(day=1)
    next_first = (first + timedelta(days=32)).replace(day=1)
    return first, next_first - timedelta(days=1)


def resolve_period(preset: str, start: date | None = None, end: date | None = None) -> Period:
    today = timezone.localdate()
    if preset == "this_month":
        first, last = month_bounds(today)
        return Period(first, last, today.strftime("%B %Y"))
    if preset == "last_month":
        first, last = month_bounds(today.replace(day=1) - timedelta(days=1))
        return Period(first, last, first.strftime("%B %Y"))
    if preset == "this_season":
        return Period(date(today.year, 1, 1), date(today.year, 12, 31), str(today.year))
    if preset == "last_season":
        year = today.year - 1
        return Period(date(year, 1, 1), date(year, 12, 31), str(year))
    if preset == "last_12_months":
        return Period(today - timedelta(days=364), today, str(PRESETS["last_12_months"]))
    if preset == "custom" and (start or end):
        return Period(start, end, str(PRESETS["custom"]))
    return Period(None, None, str(PRESETS["all"]))
