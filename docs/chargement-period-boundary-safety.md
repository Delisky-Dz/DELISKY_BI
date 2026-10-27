# Chargement selected-period safety

Both raw Chargement review entry points validate adapted, in-scope data rows before persistence. The inclusive date comparison uses parsed Date&Heure values. Out-of-period data rejects the entire file with `chargement_row_outside_selected_period`; details include the complete count, earliest/latest dates, selected bounds and up to 20 original Excel row numbers. The accountant page displays these details. There is no silent filtering.

Export footers and configured source exclusions are removed by adaptation before validation. Existing missing/invalid datetime errors remain. Legacy exports without the optional Date&Heure column retain compatibility. Mappings remain database-driven. Approved-overlap and replacement rules are unchanged.

## Current period preparation

Use separate upload copies for 2026-08-27 through 2026-10-22. Keep the original 2026-08-26 exports unchanged. The earlier approved batches remain authoritative through 2026-08-26. The prepared BIFA file contains 10,540 data rows, not 10,541: the extra row was the summary. Its stale summary count would otherwise cause row adaptation to fail. AIO contains 4,429 data rows, including one configured VAN_SUPERVISEUR source exclusion.

Upload-copy summaries are recalculated from retained export values, including article count, quantity, quantity-weighted price columns, actual Total for the Prix summary, and quantity/packaging cartons. Exported historical summary values are not reused. Original export cost summaries do not always reconcile exactly to exported detail precision; upload-copy cost summaries explicitly reflect the available retained detail. This does not alter canonical import rows or Production totals. Source workbooks have no formulas. The OOXML edit preserves all non-worksheet package members byte-for-byte, headers, styles and retained detail values.

## Follow-up: unknown source truck review

Implement as a separate feature because it adds a reference-data approval workflow and authorization/audit requirements. Do not create trucks or mappings during upload.

1. Collect unknown source codes and original Excel row numbers into a blocked discovery review.
2. Store source-system-specific naming proposals in configurable database rules, with pattern, canonical prefix, enabled flag and version. For BIFA, proposals may use DCV-XX to BIFA LIVXX and DLV-XX to BIFA PLIVXX. These are suggestions only.
3. Present the proposed existing truck or proposed new truck and brand. Require an authorized reviewer to explicitly confirm each proposal and required truck fields. Do not infer registration numbers.
4. On approval, atomically validate uniqueness, active source/brand/truck, conflict with exclusions and concurrent mappings, then create only the explicitly approved references with an audit trail. Retry upload using normal persisted mappings.
5. Test DCV/DLV separation, zero-padded numbers, typos/unrecognized patterns, inactive references, brand mismatch, exclusion conflicts, duplicate/concurrent approvals, permissions, rollback and audit history. Rejection must never create references.

No deployment or Production approval is included in this change.
