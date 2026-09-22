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


def _canonicalize_scope(
    values: Mapping[object, object],
    *,
    default_value: str | None = None,
    label: str,
) -> dict[str, str]:
    result: dict[str, str] = {}

    for raw_source_code, raw_value in values.items():
        source_code = _canonical(raw_source_code)
        if not source_code:
            continue

        value = _canonical(raw_value)
        if not value and default_value is not None:
            value = default_value

        existing = result.get(source_code)
        if existing is not None and existing != value:
            raise ValueError(
                f"Conflicting {label} entries for {source_code}: "
                f"{existing} != {value}"
            )

        result[source_code] = value

    return result


def build_source_truck_scope_snapshot(
    *,
    mappings: Mapping[object, object],
    exclusions: Mapping[object, object],
) -> SourceTruckScopeSnapshot:
    """Build a stable audit fingerprint for the truck scope used by an import.

    The snapshot deliberately stores canonical source codes and resolved
    internal truck codes/reasons rather than database primary keys. This makes
    a review reproducible across restored databases where row IDs can differ.
    Conflicting entries that collapse to the same canonical source code are
    rejected instead of being silently overwritten.
    """
    canonical_mappings = _canonicalize_scope(
        mappings,
        label="mapping",
    )
    canonical_exclusions = _canonicalize_scope(
        exclusions,
        default_value="OUT_OF_SCOPE",
        label="exclusion",
    )

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
