# Future SDD Configuration workflow

## Placement and intent

Add a non-technical `SDD Configuration` workflow after the final Move to OCVS sizing is saved and before Word export. It must read from a frozen final-sizing snapshot. Changing selected scope, topology, assignments, capacity policy or pricing after configuration started must mark the configuration stale and require review.

Every field displays one of three badges:

- **Calculated by the application** — read-only fact derived from selected scope or saved sizing.
- **Provided by you** — editable customer/engagement input.
- **Specialist confirmation required** — proposed content that cannot become customer-ready until approved.

Top-level actions: `Save draft`, `Validate`, `Preview sections`, `Generate Draft`, and `Generate Customer-ready SDD`. The final action remains disabled until validation passes.

## 1. Customer & Document

**Calculated/read-only:** customer display name, assessment name, scenario, generation date preview, RVTools filename.

**Editable:** legal customer name, project name, author/email, reviewers, approvers, version/comment, customer contacts, business context, drivers, requirements and success criteria.

**Required:** legal name, project, author, version, business context, at least one driver, business and technical requirement, and measurable success criterion.

**Conditional:** reviewer and approver grids appear only when document governance is enabled.

**Validation messages:** `Replace the sample or blank customer name`; `Add at least one measurable success criterion`; `Use a valid document version`.

**Specialist validation:** proposed solution-scope paragraph.

## 2. OCI Target

**Calculated/read-only:** final topology, SDDC count, target-cluster count, cluster names/roles, selected shapes, nodes, sizing drivers, storage architecture and capacity requirements.

**Editable:** tenancy, compartment, OCI region, availability domain, environment names, landing-zone status, naming standard and defined tags.

**Required:** tenancy, compartment, region and landing-zone status.

**Conditional:** AD appears only where relevant; per-cluster review appears in multi-cluster mode. Mixed storage architectures are shown per target cluster.

**Validation messages:** `Select a target OCI region`; `The saved multi-cluster plan is incomplete`; `Final sizing changed—review this section again`.

**Specialist validation:** future-state architecture narrative and any manual target-cluster description.

## 3. Network

**Calculated/read-only:** selected source datacenters, clusters and workload totals.

**Editable:** on-prem CIDRs, VCN CIDR, SDDC CIDR, workload segments, VLAN/subnet rows, DNS, NTP, connectivity type, bandwidth, FastConnect/VPN and routing/firewall details.

**Required:** VCN/SDDC/workload ranges, DNS, NTP, connectivity choice and bandwidth.

**Conditional:** FastConnect fields for FastConnect/Both; VPN fields for IPSec/Both; HCX network details when HCX is enabled.

**Validation messages:** `CIDR is invalid`; `CIDR overlaps another network`; `Complete the BGP and bandwidth details`; `Sample CIDRs are not allowed`.

**Specialist validation:** subnet/VLAN plan, route/security design and non-overlap confirmation.

## 4. Security & Compliance

**Calculated/read-only:** selected storage architecture and standard OCVS/OCI security baseline reference.

**Editable:** regulations, customer security requirements, identity federation, privileged access, logging/SIEM, encryption/KMS and vulnerability monitoring.

**Required:** explicit confirmation of regulations (including `None declared`), security requirements and key-management decision.

**Conditional:** SIEM, customer-managed key and compliance detail panels appear when enabled.

**Validation messages:** `Confirm whether regulatory requirements apply`; `Describe administrative access ownership`; `Approve or replace the proposed security baseline`.

**Specialist validation:** all generated security design text.

## 5. Migration

**Calculated/read-only:** selected workload and optional proposed migration waves from `build_migration_waves()` / `build_migration_plan_records()`.

**Editable:** HCX requirement/edition, migration methods, window, downtime, wave strategy, dependencies, validation, rollback and transfer constraints.

**Required:** HCX decision, methods, window, downtime, validation and rollback.

**Conditional:** HCX panels only when enabled; wave editor only when included; FastConnect migration fields only when that path is selected.

**Validation messages:** `Confirm HCX availability`; `Add a rollback trigger and owner`; `Migration window requires a timezone`; `Review all proposed waves`.

**Specialist validation:** proposed wave membership, method compatibility and bandwidth feasibility.

## 6. Operations

**Calculated/read-only:** final platform quantities and selected architecture.

**Editable:** operating model, monitoring, backup, support ownership, change management, capacity management, HA and DR requirements.

**Required:** operating model, support ownership, change process and explicit backup/DR decisions.

**Conditional:** backup detail only when backup is in scope; DR detail only when enabled; VEEAM wording only when VEEAM is explicitly selected.

**Validation messages:** `Choose whether backup is in scope`; `RPO and RTO are required when DR is enabled`; `Assign an operational owner`.

**Specialist validation:** proposed HA, backup, monitoring and DR architecture.

## 7. Implementation

**Calculated/read-only:** scenario and high-level selected-scope facts.

**Editable:** provider, inclusion of Oracle Lift, scope/out-of-scope, RACI, risks, assumptions, obligations, transition and post-project support.

**Required:** implementation provider. Other fields become required when their section is included.

**Conditional:** Oracle Lift content appears only for provider `Oracle` and explicit `include_oracle_lift=true`; RACI/risks/transition use separate include toggles.

**Validation messages:** `Oracle Lift content requires explicit authorization`; `Each RACI activity needs one Accountable owner`; `Remove or replace sample risks`.

**Specialist validation:** all seeded assumptions, risks, scope and responsibility rows.

## 8. Review & Generate

Display a plain-language readiness dashboard:

- final-sizing snapshot ID and timestamp;
- selected workload count and source clusters;
- single/multi-cluster topology and assignment completeness;
- completed fields by section;
- specialist approvals pending;
- unresolved blocking and non-blocking items;
- sections to include/exclude;
- pricing availability;
- sample-content detector result;
- output type: `Draft` or `Customer-ready`.

### Generation rules

1. **Draft:** permitted when final sizing is valid and critical identity/scope data exists. Add a visible `DRAFT — NOT FOR CUSTOMER DELIVERY` watermark. `To be confirmed` is allowed only for listed non-critical fields.
2. **Customer-ready:** require all mandatory fields, all specialist approvals, zero unresolved samples/placeholders, valid final saved sizing and a clean conditional-section plan.
3. Recalculate nothing during document generation. Read the saved final results only.
4. If multi-cluster is saved, require the valid multi-cluster summary and assignments. Never substitute single-cluster values.
5. Update TOC, headers, footers, dates, version and copyright consistently.
6. Remove excluded modules at the section level, including their headings, page breaks, captions and TOC entries.

## Proposed configuration state

Store an SDD configuration object alongside the assessment, not only in the browser session:

```text
sdd_configuration:
  schema_version
  status: draft | validated
  source_assessment_id
  source_step4_updated_at
  customer_document
  oci_target
  network
  security
  migration
  operations
  implementation
  section_flags
  specialist_approvals
  validation_results
  last_saved_at
```

Do not duplicate calculated sizing values in editable fields. Store the source snapshot identifiers and resolve calculated content from the frozen saved snapshot at generation time. If the source snapshot changes, invalidate prior specialist approvals.

## Accessibility and usability

- Use progressive disclosure; show one section at a time with a completion indicator.
- Explain acronyms and provide examples without pre-populating customer facts.
- Allow import/export of the SDD configuration as part of the portable assessment.
- Keep field labels business-friendly; put implementation keys and code details outside the user interface.
- Provide a preview of the exact section that each input affects.
