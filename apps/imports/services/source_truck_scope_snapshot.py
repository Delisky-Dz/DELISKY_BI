from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SourceTruckScopeSnapshot:
    mappings: tuple[tuple[str, str], ...]
    exclusions: tuple[tuple[str, str], ...]
    sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "mappings": dict(self.mappings),
            "exclusions": dict(self.exclusions),
            "sha256": self.sha256,
        }


def _canonical(value: object) -> str:
    return " ".join(str(value or "").split()).upper()


def build_source_truck_scope_snapshot(
    *,
    mappings: Mapping[object, object],
    exclusions: Mapping[object, object],
) -> SourceTruckScopeSnapshot:
    """Build a stable audit fingerprint for the truck scope used by an import.

    The snapshot deliberately stores canonical source codes and resolved
    internal truck codes/reasons rather than database primary keys. This makes
    a review reproducible across restored databases where row IDs can differ.
    """
    canonical_mappings = {
        _canonical(source_code): _canonical(internal_code)
        for source_code, internal_code in mappings.items()
        if _canonical(source_code)
    }
    canonical_exclusions = {
        _canonical(source_code): (
            _canonical(reason) or "OUT_OF_SCOPE"
        )
        for source_code, reason in exclusions.items()
        if _canonical(source_code)
    }

    conflicts = sorted(
        set(canonical_mappings) & set(canonical_exclusions)
    )
    if conflicts:
        raise ValueError(
            "Source truck codes cannot be both mapped and excluded: "
            + ", ".join(conflicts)
        )

    mapping_items = tuple(sorted(canonical_mappings.items()))
    exclusion_items = tuple(sorted(canonical_exclusions.items()))

    payload = json.dumps(
        {
            "mappings": mapping_items,
            "exclusions": exclusion_items,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return SourceTruckScopeSnapshot(
        mappings=mapping_items,
        exclusions=exclusion_items,
        sha256=sha256(payload).hexdigest(),
    )
