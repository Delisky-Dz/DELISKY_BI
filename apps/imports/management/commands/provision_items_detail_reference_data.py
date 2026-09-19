from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.fleet.models import Truck, TruckCrewAssignment
from apps.imports.models import (
    DistributionBrand,
    ImportSourceSystem,
    SourceTruckExclusion,
    SourceTruckMapping,
)
from apps.workforce.models import Worker


START_DATE = date(2026, 4, 4)

# These four generic assignments exist only to attribute the historical
# transaction-detail rows that proved activity for otherwise inactive routes.
# Bound them to the last observed accepted Items sale so a later route
# reactivation cannot silently inherit a historical analytical worker.
ASSIGNMENT_END_DATES = {
    "GEN-BIFA-LIV04": date(2026, 6, 20),
    "GEN-BIFA-LIV05": date(2026, 4, 15),
    "GEN-BIFA-PLIV07": date(2026, 6, 23),
    "GEN-BIFA-PSLIV01": date(2026, 4, 8),
}

WORKER_NOTES = (
    "Generic analytical workforce identity for this historical distribution "
    "route. It does not represent one real employee."
)
ASSIGNMENT_NOTES = (
    "Generic primary seller assignment used for transaction-level Items "
    "analytics."
)
MAPPING_NOTES = (
    "Confirmed source-truck identity for transaction-level Items analytics."
)

HISTORICAL_TRUCKS = (
    (
        "BIFA LIV04",
        Truck.RouteType.LIV,
        4,
        (
            "Historical BIFA truck identity found in Opening Stock snapshot "
            "dated 2026-04-03."
        ),
    ),
    (
        "BIFA LIV05",
        Truck.RouteType.LIV,
        5,
        (
            "Historical BIFA truck identity found in Opening Stock snapshot "
            "dated 2026-04-03."
        ),
    ),
    (
        "BIFA PLIV07",
        Truck.RouteType.PLIV,
        7,
        (
            "Historical BIFA truck identity confirmed from transaction-level "
            "Items report covering 2026-04-04 to 2026-08-26."
        ),
    ),
    (
        "BIFA PSLIV01",
        Truck.RouteType.PSLIV,
        1,
        (
            "Historical BIFA truck identity confirmed from transaction-level "
            "Items report covering 2026-04-04 to 2026-08-26."
        ),
    ),
)

GENERIC_WORKERS = (
    ("GEN-BIFA-LIV04", "BIFA LIV04", "BIFA LIV04"),
    ("GEN-BIFA-LIV05", "BIFA LIV05", "BIFA LIV05"),
    ("GEN-BIFA-PLIV07", "BIFA PLIV07", "BIFA PLIV07"),
    ("GEN-BIFA-PSLIV01", "BIFA PSLIV01", "BIFA PSLIV01"),
)

SOURCE_MAPPINGS = {
    "AIO_WEB": (
        ("DELISKY-LIVREUR1", "DELISKY LIV01"),
        ("DELISKY-LIVREUR2", "DELISKY LIV02"),
        ("DELISKY-LIVREUR3", "DELISKY LIV03"),
        ("NITA-LIVREUR1", "NITA LIV01"),
        ("NITA-LIVREUR2", "NITA LIV02"),
        ("NITA-LIVREUR3", "NITA LIV03"),
    ),
    "BIFA_MILA": (
        ("CV-03", "BIFA LIV03"),
        ("CV-04", "BIFA LIV04"),
        ("CV-05", "BIFA LIV05"),
        ("CV-07", "BIFA LIV07"),
        ("LV-01", "BIFA PLIV01"),
        ("LV-02", "BIFA PLIV02"),
        ("LV-04", "BIFA PLIV04"),
        ("LV-05", "BIFA PLIV05"),
        ("LV-06", "BIFA PLIV06"),
        ("LV-07", "BIFA PLIV07"),
        ("LVS-01", "BIFA PSLIV01"),
        ("DCV-03", "BIFA LIV03"),
        ("DCV-07", "BIFA LIV07"),
        ("DLV-01", "BIFA PLIV01"),
        ("DLV-02", "BIFA PLIV02"),
        ("DLV-04", "BIFA PLIV04"),
        ("DLV-05", "BIFA PLIV05"),
        ("DLV-06", "BIFA PLIV06"),
    ),
}

SOURCE_EXCLUSIONS = {
    "AIO_WEB": (
        ("ADV", "OUT_OF_SCOPE"),
        ("RACHID", "OUT_OF_SCOPE"),
        ("RACHIDONE", "OUT_OF_SCOPE"),
    ),
    "BIFA_MILA": (
        ("ADV", "OUT_OF_SCOPE"),
    ),
}


class Command(BaseCommand):
    help = (
        "Provision confirmed transaction-level Items reference data. "
        "Dry-run by default; use --apply to persist."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        self.stdout.write("=== ITEMS DETAIL REFERENCE DATA ===")
        self.stdout.write("MODE: APPLY" if apply_changes else "MODE: DRY RUN")

        sources = self._sources(lock=False)
        bifa = self._brand(lock=False)

        self._inspect_historical_trucks(bifa)
        self._inspect_workers()
        self._inspect_mappings(sources)
        self._inspect_exclusions(sources)

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("DRY RUN: PASS"))
            self.stdout.write("No database changes were made.")
            return

        with transaction.atomic():
            sources = self._sources(lock=True)
            bifa = self._brand(lock=True)

            self._apply_historical_trucks(bifa)
            trucks = self._target_trucks(lock=True)
            workers = self._apply_workers()
            self._apply_assignments(workers, trucks)
            self._apply_mappings(sources, trucks)
            self._apply_exclusions(sources)
            self._verify(sources, trucks)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("ITEMS DETAIL REFERENCE DATA: APPLIED")
        )

    def _sources(self, *, lock):
        qs = ImportSourceSystem.objects
        if lock:
            qs = qs.select_for_update()

        result = {}
        for code in SOURCE_MAPPINGS:
            try:
                result[code] = qs.get(code__iexact=code, is_active=True)
            except ImportSourceSystem.DoesNotExist as exc:
                raise CommandError(
                    f"Active source system not found: {code}."
                ) from exc
        return result

    def _brand(self, *, lock):
        qs = DistributionBrand.objects
        if lock:
            qs = qs.select_for_update()
        try:
            return qs.get(code__iexact="BIFA")
        except DistributionBrand.DoesNotExist as exc:
            raise CommandError("BIFA distribution brand not found.") from exc

    def _historical_truck(self, code):
        return Truck.objects.filter(internal_code=code).first()

    def _inspect_historical_trucks(self, bifa):
        self.stdout.write("")
        self.stdout.write("Historical BIFA trucks:")
        for code, route_type, route_number, notes in HISTORICAL_TRUCKS:
            truck = self._historical_truck(code)
            if truck is None:
                state = "CREATE"
            else:
                self._validate_truck_identity(
                    truck,
                    bifa=bifa,
                    route_type=route_type,
                    route_number=route_number,
                )
                state = "OK"
            self.stdout.write(f"  [{state}] {code}")

    def _validate_truck_identity(
        self,
        truck,
        *,
        bifa,
        route_type,
        route_number,
    ):
        if (
            truck.distribution_brand_id != bifa.pk
            or truck.route_type != route_type
            or truck.route_number != route_number
        ):
            raise CommandError(
                f"Historical truck identity conflict: {truck.internal_code}."
            )

    def _apply_historical_trucks(self, bifa):
        for code, route_type, route_number, notes in HISTORICAL_TRUCKS:
            truck = self._historical_truck(code)
            if truck is None:
                truck = Truck(
                    internal_code=code,
                    distribution_brand=bifa,
                    route_type=route_type,
                    route_number=route_number,
                    registration_number=code,
                    brand="BIFA",
                    model="",
                    is_active=False,
                    notes=notes,
                )
                truck.full_clean()
                truck.save()
            else:
                self._validate_truck_identity(
                    truck,
                    bifa=bifa,
                    route_type=route_type,
                    route_number=route_number,
                )

    def _required_truck_codes(self):
        codes = {
            truck_code
            for specs in SOURCE_MAPPINGS.values()
            for _, truck_code in specs
        }
        codes.update(spec[2] for spec in GENERIC_WORKERS)
        return codes

    def _target_trucks(self, *, lock):
        codes = self._required_truck_codes()
        qs = Truck.objects.filter(internal_code__in=codes)
        if lock:
            qs = qs.select_for_update()

        trucks = {truck.internal_code: truck for truck in qs}
        missing = sorted(codes - set(trucks))
        if missing:
            raise CommandError("Missing target trucks: " + ", ".join(missing))
        return trucks

    def _inspect_workers(self):
        self.stdout.write("")
        self.stdout.write("Generic historical workers:")
        for employee_code, first_name, truck_code in GENERIC_WORKERS:
            worker = Worker.objects.filter(
                employee_code=employee_code
            ).first()
            if worker is None:
                state = "CREATE"
            elif (
                worker.first_name != first_name
                or worker.last_name != "WORKERS"
            ):
                raise CommandError(
                    f"Worker identity conflict: {employee_code}."
                )
            else:
                state = "OK"
            self.stdout.write(
                f"  [{state}] {employee_code} -> {truck_code}"
            )

    def _apply_workers(self):
        result = {}
        for employee_code, first_name, truck_code in GENERIC_WORKERS:
            worker = Worker.objects.filter(
                employee_code=employee_code
            ).first()
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
                    f"Worker identity conflict: {employee_code}."
                )

            worker.is_active = True
            worker.notes = WORKER_NOTES
            worker.full_clean()
            worker.save()
            result[employee_code] = worker
        return result

    def _apply_assignments(self, workers, trucks):
        for employee_code, first_name, truck_code in GENERIC_WORKERS:
            worker = workers[employee_code]
            truck = trucks[truck_code]
            assignment_end = ASSIGNMENT_END_DATES[employee_code]

            existing_primary = (
                TruckCrewAssignment.objects
                .filter(
                    truck=truck,
                    is_primary_seller=True,
                    start_date__lte=assignment_end,
                )
                .filter(
                    Q(end_date__isnull=True)
                    | Q(end_date__gte=START_DATE)
                )
                .exclude(worker=worker)
                .first()
            )
            if existing_primary is not None:
                raise CommandError(
                    f"Primary seller conflict for {truck_code}."
                )

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

            assignment.crew_role = TruckCrewAssignment.CrewRole.SELLER
            assignment.is_primary_seller = True
            assignment.end_date = assignment_end
            assignment.notes = ASSIGNMENT_NOTES
            assignment.full_clean()
            assignment.save()

    def _mapping(self, source, source_code):
        return (
            SourceTruckMapping.objects
            .filter(
                source_system=source,
                source_code__iexact=source_code,
            )
            .select_related("truck")
            .first()
        )

    def _exclusion(self, source, source_code):
        return SourceTruckExclusion.objects.filter(
            source_system=source,
            source_code__iexact=source_code,
        ).first()

    def _inspect_mappings(self, sources):
        self.stdout.write("")
        self.stdout.write("Source truck mappings:")
        for source_code_system, specs in SOURCE_MAPPINGS.items():
            source = sources[source_code_system]
            for source_code, truck_code in specs:
                exclusion = self._exclusion(source, source_code)
                if exclusion is not None and exclusion.is_active:
                    raise CommandError(
                        f"Mapping/exclusion conflict: "
                        f"{source_code_system}:{source_code}."
                    )

                mapping = self._mapping(source, source_code)
                if mapping is None:
                    state = "CREATE"
                elif mapping.truck.internal_code != truck_code:
                    raise CommandError(
                        f"Mapping conflict: {source_code_system}:"
                        f"{source_code} -> {mapping.truck.internal_code}, "
                        f"expected {truck_code}."
                    )
                else:
                    state = "OK"
                self.stdout.write(
                    f"  [{state}] {source_code_system}:{source_code} "
                    f"-> {truck_code}"
                )

    def _apply_mappings(self, sources, trucks):
        for source_system_code, specs in SOURCE_MAPPINGS.items():
            source = sources[source_system_code]
            for source_code, truck_code in specs:
                exclusion = self._exclusion(source, source_code)
                if exclusion is not None and exclusion.is_active:
                    raise CommandError(
                        f"Mapping/exclusion conflict: "
                        f"{source_system_code}:{source_code}."
                    )

                mapping = self._mapping(source, source_code)
                target = trucks[truck_code]
                if mapping is None:
                    mapping = SourceTruckMapping(
                        source_system=source,
                        source_code=source_code,
                        truck=target,
                    )
                elif mapping.truck_id != target.pk:
                    raise CommandError(
                        f"Mapping conflict: {source_system_code}:"
                        f"{source_code}."
                    )

                mapping.is_active = True
                mapping.notes = MAPPING_NOTES
                mapping.full_clean()
                mapping.save()

    def _inspect_exclusions(self, sources):
        self.stdout.write("")
        self.stdout.write("Source truck exclusions:")
        for source_system_code, specs in SOURCE_EXCLUSIONS.items():
            source = sources[source_system_code]
            for source_code, reason in specs:
                mapping = self._mapping(source, source_code)
                if mapping is not None and mapping.is_active:
                    raise CommandError(
                        f"Mapping/exclusion conflict: "
                        f"{source_system_code}:{source_code}."
                    )
                exclusion = self._exclusion(source, source_code)
                state = "CREATE" if exclusion is None else "OK"
                self.stdout.write(
                    f"  [{state}] {source_system_code}:{source_code}"
                )

    def _apply_exclusions(self, sources):
        for source_system_code, specs in SOURCE_EXCLUSIONS.items():
            source = sources[source_system_code]
            for source_code, reason in specs:
                mapping = self._mapping(source, source_code)
                if mapping is not None and mapping.is_active:
                    raise CommandError(
                        f"Mapping/exclusion conflict: "
                        f"{source_system_code}:{source_code}."
                    )

                exclusion = self._exclusion(source, source_code)
                if exclusion is None:
                    exclusion = SourceTruckExclusion(
                        source_system=source,
                        source_code=source_code,
                    )
                exclusion.reason = reason
                exclusion.is_active = True
                exclusion.notes = MAPPING_NOTES
                exclusion.full_clean()
                exclusion.save()

    def _verify(self, sources, trucks):
        for employee_code, first_name, truck_code in GENERIC_WORKERS:
            if not TruckCrewAssignment.objects.filter(
                worker__employee_code=employee_code,
                truck=trucks[truck_code],
                is_primary_seller=True,
                start_date=START_DATE,
                end_date=ASSIGNMENT_END_DATES[employee_code],
            ).exists():
                raise CommandError(
                    f"Assignment verification failed: {employee_code}."
                )

        for source_system_code, specs in SOURCE_MAPPINGS.items():
            source = sources[source_system_code]
            for source_code, truck_code in specs:
                mapping = self._mapping(source, source_code)
                if (
                    mapping is None
                    or not mapping.is_active
                    or mapping.truck_id != trucks[truck_code].pk
                ):
                    raise CommandError(
                        f"Mapping verification failed: "
                        f"{source_system_code}:{source_code}."
                    )

        for source_system_code, specs in SOURCE_EXCLUSIONS.items():
            source = sources[source_system_code]
            for source_code, reason in specs:
                if not SourceTruckExclusion.objects.filter(
                    source_system=source,
                    source_code__iexact=source_code,
                    reason=reason,
                    is_active=True,
                ).exists():
                    raise CommandError(
                        f"Exclusion verification failed: "
                        f"{source_system_code}:{source_code}."
                    )
