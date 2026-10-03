import re


_SALES_CLIENT_CODE_RE = re.compile(
    r"^(?P<code>\d+)\s+(?P<name>.+)$"
)


def split_sales_client_identity(
    *,
    client: str,
    client_normalized: str,
) -> tuple[str | None, str, str]:
    normalized = client_normalized.strip()
    display = client.strip()

    normalized_match = (
        _SALES_CLIENT_CODE_RE.match(normalized)
    )

    if normalized_match is None:
        return (
            None,
            display,
            normalized,
        )

    code = normalized_match.group("code")
    canonical_normalized = (
        normalized_match.group("name").strip()
    )

    display_match = (
        _SALES_CLIENT_CODE_RE.match(display)
    )

    if display_match is not None:
        canonical_display = (
            display_match.group("name").strip()
        )
    else:
        canonical_display = display

    return (
        code,
        canonical_display,
        canonical_normalized,
    )

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SalesClientIdentityIndex:
    safe_matches: dict[tuple[int, int, str], str]
    ambiguous_keys: frozenset[tuple[int, int, str]]

    def resolve(
        self,
        *,
        brand_id: int,
        truck_id: int,
        client_normalized: str,
    ) -> str | None:
        return self.safe_matches.get(
            (
                brand_id,
                truck_id,
                client_normalized,
            )
        )

    def is_ambiguous(
        self,
        *,
        brand_id: int,
        truck_id: int,
        client_normalized: str,
    ) -> bool:
        return (
            brand_id,
            truck_id,
            client_normalized,
        ) in self.ambiguous_keys

def build_sales_client_identity_index(
    sales_rows,
) -> SalesClientIdentityIndex:
    identities_by_key = {}

    for sale in sales_rows:
        _, _, canonical_normalized = (
            split_sales_client_identity(
                client=sale.client,
                client_normalized=(
                    sale.client_normalized
                ),
            )
        )

        key = (
            sale.brand_id,
            sale.truck_id,
            canonical_normalized,
        )

        identities_by_key.setdefault(
            key,
            set(),
        ).add(
            sale.client_normalized
        )

    safe_matches = {}
    ambiguous_keys = set()

    for key, identities in identities_by_key.items():
        if len(identities) == 1:
            safe_matches[key] = next(iter(identities))
        else:
            ambiguous_keys.add(key)

    return SalesClientIdentityIndex(
        safe_matches=safe_matches,
        ambiguous_keys=frozenset(ambiguous_keys),
    )
