# OCVS Draft SDD Flask integration

## Purpose

Phase 3 connects the validated standalone Draft SDD generator to the dedicated Move to OCVS workflow. Phase 4 adds the guided configuration wizard documented in `docs/sdd/OCVS_SDD_CONFIGURATION_WIZARD.md`. The workflow remains unavailable to OCI Compute Migration, Hybrid, Capacity Expansion, and Disaster Recovery.

## Architecture

The integration has three boundaries:

1. `app.py` captures the saved assessment result and exposes the user workflow.
2. `services/ocvs_sdd_adapter.py` converts a frozen saved result plus user-entered Draft details into the Phase 2 JSON contract.
3. `scripts/generate_ocvs_sdd.py` validates and populates the protected master template.

The standalone generator remains independent of Flask and its command-line interface is unchanged.

## Sources of truth

- Inventory Review supplies only the persisted included VM scope.
- Saved Step 4 state supplies topology, assignments, capacity policy, selected profiles, commitment term, commercial inputs, and the sizing timestamp.
- The current OCVS result is frozen when the user selects **Save Draft SDD Details**.
- Document identity and verified business narrative come only from the Draft SDD form.
- Draft generation reads the frozen snapshot and does not invoke sizing or pricing.

The frozen source snapshot is stored separately from `sdd_configuration`. Calculated capacity and cost values are not editable SDD form fields.

## Persisted Draft configuration

`app_state.sdd_configuration` contains the schema version, Draft status, assessment identifier, source hash, sizing timestamp, document identity, business narrative, implementation provider, future design structures, validation results, and last-saved timestamp.

`app_state.sdd_source_snapshot` contains the frozen selected scope, final OCVS sizing, target-cluster rows, and commercial result. Both objects follow the existing portable assessment persistence of `app_state`.

## Snapshot hash and staleness

The adapter serializes source values with sorted keys and calculates SHA-256. Saving Draft details stores that hash. Generation is blocked when selected VM names change, the saved Step 4 timestamp changes, or the active result hash differs. The application never silently approves changed source data; the user must review and save the Draft details again.

## Readiness validation

Blocking checks cover scenario isolation, selected workload, saved source snapshot, topology consistency, exactly one unified management cluster, complete and unique source-cluster assignments, host minima, required identity and business fields, staleness, and the Phase 2 generator contract.

Unavailable pricing is a warning. Monthly and annual amounts are null and the Draft shows `Not available`; no price is invented. Optional network, security, transition, RACI, reviewer, and approver details stay neutral or disabled until Phase 4.

## Route and user interface

The `Solution Definition Document` panel appears only on Results and Export for Move to OCVS. It shows Draft type, topology, selected VM count, target-cluster count, saved sizing timestamp, freshness, completion, blocker count and warning count.

- **Configure Draft SDD** opens the seven-step Phase 4 wizard. Saving any step explicitly rebinds the preserved customer data to the current sizing snapshot.
- **Validate Draft SDD** runs readiness and generator checks without downloading.
- **Generate Draft SDD** is enabled only when blocking checks pass.

All documents retain `DRAFT — NOT FOR CUSTOMER DELIVERY` and require specialist review.

## Security and temporary files

Generation writes input and output into a private temporary directory, reads the completed DOCX into memory, and removes the directory before returning the download. User input never becomes a path. The RVTools path is reduced to its base filename. The master template is never overwritten.

The download name follows `<customer>_ocvs_sdd_draft_<YYYYMMDD_HHMMSS>.docx`.

## Audit fields

The application log records the assessment identifier, source hash, topology, selected workload count, cluster count, output filename, template checksum, input checksum, output checksum, status, and warning count. It does not log customer narrative, email addresses, CIDRs, payloads, or prices.

## Testing

Run:

```text
python -m unittest tests.test_ocvs_sdd_generation tests.test_ocvs_sdd_flask_integration
```

Tests cover single and multi-cluster payloads, selected-scope reconciliation, host minima, safe filenames, unavailable pricing, missing inputs, stale configuration, invalid assignments, scenario isolation, route downloads and failures, portable Draft configuration, and UI scope.

## Known limitations

Phase 4 collects detailed design input but does not certify architecture correctness or provide customer-ready approval. Specialist review remains mandatory. The workflow does not change Inventory Review, sizing, pricing, PowerPoint, or Excel behaviour.
