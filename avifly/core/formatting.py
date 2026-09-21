"""Number, money, area and duration formatting used by templates and exports."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings

EMPTY = "—"


def to_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def format_number(value, places: int = 0) -> str:
    number = to_decimal(value)
    if number is None:
        return EMPTY
    quantum = Decimal(1).scaleb(-places)
    return f"{number.quantize(quantum, rounding=ROUND_HALF_UP):,.{places}f}"


def format_money(value, currency: str | None = "") -> str:
    """``12160`` → ``"12,160 MKD"``; decimals are only shown when there are any."""
    number = to_decimal(value)
    if number is None:
        return EMPTY
    places = 0 if number == number.to_integral_value() else 2
    text = format_number(number, places)
    if currency == "":
        from avifly.core.models import get_business_settings

        currency = get_business_settings().currency
    return f"{text} {currency}" if currency else text


def format_hectares(value) -> str:
    number = to_decimal(value)
    return EMPTY if number is None else f"{format_number(number, 2)} ha"


def format_duration(minutes) -> str:
    """``320`` → ``"5 h 20 min"``."""
    if minutes is None:
        return EMPTY
    minutes = int(minutes)
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    return f"{hours} h" if hours else f"{rest} min"


def format_date(value) -> str:
    """``date(2026, 6, 1)`` → ``"01.06.2026"`` (anything else is shown as-is)."""
    return value.strftime("%d.%m.%Y") if hasattr(value, "strftime") else str(value or EMPTY)


def round_money(value: Decimal) -> Decimal:
    """Round a calculated amount to the configured step (whole denars by default)."""
    quantum = Decimal(settings.AVIFLY_MONEY_QUANTUM)
    return value.quantize(quantum, rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))
