from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.fleet.models import Truck, TruckCrewAssignment
from apps.imports.models import (
    ImportSourceSystem,
    SourceProductAlias,
    SourceProductPackaging,
    SourceTruckExclusion,
)
from apps.workforce.models import Worker


SOURCE_SYSTEM_CODE = "AIO_WEB"

WORKER_NOTES = (
    "Generic analytical workforce identity for this distribution route. "
    "It does not represent one real employee."
)

ASSIGNMENT_NOTES = (
    "Generic primary seller assignment used for route-level analytics."
)

START_DATE = date(2026, 4, 4)


PRODUCT_ALIASES = (
    (
        "NITA DOPPIO VANILLA STRAWBERRY",
        "NITA DOPPIO VANILLE FRAISE",
        "GAU-00049",
        1,
        (
            "Historical NITA designation confirmed from Opening Stock "
            "2026-04-03 and Items exports 2026-04-04 to 2026-08-26."
        ),
    ),
    (
        "NITA GRAND BISCUIT CHOCOLAT",
        "NITA GRAND BISCUIT",
        "BIS-00125",
        1,
        (
            "Confirmed by DELISKY manager as the same product as "
            "NITA GRAND BISCUIT."
        ),
    ),
    (
        "NITA PERFECTO",
        "NITA PERFECTO CACAO VANILLE",
        "BIS-00129",
        6,
        (
            "Confirmed by DELISKY manager as the same NITA "
            "product designation."
        ),
    ),
    (
        "NITA SO WAFER NOISETTE",
        "NITA SO WAFER NOISETTES",
        "GAU-00048",
        1,
        (
            "Historical NITA designation confirmed from Opening Stock "
            "2026-04-03 and Items exports 2026-04-04 to 2026-08-26."
        ),
    ),
    (
        "NITA SPECULOOS",
        "NITA SPECULOOS CANNELLA",
        "BIS-00140",
        1,
        (
            "Confirmed by DELISKY manager as the same NITA "
            "product designation."
        ),
    ),
)


TRUCK_EXCLUSIONS = (
    (
        "VAN_SUPERVISEUR",
        "OUT_OF_SCOPE",
        "Destination outside DELISKY BI distribution scope.",
    ),
    (
        "VAN1-ABIA",
        "OUT_OF_SCOPE",
        "Destination outside DELISKY BI distribution scope.",
    ),
)


WORKERS = (
    ("GEN-BIFA-LIV03", "BIFA LIV03", "BIFA LIV03", None),
    ("GEN-BIFA-LIV07", "BIFA LIV07", "BIFA LIV07", None),
    ("GEN-BIFA-PLIV01", "BIFA PLIV01", "BIFA PLIV01", None),
    ("GEN-BIFA-PLIV02", "BIFA PLIV02", "BIFA PLIV02", None),
    ("GEN-BIFA-PLIV04", "BIFA PLIV04", "BIFA PLIV04", None),
    ("GEN-BIFA-PLIV05", "BIFA PLIV05", "BIFA PLIV05", None),
    ("GEN-BIFA-PLIV06", "BIFA PLIV06", "BIFA PLIV06", None),
    (
        "GEN-DELISKY-LIV01",
        "DELISKY LIV01",
        "DELISKY LIV01",
        date(2026, 8, 17),
    ),
    ("GEN-DELISKY-LIV02", "DELISKY LIV02", "DELISKY LIV02", None),
    ("GEN-DELISKY-LIV03", "DELISKY LIV03", "DELISKY LIV03", None),
    ("GEN-NITA-LIV01", "NITA LIV01", "NITA LIV01", None),
    ("GEN-NITA-LIV02", "NITA LIV02", "NITA LIV02", None),
    ("GEN-NITA-LIV03", "NITA LIV03", "NITA LIV03", None),
)


def normalize(value):
    return " ".join(str(value).split()).upper()


class Command(BaseCommand):
    help = (
        "Provision confirmed Phase 10 reference data. "
        "Dry-run by default; use --apply to persist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        self.stdout.write(
            "=== PHASE 10 REFERENCE DATA PROVISIONING ==="
        )
        self.stdout.write(
            "MODE: APPLY" if apply_changes else "MODE: DRY RUN"
        )

        source = self.get_source()
        products = self.get_products(source)
        trucks = self.get_trucks()

        self.inspect(
            source,
            products,
            trucks,
        )

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS("DRY RUN: PASS")
            )
            self.stdout.write(
                "No database changes were made."
            )
            return

        with transaction.atomic():
            source = self.get_source(lock=True)
            products = self.get_products(
                source,
                lock=True,
            )
            trucks = self.get_trucks(lock=True)

            self.apply_aliases(
                source,
                products,
            )
            self.apply_exclusions(source)

            workers = self.apply_workers()

            self.apply_assignments(
                workers,
                trucks,
            )

            self.verify(
                source,
                products,
                trucks,
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "PHASE 10 REFERENCE DATA: APPLIED"
            )
        )

    def get_source(self, *, lock=False):
        qs = ImportSourceSystem.objects

        if lock:
            qs = qs.select_for_update()

        try:
            return qs.get(
                code__iexact=SOURCE_SYSTEM_CODE,
                is_active=True,
            )
        except ImportSourceSystem.DoesNotExist as exc:
            raise CommandError(
                "Active AIO_WEB source system not found."
            ) from exc

    def get_products(
        self,
        source,
        *,
        lock=False,
    ):
        result = {}

        qs = SourceProductPackaging.objects.filter(
            source_system=source,
            is_active=True,
        )

        if lock:
            qs = qs.select_for_update()

        for (
            alias_name,
            target_name,
            barcode,
            expected_upc,
            notes,
        ) in PRODUCT_ALIASES:

            matches = qs.filter(
                designation__iexact=target_name,
                barcode=barcode,
            )

            count = matches.count()

            if count != 1:
                raise CommandError(
                    (
                        f"Product Master mismatch for "
                        f"{target_name} / {barcode}: "
                        f"found {count}."
                    )
                )

            product = matches.get()

            if product.units_per_carton != expected_upc:
                raise CommandError(
                    (
                        f"Unexpected UPC for {target_name}: "
                        f"{product.units_per_carton}."
                    )
                )

            if product.needs_review:
                raise CommandError(
                    f"Product requires review: {target_name}."
                )

            result[alias_name] = product

        return result

    def get_trucks(self, *, lock=False):
        codes = {
            truck_code
            for (
                employee_code,
                first_name,
                truck_code,
                end_date,
            ) in WORKERS
        }

        qs = Truck.objects.filter(
            internal_code__in=codes
        )

        if lock:
            qs = qs.select_for_update()

        trucks = {
            truck.internal_code: truck
            for truck in qs
        }

        missing = sorted(
            codes - set(trucks)
        )

        if missing:
            raise CommandError(
                "Missing trucks: " + ", ".join(missing)
            )

        if len(trucks) != 13:
            raise CommandError(
                f"Expected 13 trucks, found {len(trucks)}."
            )

        return trucks

    def find_alias(self, source, alias_name):
        return (
            SourceProductAlias.objects
            .filter(
                source_system=source,
                normalized_alias=normalize(
                    alias_name
                ),
            )
            .select_related("product")
            .first()
        )

    def find_worker(self, employee_code):
        return (
            Worker.objects
            .filter(
                employee_code=employee_code
            )
            .first()
        )

    def inspect(
        self,
        source,
        products,
        trucks,
    ):
        self.stdout.write("")
        self.stdout.write("Product aliases:")

        for (
            alias_name,
            target_name,
            barcode,
            expected_upc,
            notes,
        ) in PRODUCT_ALIASES:

            product = products[alias_name]

            existing = self.find_alias(
                source,
                alias_name,
            )

            if existing is None:
                state = "CREATE"
            elif existing.product_id != product.id:
                raise CommandError(
                    (
                        f"Alias conflict: {alias_name} "
                        f"currently points to "
                        f"{existing.product.designation}."
                    )
                )
            elif (
                existing.alias == alias_name
                and existing.is_active
                and existing.notes == notes
            ):
                state = "OK"
            else:
                state = "UPDATE"

            self.stdout.write(
                f"  [{state}] {alias_name} -> {target_name}"
            )

        self.stdout.write("")
        self.stdout.write("Source truck exclusions:")

        for source_code, reason, notes in TRUCK_EXCLUSIONS:
            existing = (
                SourceTruckExclusion.objects
                .filter(
                    source_system=source,
                    source_code__iexact=source_code,
                )
                .first()
            )

            if existing is None:
                state = "CREATE"
            elif (
                existing.reason == reason
                and existing.is_active
                and existing.notes == notes
            ):
                state = "OK"
            else:
                state = "UPDATE"

            self.stdout.write(
                f"  [{state}] {source_code}"
            )

        self.stdout.write("")
        self.stdout.write("Generic workers:")

        for (
            employee_code,
            first_name,
            truck_code,
            end_date,
        ) in WORKERS:

            worker = self.find_worker(employee_code)

            if worker is None:
                state = "CREATE"
            else:
                if (
                    worker.first_name != first_name
                    or worker.last_name != "WORKERS"
                ):
                    raise CommandError(
                        (
                            f"Worker identity conflict: "
                            f"{employee_code}."
                        )
                    )

                if (
                    worker.is_active
                    and worker.notes == WORKER_NOTES
                ):
                    state = "OK"
                else:
                    state = "UPDATE"

            self.stdout.write(
                f"  [{state}] {employee_code}"
            )

        self.stdout.write("")
        self.stdout.write("Generic assignments:")

        for (
            employee_code,
            first_name,
            truck_code,
            end_date,
        ) in WORKERS:

            worker = self.find_worker(employee_code)
            truck = trucks[truck_code]

            if worker is None:
                state = "CREATE"
            else:
                assignment = (
                    TruckCrewAssignment.objects
                    .filter(
                        worker=worker,
                        truck=truck,
                        start_date=START_DATE,
                    )
                    .first()
                )

                if assignment is None:
                    state = "CREATE"
                elif (
                    assignment.crew_role
                    == TruckCrewAssignment.CrewRole.SELLER
                    and assignment.is_primary_seller
                    and assignment.end_date == end_date
                    and assignment.notes
                    == ASSIGNMENT_NOTES
                ):
                    state = "OK"
                else:
                    state = "UPDATE"

            self.stdout.write(
                (
                    f"  [{state}] {employee_code} -> "
                    f"{truck_code} "
                    f"({START_DATE} -> "
                    f"{end_date or 'OPEN'})"
                )
            )

    def apply_aliases(
        self,
        source,
        products,
    ):
        for (
            alias_name,
            target_name,
            barcode,
            expected_upc,
            notes,
        ) in PRODUCT_ALIASES:

            product = products[alias_name]

            alias = self.find_alias(
                source,
                alias_name,
            )

            if alias is None:
                alias = SourceProductAlias(
                    source_system=source,
                    product=product,
                    alias=alias_name,
                )
            elif alias.product_id != product.id:
                raise CommandError(
                    f"Alias conflict: {alias_name}."
                )

            alias.product = product
            alias.alias = alias_name
            alias.normalized_alias = normalize(
                alias_name
            )
            alias.is_active = True
            alias.notes = notes

            alias.full_clean()
            alias.save()

    def apply_exclusions(self, source):
        for source_code, reason, notes in TRUCK_EXCLUSIONS:
            exclusion = (
                SourceTruckExclusion.objects
                .filter(
                    source_system=source,
                    source_code__iexact=source_code,
                )
                .first()
            )

            if exclusion is None:
                exclusion = SourceTruckExclusion(
                    source_system=source,
                    source_code=source_code,
                )

            exclusion.source_code = source_code
            exclusion.reason = reason
            exclusion.is_active = True
            exclusion.notes = notes

            exclusion.full_clean()
            exclusion.save()

    def apply_workers(self):
        result = {}

        for (
            employee_code,
            first_name,
            truck_code,
            end_date,
        ) in WORKERS:

            worker = self.find_worker(
                employee_code
            )

            if worker is None:
                worker = Worker(
                    employee_code=employee_code,
                    first_name=first_name,
                    last_name="WORKERS",
                )
            elif (
                worker.first_name != first_name
                or worker.last_name != "WORKERS"
            ):
                raise CommandError(
                    (
                        f"Worker identity conflict: "
                        f"{employee_code}."
                    )
                )

            worker.is_active = True
            worker.notes = WORKER_NOTES

            worker.full_clean()
            worker.save()

            result[employee_code] = worker

        return result

    def apply_assignments(
        self,
        workers,
        trucks,
    ):
        for (
            employee_code,
            first_name,
            truck_code,
            end_date,
        ) in WORKERS:

            worker = workers[employee_code]
            truck = trucks[truck_code]

            assignment = (
                TruckCrewAssignment.objects
                .filter(
                    worker=worker,
                    truck=truck,
                    start_date=START_DATE,
                )
                .first()
            )

            if assignment is None:
                assignment = TruckCrewAssignment(
                    worker=worker,
                    truck=truck,
                    start_date=START_DATE,
                )

            assignment.crew_role = (
                TruckCrewAssignment.CrewRole.SELLER
            )
            assignment.is_primary_seller = True
            assignment.end_date = end_date
            assignment.notes = ASSIGNMENT_NOTES

            assignment.full_clean()
            assignment.save()

    def verify(
        self,
        source,
        products,
        trucks,
    ):
        alias_count = 0

        for (
            alias_name,
            target_name,
            barcode,
            expected_upc,
            notes,
        ) in PRODUCT_ALIASES:

            alias = self.find_alias(
                source,
                alias_name,
            )

            if (
                alias is None
                or alias.product_id
                != products[alias_name].id
                or not alias.is_active
            ):
                raise CommandError(
                    f"Alias verification failed: {alias_name}."
                )

            alias_count += 1

        exclusion_count = 0

        for source_code, reason, notes in TRUCK_EXCLUSIONS:
            exists = (
                SourceTruckExclusion.objects
                .filter(
                    source_system=source,
                    source_code__iexact=source_code,
                    reason=reason,
                    is_active=True,
                )
                .exists()
            )

            if not exists:
                raise CommandError(
                    (
                        "Exclusion verification failed: "
                        f"{source_code}."
                    )
                )

            exclusion_count += 1

        worker_count = 0
        assignment_count = 0

        for (
            employee_code,
            first_name,
            truck_code,
            end_date,
        ) in WORKERS:

            try:
                worker = Worker.objects.get(
                    employee_code=employee_code,
                    first_name=first_name,
                    last_name="WORKERS",
                    is_active=True,
                )
            except Worker.DoesNotExist as exc:
                raise CommandError(
                    (
                        "Worker verification failed: "
                        f"{employee_code}."
                    )
                ) from exc

            worker_count += 1

            exists = (
                TruckCrewAssignment.objects
                .filter(
                    worker=worker,
                    truck=trucks[truck_code],
                    crew_role=(
                        TruckCrewAssignment
                        .CrewRole
                        .SELLER
                    ),
                    is_primary_seller=True,
                    start_date=START_DATE,
                    end_date=end_date,
                )
                .exists()
            )

            if not exists:
                raise CommandError(
                    (
                        "Assignment verification failed: "
                        f"{employee_code} -> {truck_code}."
                    )
                )

            assignment_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Verified: {alias_count} aliases, "
                    f"{exclusion_count} exclusions, "
                    f"{worker_count} workers, "
                    f"{assignment_count} assignments."
                )
            )
        )
