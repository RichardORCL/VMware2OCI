# OCVS Draft SDD Configuration wizard

## Purpose and scope

Phase 4 replaces the compact Draft SDD form with a seven-step, non-technical wizard. It is available only for the dedicated `Move to OCVS` / `Oracle Cloud VMware Solution` (`ocvs`) business scenario. OCI Compute Migration, OCI Native, Hybrid, Capacity Expansion and Disaster Recovery do not expose this workflow.

Every output remains **DRAFT — NOT FOR CUSTOMER DELIVERY**. The wizard does not perform customer approval, specialist sign-off, sizing or pricing.

## Architecture

The workflow keeps the Phase 3 boundaries:

1. `app.py` provides `/step4/sdd/configure` and `/step4/sdd/configure/<section>`, saves one section at a time, and continues to use the secure `/step4/sdd` validation and generation route.
2. `templates/sdd_wizard.html`, `static/css/sdd-wizard.css` and `static/js/sdd-wizard.js` provide the accessible interface and client-side repeatable-row controls.
3. `services/ocvs_sdd_adapter.py` normalizes Phase 3 and Phase 4 state, validates sections, calculates readiness and maps the frozen snapshot to the existing Phase 2 generator contract.
4. `scripts/generate_ocvs_sdd.py` and `schemas/ocvs_sdd_generation.schema.json` remain the validated standalone generator and contract.

## Wizard steps

| Step | User-owned information |
|---|---|
| Customer & Project | Legal name, project, assessment, author, version, classification, reviewers, approvers and team |
| Business Requirements | Verified business context, drivers, scope, requirements, success criteria, assumptions, risks, obligations and exclusions |
| OCI Network Design | OCI target, CIDRs, DNS/NTP, DRG, FastConnect, VPN, HCX and repeatable network segments |
| Security & Compliance | Explicitly enabled customer IAM, encryption, logging, SIEM, monitoring, security, compliance and responsibility notes |
| Operations & Resilience | Provider, operating model, monitoring, backup, DR, HA, support, escalation, ownership and service management |
| Migration & Transition | Method, tooling, waves, window, downtime, validation, rollback, scope, milestones, obligations, risks and RACI |
| Review & Generate | Read-only document, workload, topology, sizing and commercial summaries; enabled modules; blockers and warnings |

Users may save incomplete steps. `Save & Continue` advances only when that step has no blocking validation error. `Save Draft` stays on the current step. Saved values survive leaving and returning to the wizard.

## Field ownership and sources of truth

User-entered narrative and customer design decisions live only in `sdd_configuration`. The wizard does not create customer facts, reviewers, approvers, CIDRs or commitments.

Calculated information lives only in the frozen `sdd_source_snapshot`:

- selected VM, power-state, vCPU, RAM, storage and OS totals;
- source vCenters, datacenters and clusters;
- final single- or multi-cluster topology;
- profiles, shapes, sizing drivers, host counts, storage and storage architecture;
- capacity policy, commitment term, currency, discount and authoritative pricing availability.

The review page displays these calculated values read-only. They are never copied into editable wizard fields.

## Persisted configuration

`app_state.sdd_configuration` uses schema version `2.0` and contains:

```text
schema_version, status
source_assessment_id, source_snapshot_hash, source_step4_updated_at
customer_document, business, network, security, operations, delivery
section_flags
wizard.current_step, wizard.completed_steps
wizard.completion_percentage, wizard.last_saved_section
validation_results, last_saved_at
```

`app_state.sdd_source_snapshot` remains separate. Portable assessment export/import preserves both objects, clears installation-local assessment identifiers and stores only the RVTools base filename.

## Normalization and backward compatibility

`normalize_sdd_configuration()` accepts missing objects and Phase 3 schema `1.0` state. It supplies safe Phase 4 defaults, preserves multiline narratives, normalizes dynamic rows and keeps the output status as Draft. Older RACI and transition-row fields are accepted and mapped into the unchanged generator contract.

Optional values are represented by an explicit user value such as `Not provided` or `Not applicable`; the application does not insert sample customer narratives or IP ranges.

## Snapshot and staleness

The frozen source snapshot is serialized deterministically and hashed with SHA-256. A configuration save explicitly binds the current wizard data to the current sizing result.

Readiness compares the saved hash with the current result. Changes to selected scope, source clusters, target topology and assignments, capacity policy, profiles, shapes, host counts, storage, commitment, currency, discount or pricing make the configuration stale. Narrative data is retained, but generation is blocked until the user reviews and saves the configuration again.

The generation route reloads persisted state and uses the frozen snapshot; it never recalculates or silently accepts changed sizing.

## Readiness and completion

The adapter returns:

- overall readiness;
- completion percentage and per-step completion;
- blocking errors grouped by step;
- warnings grouped by step;
- missing required and optional inputs;
- specialist-review items;
- current/stale status.

Required document and business fields are blockers. Invalid emails, document versions and CIDRs are blockers. Enabled Security, RACI, Risks and Transition modules require their mandatory information. Disabled optional modules do not reduce readiness. Unavailable pricing is a warning and remains `Not available`; no amount is invented.

The export-panel **Generate Draft SDD** action remains disabled until all blockers are resolved.

## Dynamic rows

The browser can add and remove reviewers, approvers, project-team members, network segments, implementation-scope items, milestones, risks, obligations and RACI rows. The server reads every posted column, removes fully blank rows, caps row counts and normalizes values before persistence. Server validation remains authoritative.

## Security and generation

The existing `/step4/sdd` route continues to validate the generator payload, use a private temporary directory, return the editable DOCX from memory, clean temporary files and verify that the protected master template is unchanged. Logs contain non-sensitive audit metadata only—never narratives, emails, CIDRs, prices or local paths.

## Tests

Focused Phase 4 tests are in `tests/test_ocvs_sdd_wizard.py`. Phase 2/3 generator, adapter, route and portable-assessment tests remain in place.

Run Flask and persistence tests with the application Python environment, and generator tests with the bundled document runtime. Visual QA must render a complete single-cluster Draft, complete multi-cluster Draft and a Draft with optional modules disabled to PDF and page images before release.

## Limitations

The wizard validates formatting and completeness, not architecture correctness. CIDR overlap, HCX feasibility, RPO/RTO, security controls, commercial authority, migration waves and customer obligations still require an OCVS specialist review. Customer-ready approval remains outside Phase 4.
