"""Analytics queries: headline numbers and chart data for a period and filters.

Everything is computed from jobs (done or in progress), their days, and — when the
money module is on — payments and costs. Averages per hectare are area-weighted
(total ÷ total hectares), so one small job at a high price can't skew them.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Min, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from avifly.core.formatting import format_hectares, format_money, format_number
from avifly.core.periods import Period
from avifly.core.registry import registry
from avifly.customers.models import Customer
from avifly.equipment.models import Equipment, EquipmentType
from avifly.jobs.models import Crop, Job, JobDay, OperationType

ZERO = Decimal(0)
TOP_N = 10


@dataclass(frozen=True)
class Filters:
    period: Period
    operation: OperationType | None = None
    crop: Crop | None = None
    customer: Customer | None = None
    equipment: Equipment | None = None

    @property
    def splits_jobs(self) -> bool:
        """True when only some jobs are included (costs can't be split that way)."""
        return any((self.operation, self.crop, self.customer, self.equipment))

    def with_period(self, period: Period) -> Filters:
        return Filters(period, self.operation, self.crop, self.customer, self.equipment)


def money_enabled() -> bool:
    return registry.is_enabled("money")


def _between(qs, period: Period, field_name: str):
    if period.start:
        qs = qs.filter(**{f"{field_name}__gte": period.start})
    if period.end:
        qs = qs.filter(**{f"{field_name}__lte": period.end})
    return qs


def job_scope(filters: Filters):
    """Worked jobs matching the filters (any date)."""
    qs = Job.objects.worked()
    if filters.operation:
        qs = qs.filter(operation_type=filters.operation)
    if filters.crop:
        qs = qs.filter(crop=filters.crop)
    if filters.customer:
        qs = qs.filter(customer=filters.customer)
    if filters.equipment:
        qs = qs.filter(pk__in=JobDay.objects.filter(equipment=filters.equipment).values("job"))
    return qs


def jobs_in(filters: Filters):
    return _between(job_scope(filters), filters.period, "end_date")


def days_in(filters: Filters):
    qs = JobDay.objects.filter(job__in=job_scope(filters).values("pk"))
    if filters.equipment:
        qs = qs.filter(equipment=filters.equipment)
    return _between(qs, filters.period, "date")


def payments_in(filters: Filters):
    from avifly.money.models import Payment

    qs = _between(Payment.objects.all(), filters.period, "date")
    if filters.splits_jobs:
        qs = qs.filter(job__in=job_scope(filters).values("pk"))
    return qs


def costs_in(filters: Filters):
    """Costs in the period, or ``None`` when the filters can't apply to costs."""
    from avifly.money.models import Cost

    if filters.operation or filters.crop or filters.customer:
        return None
    qs = _between(Cost.objects.all(), filters.period, "date")
    if filters.equipment:
        qs = qs.filter(equipment=filters.equipment)
    return qs


def data_bounds(filters: Filters) -> tuple[date, date]:
    """The period, with open ends closed by the data (for building month/week axes)."""
    today = timezone.localdate()
    start, end = filters.period.start, filters.period.end
    if start is None:
        first = job_scope(filters).aggregate(first=Min("start_date"))["first"]
        start = first or today.replace(month=1, day=1)
    if end is None or end > today:
        end = max(today, start)
    return start, end


# -- headline numbers --------------------------------------------------------------------
@dataclass
class Kpi:
    key: str
    label: str
    value: Decimal | int | None
    kind: str  # money, money_per_ha, ha, ha_per_hour, count, percent
    previous: Decimal | int | None = None
    up_is_good: bool = True
    note: str = ""

    @property
    def display(self) -> str:
        return format_value(self.value, self.kind)

    @property
    def change(self) -> Decimal | None:
        if self.value is None or self.previous in (None, 0):
            return None
        return (Decimal(self.value) - Decimal(self.previous)) / abs(Decimal(self.previous)) * 100

    @property
    def change_abs(self) -> Decimal | None:
        change = self.change
        return abs(change) if change is not None else None

    @property
    def change_is_good(self) -> bool | None:
        change = self.change
        if change is None or change == 0:
            return None
        return (change > 0) == self.up_is_good


def format_value(value, kind: str) -> str:
    if value is None:
        return "—"
    if kind in ("money", "money_per_ha"):
        value = Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    if kind == "money":
        return format_money(value)
    if kind == "money_per_ha":
        return f"{format_money(value)}/ha"
    if kind == "ha":
        return format_hectares(value)
    if kind == "ha_per_hour":
        return f"{format_number(value, 1)} ha/h"
    if kind == "percent":
        return f"{format_number(value, 0)}%"
    if kind == "hours":
        return f"{format_number(value, 0)} h"
    return format_number(value, 0)


def _ratio(a, b) -> Decimal | None:
    if a is None or not b:
        return None
    return Decimal(a) / Decimal(b)


def raw_numbers(filters: Filters) -> dict:
    jobs = jobs_in(filters)
    agg = jobs.aggregate(
        jobs=Count("pk"),
        hectares=Sum("total_hectares"),
        charged=Sum("total_amount"),
        extras=Sum("extras_amount"),
        customers=Count("customer", distinct=True),
    )
    hectares = agg["hectares"] or ZERO
    days = days_in(filters)
    timed = days.filter(duration_minutes__gt=0).aggregate(
        ha=Sum("hectares"), minutes=Sum("duration_minutes")
    )
    working_days = days.values("date").distinct().count()

    new_customers = None
    if filters.period.start:
        firsts = (
            Job.objects.worked()
            .values("customer")
            .annotate(first=Min("end_date"))
            .filter(customer__in=jobs.values("customer"), first__gte=filters.period.start)
        )
        new_customers = firsts.count()

    numbers = {
        "jobs": agg["jobs"],
        "hectares": hectares,
        "charged": agg["charged"] or ZERO,
        "extras": agg["extras"] or ZERO,
        "customers": agg["customers"],
        "new_customers": new_customers,
        "working_days": working_days,
        "work_hours": Decimal(timed["minutes"] or 0) / 60,
        "ha_per_hour": _ratio(timed["ha"], Decimal(timed["minutes"] or 0) / 60),
        "received": None,
        "costs": None,
    }
    if money_enabled():
        numbers["received"] = payments_in(filters).aggregate(s=Sum("amount"))["s"] or ZERO
        costs = costs_in(filters)
        if costs is not None:
            numbers["costs"] = costs.aggregate(s=Sum("amount"))["s"] or ZERO
    return numbers


def kpis(filters: Filters) -> list[Kpi]:
    now = raw_numbers(filters)
    previous_period = filters.period.previous()
    before = raw_numbers(filters.with_period(previous_period)) if previous_period else {}

    def prev(key):
        return before.get(key) if before else None

    ha = now["hectares"]
    income = now["received"] if now["received"] is not None else now["charged"]
    profit = income - now["costs"] if now["costs"] is not None else None
    prev_income = prev("received") if prev("received") is not None else prev("charged")
    prev_profit = (
        prev_income - prev("costs")
        if prev("costs") is not None and prev_income is not None
        else None
    )
    items = [
        Kpi("charged", _("Charged"), now["charged"], "money", prev("charged")),
    ]
    if now["received"] is not None:
        items.append(Kpi("received", _("Received"), now["received"], "money", prev("received")))
    if money_enabled():
        cost_note = "" if now["costs"] is not None else _("Costs can't be split by this filter")
        items += [
            Kpi("costs", _("Costs"), now["costs"], "money", prev("costs"), False, cost_note),
            Kpi("profit", _("Profit"), profit, "money", prev_profit),
            Kpi(
                "margin",
                _("Margin"),
                _ratio(profit, income) * 100 if profit is not None and income else None,
                "percent",
                (_ratio(prev_profit, prev_income) or 0) * 100 if prev_profit is not None else None,
            ),
        ]
    items += [
        Kpi("hectares", _("Hectares"), ha, "ha", prev("hectares")),
        Kpi("jobs", _("Jobs"), now["jobs"], "count", prev("jobs")),
        Kpi(
            "customers",
            _("Customers"),
            now["customers"],
            "count",
            prev("customers"),
            note=(
                _("%(n)d new") % {"n": now["new_customers"]}
                if now["new_customers"] is not None
                else ""
            ),
        ),
        Kpi(
            "price_per_ha",
            _("Avg price / ha"),
            _ratio(now["charged"], ha),
            "money_per_ha",
            _ratio(prev("charged"), prev("hectares")),
        ),
    ]
    if money_enabled():
        items += [
            Kpi(
                "cost_per_ha",
                _("Avg cost / ha"),
                _ratio(now["costs"], ha),
                "money_per_ha",
                _ratio(prev("costs"), prev("hectares")),
                False,
            ),
            Kpi(
                "profit_per_ha",
                _("Avg profit / ha"),
                _ratio(profit, ha),
                "money_per_ha",
                _ratio(prev_profit, prev("hectares")),
            ),
        ]
    items += [
        Kpi(
            "job_size",
            _("Avg job size"),
            _ratio(ha, now["jobs"]),
            "ha",
            _ratio(prev("hectares"), prev("jobs")),
        ),
        Kpi(
            "ha_per_hour",
            _("Hectares per hour"),
            now["ha_per_hour"],
            "ha_per_hour",
            prev("ha_per_hour"),
        ),
        Kpi(
            "per_day",
            _("Charged per working day"),
            _ratio(now["charged"], now["working_days"]),
            "money",
            _ratio(prev("charged"), prev("working_days")),
            note=_("%(n)d working days") % {"n": now["working_days"]},
        ),
        Kpi("extras", _("Extra charges"), now["extras"], "money", prev("extras")),
    ]
    return items


# -- chart helpers ---------------------------------------------------------------------------
def month_starts(start: date, end: date) -> list[date]:
    months, current = [], start.replace(day=1)
    while current <= end:
        months.append(current)
        current = (current + timedelta(days=32)).replace(day=1)
    return months


def week_starts(start: date, end: date) -> list[date]:
    weeks, current = [], start - timedelta(days=start.weekday())
    while current <= end:
        weeks.append(current)
        current += timedelta(days=7)
    return weeks


def _month_key(day: date) -> date:
    return day.replace(day=1)


def _week_key(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _f(value) -> float:
    return float(value or 0)


@dataclass
class Chart:
    key: str
    title: str
    kind: str
    unit: str
    subtitle: str = ""
    data: dict = field(default_factory=dict)
    table_columns: list[str] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)
    wide: bool = False

    def as_json(self) -> dict:
        return {"key": self.key, "kind": self.kind, "unit": self.unit, **self.data}

    @property
    def is_empty(self) -> bool:
        return not self.table_rows


def money_by_month(filters: Filters) -> Chart | None:
    if not money_enabled():
        return None
    start, end = data_bounds(filters)
    months = month_starts(start, end)
    income = defaultdict(Decimal)
    for day, amount in payments_in(filters).values_list("date", "amount"):
        income[_month_key(day)] += amount
    costs = defaultdict(Decimal)
    cost_qs = costs_in(filters)
    if cost_qs is not None:
        for day, amount in cost_qs.values_list("date", "amount"):
            costs[_month_key(day)] += amount
    labels = [m.strftime("%b %Y") for m in months]
    received = [income[m] for m in months]
    spent = [costs[m] for m in months]
    profit = [income[m] - costs[m] for m in months]
    series = [{"name": _("Received"), "type": "bar", "slot": 0, "data": [_f(v) for v in received]}]
    if cost_qs is not None:
        series += [
            {"name": _("Costs"), "type": "bar", "slot": 1, "data": [_f(v) for v in spent]},
            {"name": _("Profit"), "type": "line", "slot": 2, "data": [_f(v) for v in profit]},
        ]
    rows = [
        [
            label,
            format_money(r),
            format_money(s) if cost_qs is not None else "—",
            format_money(p) if cost_qs is not None else "—",
        ]
        for label, r, s, p in zip(labels, received, spent, profit, strict=True)
        if r or s
    ]
    return Chart(
        "money_months",
        _("Money in and out per month"),
        "combo",
        "money",
        data={"categories": labels, "series": series},
        table_columns=[_("Month"), _("Received"), _("Costs"), _("Profit")],
        table_rows=rows,
        wide=True,
    )


def running_profit(filters: Filters) -> Chart | None:
    """Cumulative profit through the season, this season against last."""
    if not money_enabled() or filters.splits_jobs:
        return None
    from avifly.money.models import Cost, Payment

    year = (filters.period.end or timezone.localdate()).year
    today = timezone.localdate()
    weeks = [date(year, 1, 1) + timedelta(days=7 * n) for n in range(53)]
    series, rows = [], []
    for offset, slot in ((1, "muted"), (0, 0)):
        season = year - offset
        flows = defaultdict(Decimal)
        for day, amount in Payment.objects.filter(date__year=season).values_list("date", "amount"):
            flows[day.timetuple().tm_yday] += amount
        for day, amount in Cost.objects.filter(date__year=season).values_list("date", "amount"):
            flows[day.timetuple().tm_yday] -= amount
        running, points = ZERO, []
        for week in weeks:
            week_end = (week - date(year, 1, 1)).days + 7  # day-of-year at the week's end
            running = sum((v for d, v in flows.items() if d <= week_end), ZERO)
            in_future = offset == 0 and week > today
            points.append(None if in_future else _f(running))
        series.append({"name": str(season), "type": "line", "slot": slot, "data": points})
        rows.append([str(season), format_money(sum(flows.values(), ZERO))])
    return Chart(
        "running_profit",
        _("Running profit: this season vs last"),
        "lines",
        "money",
        subtitle=_(
            "Received minus costs since 1 January. "
            "Where the line crosses zero, the season has paid for itself."
        ),
        data={
            "categories": [w.strftime("%d %b") for w in weeks],
            "series": series,
            "zero_line": True,
        },
        table_columns=[_("Season"), _("Profit so far")],
        table_rows=rows,
    )


def hectares_over_time(filters: Filters) -> Chart:
    start, end = data_bounds(filters)
    weekly = (end - start).days <= 190
    buckets = week_starts(start, end) if weekly else month_starts(start, end)
    key = _week_key if weekly else _month_key
    operations = list(OperationType.objects.order_by("sort_order", "pk"))
    slot_of = {op.pk: index for index, op in enumerate(operations)}
    totals = defaultdict(Decimal)
    for day_date, op_id, hectares in days_in(filters).values_list(
        "date", "job__operation_type", "hectares"
    ):
        totals[(key(day_date), op_id)] += hectares or ZERO
    used = [op for op in operations if any(totals[(b, op.pk)] for b in buckets)]
    series = [
        {
            "name": op.name,
            "type": "bar",
            "stack": "ha",
            "slot": min(slot_of[op.pk], 7),
            "data": [_f(totals[(b, op.pk)]) for b in buckets],
        }
        for op in used
    ]
    fmt = "%d %b" if weekly else "%b %Y"
    labels = [b.strftime(fmt) for b in buckets]
    rows = []
    for bucket, label in zip(buckets, labels, strict=True):
        values = [totals[(bucket, op.pk)] for op in used]
        if any(values):
            rows.append([label, *[format_hectares(v) for v in values]])
    return Chart(
        "hectares_time",
        _("Hectares per week") if weekly else _("Hectares per month"),
        "combo",
        "ha",
        data={"categories": labels, "series": series},
        table_columns=[_("Week") if weekly else _("Month"), *[op.name for op in used]],
        table_rows=rows,
        wide=True,
    )


def _hbar(key, title, unit, pairs, *, subtitle="", details=None, value_format=None) -> Chart:
    value_format = value_format or (lambda v: format_value(v, unit))
    pairs = [(label, value) for label, value in pairs if value]
    return Chart(
        key,
        title,
        "hbar",
        unit,
        subtitle=subtitle,
        data={
            "categories": [label for label, _v in pairs],
            "values": [_f(v) for _l, v in pairs],
            "details": details or [],
        },
        table_columns=[_("Name"), title],
        table_rows=[[label, value_format(value)] for label, value in pairs],
    )


def costs_by_category(filters: Filters) -> Chart | None:
    if not money_enabled():
        return None
    qs = costs_in(filters)
    if qs is None:
        return None
    rows = qs.values("category__name").annotate(total=Sum("amount")).order_by("-total")
    return _hbar(
        "costs_category",
        _("Costs by category"),
        "money",
        [(r["category__name"], r["total"]) for r in rows],
    )


def top_customers(filters: Filters) -> Chart:
    rows = list(
        jobs_in(filters)
        .values("customer__name")
        .annotate(charged=Sum("total_amount"), ha=Sum("total_hectares"), jobs=Count("pk"))
        .order_by("-charged")[:TOP_N]
    )
    details = [
        _("%(ha)s · %(jobs)d job(s)") % {"ha": format_hectares(r["ha"]), "jobs": r["jobs"]}
        for r in rows
    ]
    return _hbar(
        "top_customers",
        _("Top customers"),
        "money",
        [(r["customer__name"], r["charged"]) for r in rows],
        subtitle=_("By amount charged"),
        details=details,
    )


def price_per_ha_by_month(filters: Filters) -> Chart:
    start, end = data_bounds(filters)
    months = month_starts(start, end)
    charged, hectares = defaultdict(Decimal), defaultdict(Decimal)
    for end_date, total, ha in jobs_in(filters).values_list(
        "end_date", "total_amount", "total_hectares"
    ):
        charged[_month_key(end_date)] += total
        hectares[_month_key(end_date)] += ha
    values = [_ratio(charged[m], hectares[m]) for m in months]
    labels = [m.strftime("%b %Y") for m in months]
    return Chart(
        "price_trend",
        _("Average price per hectare"),
        "lines",
        "money_per_ha",
        subtitle=_("Per month, including extra charges"),
        data={
            "categories": labels,
            "series": [
                {
                    "name": _("Price / ha"),
                    "type": "line",
                    "slot": 0,
                    "data": [None if v is None else _f(v) for v in values],
                }
            ],
        },
        table_columns=[_("Month"), _("Price / ha")],
        table_rows=[
            [label, format_value(v, "money_per_ha")]
            for label, v in zip(labels, values, strict=True)
            if v is not None
        ],
    )


def price_by_crop(filters: Filters) -> Chart:
    rows = (
        jobs_in(filters)
        .exclude(crop=None)
        .values("crop__name")
        .annotate(charged=Sum("total_amount"), ha=Sum("total_hectares"))
        .order_by("crop__name")
    )
    pairs = sorted(
        ((r["crop__name"], _ratio(r["charged"], r["ha"])) for r in rows),
        key=lambda pair: pair[1] or 0,
        reverse=True,
    )
    return _hbar("price_crop", _("Average price per hectare by crop"), "money_per_ha", pairs)


def productivity_by_month(filters: Filters) -> Chart:
    start, end = data_bounds(filters)
    months = month_starts(start, end)
    ha, minutes = defaultdict(Decimal), defaultdict(int)
    for day_date, hectares, mins in (
        days_in(filters)
        .filter(duration_minutes__gt=0)
        .values_list("date", "hectares", "duration_minutes")
    ):
        ha[_month_key(day_date)] += hectares or ZERO
        minutes[_month_key(day_date)] += mins
    values = [_ratio(ha[m], Decimal(minutes[m]) / 60) for m in months]
    labels = [m.strftime("%b %Y") for m in months]
    return Chart(
        "productivity",
        _("Hectares per hour"),
        "lines",
        "ha_per_hour",
        subtitle=_("From each day's start and end time"),
        data={
            "categories": labels,
            "series": [
                {
                    "name": _("Hectares / hour"),
                    "type": "line",
                    "slot": 0,
                    "data": [None if v is None else _f(v) for v in values],
                }
            ],
        },
        table_columns=[_("Month"), _("Hectares / hour")],
        table_rows=[
            [label, format_value(v, "ha_per_hour")]
            for label, v in zip(labels, values, strict=True)
            if v is not None
        ],
    )


def payment_methods(filters: Filters) -> Chart | None:
    if not money_enabled():
        return None
    rows = (
        payments_in(filters).values("method__name").annotate(total=Sum("amount")).order_by("-total")
    )
    return _hbar(
        "payment_methods",
        _("How customers paid"),
        "money",
        [(r["method__name"], r["total"]) for r in rows],
    )


def hectares_by_equipment(filters: Filters, kind: EquipmentType | None) -> Chart | None:
    if kind is None:
        return None
    totals = (
        days_in(filters)
        .filter(equipment__equipment_type=kind)
        .values("equipment__name")
        .annotate(ha=Sum("hectares"), minutes=Sum("duration_minutes"))
        .order_by("-ha")
    )
    rows = list(totals)
    details = [
        _("%(hours)s h worked") % {"hours": format_number(Decimal(r["minutes"] or 0) / 60, 1)}
        for r in rows
    ]
    return _hbar(
        "equipment",
        _("Hectares per %(type)s") % {"type": kind.name.lower()},
        "ha",
        [(r["equipment__name"], r["ha"]) for r in rows],
        details=details,
    )


def season_calendar(filters: Filters) -> Chart:
    year = (filters.period.end or timezone.localdate()).year
    season = Filters(
        Period(date(year, 1, 1), date(year, 12, 31), str(year)),
        filters.operation,
        filters.crop,
        filters.customer,
        filters.equipment,
    )
    per_day = OrderedDict()
    for row in days_in(season).values("date").annotate(ha=Sum("hectares")).order_by("date"):
        per_day[row["date"]] = row["ha"] or ZERO
    return Chart(
        "calendar",
        _("Days worked in %(year)s") % {"year": year},
        "calendar",
        "ha",
        subtitle=_("Darker = more hectares that day"),
        data={
            "year": year,
            "days": [[d.isoformat(), _f(v)] for d, v in per_day.items()],
            "max": _f(max(per_day.values(), default=0)),
        },
        table_columns=[_("Date"), _("Hectares")],
        table_rows=[[d.strftime("%d.%m.%Y"), format_hectares(v)] for d, v in per_day.items()],
        wide=True,
    )


def field_points(filters: Filters) -> list[dict]:
    """Fields worked in the period, sized by hectares, for the map."""
    rows = (
        days_in(filters)
        .filter(farm_fields__latitude__isnull=False)
        .values(
            "farm_fields__pk",
            "farm_fields__name",
            "farm_fields__latitude",
            "farm_fields__longitude",
            "job__customer__name",
        )
        .annotate(ha=Sum("hectares"), visits=Count("pk"))
    )
    rows = list(rows)
    biggest = max((float(r["ha"] or 0) for r in rows), default=0) or 1
    return [
        {
            "radius": round(6 + 12 * (float(r["ha"] or 0) / biggest) ** 0.5, 1),
            "lat": float(r["farm_fields__latitude"]),
            "lng": float(r["farm_fields__longitude"]),
            "label": f"{r['farm_fields__name']} · {r['job__customer__name']}",
            "detail": _("%(ha)s over %(n)d day(s)")
            % {"ha": format_hectares(r["ha"]), "n": r["visits"]},
        }
        for r in rows
    ]


def all_charts(filters: Filters, equipment_type: EquipmentType | None) -> list[Chart]:
    charts = [
        money_by_month(filters),
        hectares_over_time(filters),
        running_profit(filters),
        top_customers(filters),
        costs_by_category(filters),
        price_per_ha_by_month(filters),
        price_by_crop(filters),
        productivity_by_month(filters),
        payment_methods(filters),
        hectares_by_equipment(filters, equipment_type),
        season_calendar(filters),
    ]
    return [chart for chart in charts if chart is not None]
