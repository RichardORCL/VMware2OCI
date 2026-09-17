# OCVS SDD Phase 7 — Customer Acceptance and Implementation Handover

Phase 7 applies only to **Move to OCVS**. It starts automatically when an immutable Phase 6 SDD version is marked as delivered. It does not modify the delivered DOCX, PDF, checksums, delivery manifest, or delivery metadata.

## Lifecycle

1. `acceptance_pending` — the delivered baseline is waiting for a customer decision.
2. `accepted`, `accepted_with_conditions`, or `rejected` — the customer decision is recorded once against that exact delivered version.
3. `handover_ready` — checklist, ownership, action, and integrity rules allow handover.
4. `handed_over` — the accepted SDD version is locked as the implementation baseline.

A rejection requires a governed Phase 6 revision. Starting a new revision preserves the previous acceptance and handover history, marks its baseline as superseded, and requires a new acceptance decision after the new revision is delivered.

## Customer Acceptance & Handover workspace

The workspace is linked from Results & Export, SDD Customer Delivery, and delivered-version history. It shows the customer, project, assessment identifier, delivered version, delivery and recipient details, artifact-integrity state, acceptance state, outstanding conditions, and implementation readiness.

The acceptance form records the minimum customer and internal traceability fields. Accepted-with-conditions entries automatically create open customer-condition actions. Rejected decisions require a reason.

## Readiness controls

The implementation checklist contains 37 governed items across approvals, OCI prerequisites, networking, OCVS platform, migration preparation, and operations. Each item records status, owner, target date, comment, and evidence.

Readiness is calculated as:

- **Not ready** when acceptance is missing or rejected, a mandatory checklist item is incomplete, integrity fails, ownership is missing, or a blocking action is open.
- **Ready with conditions** when the SDD is accepted with conditions and every remaining condition is documented, owned, and non-blocking.
- **Ready for implementation** when the SDD is accepted, mandatory items are complete or not applicable, owners are assigned, integrity is valid, and no blocking action remains.

Actions are append-only records. Closing an action retains it in history; overdue and blocked actions are highlighted. After handover, completed checklist items and the acceptance decision are locked, while actions remain manageable until closure.

## Implementation handover and package

The handover captures the sending and receiving parties, receiving organisation, handover date, implementation owner, migration-planning owner, optional planned start date, and comments. Confirmation creates an immutable audit event and establishes the accepted SDD version as the implementation baseline.

The downloadable package contains exactly nine files:

1. Final delivered SDD DOCX
2. Final delivered SDD PDF
3. Phase 6 delivery manifest JSON
4. Phase 6 delivery manifest Markdown
5. Customer acceptance JSON
6. Implementation readiness checklist XLSX
7. Open-action register XLSX
8. Implementation handover summary PDF
9. Handover manifest JSON

The handover manifest records traceability fields and SHA-256 checksums for every payload artifact. The self-describing manifest is excluded from its own checksum table. No absolute host path is persisted or exported.

## Migration-planning handoff

After handover, **Start Migration Planning** persists a structured payload containing the selected workload scope, source and target clusters, assignments, OCVS shapes and nodes, storage architecture, known dependencies, owners, constraints, open actions, proposed start date, and accepted SDD version. Migration execution is outside Phase 7.

## Audit and integrity

Phase 7 records append-only events for acceptance, conditions, checklist and action changes, readiness recalculation, handover confirmation, package generation, and revision invalidation. Delivered-artifact checksums are verified before acceptance, readiness, handover, and package generation. Opaque identifiers and safe package filenames prevent path traversal and host-path disclosure.

