"""Fill the app with realistic made-up data (two seasons), or remove it again.

    python manage.py seed_demo            # add demo data
    python manage.py seed_demo --remove   # delete everything tagged [demo]

Every demo record carries the tag "[demo]" in its notes, so removing it never touches
real records.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from avifly.accounts.models import User
from avifly.core.registry import registry
from avifly.customers.models import Customer, FarmField
from avifly.equipment.models import Equipment, EquipmentType
from avifly.jobs import services
from avifly.jobs.models import Crop, ExtraCharge, Job, JobDay, OperationType

TAG = "[demo]"

# name, town, latitude, longitude, crops, special rate. Invented: companies are named
# "Пример"/"Primer" ("Example") so none can be mistaken for a real business.
CUSTOMERS = [
    ("Горан Петровски", "Куманово", 42.132, 21.714, ["Wheat", "Maize"], None),
    ("Zoran Stojanov", "Strumica", 41.438, 22.643, ["Vegetables", "Maize"], None),
    ("Пример Агро ДООЕЛ", "Битола", 41.031, 21.335, ["Wheat", "Barley", "Sunflower"], "800"),
    ("Dragan Nikolovski", "Prilep", 41.346, 21.555, ["Tobacco"], None),
    ("Пример Винарија", "Кавадарци", 41.433, 22.012, ["Vineyard"], None),
    ("Blagoja Trajkovski", "Veles", 41.716, 21.775, ["Alfalfa", "Wheat"], None),
    ("Љупчо Ангелов", "Штип", 41.746, 22.196, ["Wheat", "Sunflower"], None),
    ("Primer Oriz DOO", "Kočani", 41.917, 22.408, ["Rice"], "850"),
    ("Arben Rexhepi", "Tetovo", 42.010, 20.971, ["Maize", "Wheat"], None),
    ("Јован Митев", "Гевгелија", 41.141, 22.502, ["Vegetables"], None),
    ("Mite Ristov", "Radoviš", 41.638, 22.465, ["Rice", "Wheat"], None),
    ("Звонко Цветков", "Свети Николе", 41.865, 21.943, ["Wheat", "Barley"], None),
    ("Primer Lozja", "Negotino", 41.484, 22.089, ["Vineyard", "Orchard"], None),
    ("Пример Овоштарник", "Ресен", 41.089, 21.012, ["Orchard"], "1000"),
]
FIELD_NAMES = [
    "Near the river",
    "Big field",
    "By the road",
    "Hill",
    "Behind the village",
    "East parcel",
]
EXTRAS = [
    ("Far field, extra travel", 1500),
    ("Difficult terrain", 2000),
    ("Loyal customer discount", -1000),
]


class Command(BaseCommand):
    help = "Add realistic demo data (two seasons), or remove it with --remove."

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="Delete all demo data.")
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, remove=False, seed=42, **options):
        if remove:
            self.remove()
            return
        if Customer.all_objects.filter(notes__contains=TAG).exists():
            self.stdout.write("Demo data is already there (use --remove first to recreate).")
            return
        self.rng = random.Random(seed)
        with transaction.atomic():
            self.create()
        self.stdout.write(self.style.SUCCESS("Demo data added. Remove it with: seed_demo --remove"))

    # -- removal -------------------------------------------------------------------------
    @transaction.atomic
    def remove(self):
        if registry.is_enabled("money"):
            from avifly.money.models import Cost

            Cost.all_objects.filter(notes__contains=TAG).delete()
        jobs = Job.all_objects.filter(notes__contains=TAG)
        count = jobs.count()
        jobs.delete()
        FarmField.all_objects.filter(customer__notes__contains=TAG).delete()
        Customer.all_objects.filter(notes__contains=TAG).delete()
        Equipment.all_objects.filter(notes__contains=TAG).delete()
        self.stdout.write(self.style.SUCCESS(f"Removed demo data ({count} jobs)."))

    # -- creation --------------------------------------------------------------------------
    def create(self):
        rng = self.rng
        spraying = OperationType.objects.get_or_create(name="Spraying")[0]
        spreading = OperationType.objects.get_or_create(name="Spreading")[0]
        for op, rate in ((spraying, "900"), (spreading, "700")):
            if op.default_rate_per_ha is None:
                op.default_rate_per_ha = Decimal(rate)
                op.save()

        drone_type = EquipmentType.objects.get_or_create(name="Drone")[0]
        generator_type = EquipmentType.objects.get_or_create(name="Generator")[0]
        battery_type = EquipmentType.objects.get_or_create(name="Battery")[0]
        drone1 = Equipment.objects.create(
            name="T50 #1", equipment_type=drone_type, model_name="DJI Agras T50",
            serial_number="SN-T50-0001", purchase_date=date(2025, 3, 10), notes=TAG,
        )  # fmt: skip
        drone2 = Equipment.objects.create(
            name="T50 #2", equipment_type=drone_type, model_name="DJI Agras T50",
            serial_number="SN-T50-0002", purchase_date=date(2026, 2, 20),
            status=Equipment.Status.SPARE, notes=TAG,
        )  # fmt: skip
        generator = Equipment.objects.create(
            name="D12000iEP", equipment_type=generator_type, model_name="DJI D12000iEP",
            purchase_date=date(2025, 3, 10), notes=TAG,
        )  # fmt: skip
        for n in range(1, 7):
            Equipment.objects.create(
                name=f"Battery {n}", equipment_type=battery_type, model_name="DB1560", notes=TAG
            )

        customers = []
        for name, town, lat, lng, crops, rate in CUSTOMERS:
            customer = Customer.objects.create(
                name=name,
                town=town,
                phone=f"+389 7{rng.randint(0, 9)} {rng.randint(100, 999)} {rng.randint(100, 999)}",
                special_rate_per_ha=Decimal(rate) if rate else None,
                notes=TAG,
            )
            fields = []
            for field_name in rng.sample(FIELD_NAMES, rng.randint(1, 3)):
                fields.append(
                    FarmField.objects.create(
                        customer=customer,
                        name=field_name,
                        hectares=Decimal(rng.randint(8, 120)),
                        latitude=Decimal(str(round(lat + rng.uniform(-0.04, 0.04), 6))),
                        longitude=Decimal(str(round(lng + rng.uniform(-0.05, 0.05), 6))),
                    )
                )
            customers.append((customer, fields, [Crop.objects.get(name=c) for c in crops]))

        crew = list(User.objects.usable()[:2])
        today = timezone.localdate()
        jobs = []
        for year in (today.year - 1, today.year):
            for _n in range(rng.randint(55, 65)):
                month = rng.choices(range(3, 11), weights=[3, 10, 14, 16, 14, 11, 7, 3])[0]
                day = date(year, month, rng.randint(1, 28))
                if day > today + timedelta(days=10):
                    continue
                customer, fields, crops = rng.choice(customers)
                operation = spreading if month in (3, 4, 10) and rng.random() < 0.5 else spraying
                drone = drone2 if day >= date(2026, 5, 1) and rng.random() < 0.3 else drone1
                jobs.append(
                    self.make_job(customer, fields, crops, operation, day, [drone, generator], crew)
                )
        # A couple of planned jobs next week.
        for offset in (3, 5):
            customer, fields, crops = rng.choice(customers)
            self.make_job(
                customer,
                fields,
                crops,
                spraying,
                today + timedelta(days=offset),
                [drone1, generator],
                crew,
                planned=True,
            )

        if registry.is_enabled("money"):
            self.money(jobs, drone1, drone2, generator)

    def make_job(self, customer, fields, crops, operation, day, equipment, crew, planned=False):
        rng = self.rng
        job = Job(
            customer=customer,
            operation_type=operation,
            crop=rng.choice(crops),
            material_note=rng.choice(
                [
                    "Customer's herbicide",
                    "Fungicide (customer's)",
                    "Insecticide, 1 L/ha",
                    "Foliar fertiliser",
                    "Urea granules",
                ]
            ),
            rate_per_ha=customer.special_rate_per_ha or operation.default_rate_per_ha,
            notes=TAG,
        )
        services.assign_number(job, day)
        job.save()
        multi = not planned and rng.random() < 0.15
        for position in range(1, (rng.randint(2, 3) if multi else 1) + 1):
            work_date = day + timedelta(days=position - 1)
            if planned or work_date > timezone.localdate():
                hectares, start, end = None, None, None
            else:
                hectares = (
                    Decimal(rng.randint(40, 450)) / 10
                    if not multi
                    else Decimal(rng.randint(250, 550)) / 10
                )
                rate = rng.uniform(8, 14)  # hectares per hour
                start_dt = datetime.combine(
                    work_date, time(rng.randint(6, 8), rng.choice([0, 15, 30, 45]))
                )
                end_dt = start_dt + timedelta(hours=float(hectares) / rate + rng.uniform(0.5, 1.5))
                start, end = start_dt.time(), end_dt.replace(second=0, microsecond=0).time()
            job_day = JobDay.objects.create(
                job=job,
                position=position,
                date=work_date,
                hectares=hectares,
                start_time=start,
                end_time=end,
            )
            job_day.farm_fields.set([rng.choice(fields)])
            job_day.equipment.set(equipment)
            job_day.crew.set(crew)
        job.is_multi_day = multi
        job.save(update_fields=["is_multi_day"])
        if not planned and rng.random() < 0.12:
            note, amount = rng.choice(EXTRAS)
            ExtraCharge.objects.create(job=job, note=note, amount=Decimal(amount))
        return services.recalculate_job(job)

    def money(self, jobs, drone1, drone2, generator):
        from avifly.money.models import Cost, CostCategory, Payment, PaymentMethod

        rng = self.rng
        methods = {m.name: m for m in PaymentMethod.objects.all()}
        for job in jobs:
            if job.status not in (Job.Status.DONE, Job.Status.IN_PROGRESS) or not job.total_amount:
                continue
            method = rng.choices(["Cash", "Invoice", "Other"], weights=[80, 16, 4])[0]
            Payment.objects.create(
                job=job,
                method=methods.get(method) or next(iter(methods.values())),
                amount=job.total_amount,
                date=job.end_date,
                note=f"INV-{job.number}" if method == "Invoice" else "",
            )

        def cost(day, amount, category, description, **extra):
            Cost.objects.create(
                date=day,
                amount=Decimal(amount),
                category=CostCategory.objects.get_or_create(name=category)[0],
                description=description,
                notes=TAG,
                **extra,
            )

        today = timezone.localdate()
        cost(
            date(2025, 3, 10),
            1_480_000,
            "Equipment purchase",
            "DJI Agras T50 kit",
            equipment=drone1,
        )
        cost(
            date(2025, 3, 10),
            175_000,
            "Equipment purchase",
            "D12000iEP generator",
            equipment=generator,
        )
        cost(date(2025, 3, 12), 180_000, "Batteries", "2 × DB1560 extra batteries")
        cost(
            date(2026, 2, 20),
            1_150_000,
            "Equipment purchase",
            "Second T50 (used)",
            equipment=drone2,
        )
        for year in (today.year - 1, today.year):
            cost(date(year, 3, 1), 28_000, "Insurance & registration", "Drone liability insurance")
            cost(date(year, 3, 2), 9_500, "Software & subscriptions", "RTK network subscription")
            for month in range(1, 13):
                if date(year, month, 5) <= today:
                    cost(date(year, month, 5), 1_200, "Phone & internet", "Mobile data")
        days = JobDay.objects.filter(job__in=[j for j in jobs if j.status == Job.Status.DONE])
        for day in days.select_related("job"):
            litres = float(day.hectares or 0) * rng.uniform(0.35, 0.55)
            cost(
                day.date,
                round(litres * 82),
                "Generator fuel",
                "Petrol for the generator",
                job=day.job,
            )
            if rng.random() < 0.35:
                cost(day.date, rng.randint(1200, 3500), "Vehicle fuel", "Diesel", job=day.job)
            if day.job.days.count() > 1 and day.position == 1:
                cost(
                    day.date,
                    rng.randint(3000, 6000),
                    "Accommodation & food",
                    "Room near the fields",
                    job=day.job,
                )
        for _n in range(9):
            month_day = date(
                rng.choice([today.year - 1, today.year]), rng.randint(4, 9), rng.randint(1, 28)
            )
            if month_day <= today:
                description, amount = rng.choice(
                    [
                        ("New propeller", 6_500),
                        ("Nozzles", 2_400),
                        ("Pump service", 8_000),
                        ("Radar cable", 4_200),
                    ]
                )
                cost(
                    month_day,
                    amount,
                    "Spare parts",
                    description,
                    equipment=rng.choice([drone1, drone2]),
                )
