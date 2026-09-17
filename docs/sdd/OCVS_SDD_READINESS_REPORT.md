# OCVS SDD automation readiness report

## Executive summary

The Move to OCVS application is ready to provide the quantitative core of a customer-specific SDD: selected workload, source clusters, OCVS topology, single- or multi-cluster sizing, shape/node decisions, storage architecture, capacity policy and modeled pricing all have real code sources.

The current Word template is **not yet ready for direct automated customer delivery**. It is a valuable content baseline, but it is an old sample solution document with no useful business content controls, numerous customer examples, inconsistent dates/copyright, static networking and sizing values, unconditional Oracle Lift language and a stale table of contents.

Recommendation: **GO for Phase 1 template preparation; NO-GO for implementing direct customer-ready generation against the unmodified template.**

## Quantitative readiness

The mapping contains **89 mapped content items**.

### By classification

| Classification | Count |
|---|---:|
| AUTO | 18 |
| DERIVED | 22 |
| USER_INPUT | 41 |
| SPECIALIST_VALIDATION | 2 |
| STATIC_APPROVED | 3 |
| CONDITIONAL | 2 |
| REMOVE | 1 |
| **Total** | **89** |

### By status

| Status | Count |
|---|---:|
| READY | 37 |
| PARTIAL | 8 |
| MISSING | 40 |
| REQUIRES_DECISION | 2 |
| OUTDATED | 1 |
| NOT_APPLICABLE | 1 |
| **Total** | **89** |

### Automation readiness

- Directly available or derivable from current application data: **40/89 = 44.9%**.
- Fully READY items: **37/89 = 41.6%**.
- Mapped fields requiring user input: **41**.
- Conditional modules defined: **18**.

The percentage measures mapped SDD items, not page volume. Large standard narrative sections can be reused only after technical/content-owner approval, while a single dynamic repeatable table may populate many document rows.

## What the application can already supply

- customer display name, assessment name and selected business scenario;
- uploaded RVTools filename and inventory quality indicators;
- exact selected VM scope rather than the full inventory;
- selected VM count, power state, vCPU, RAM, storage and OS data;
- source datacenter, vCenter and source-cluster data where RVTools provides it;
- single- or multi-cluster OCVS topology;
- saved source-to-target cluster assignments, up to six target clusters;
- Unified Management Cluster and workload-cluster roles;
- per-cluster selected profile/shape, host counts, sizing driver and storage architecture;
- capacity-policy values and workload capacity requirements;
- commitment term, currency, IaaS discount, monthly/annual price and availability;
- PowerPoint and Excel analysis outputs;
- proposed migration-wave records and vendor-neutral/RackWare/Matilda export contracts.

## Principal missing inputs

1. **Document governance:** legal customer name, project name, author, reviewers, approvers, version and change comment.
2. **Business definition:** business context, drivers, requirements and measurable success criteria.
3. **OCI target:** tenancy, compartment, region, availability domain and landing-zone status.
4. **Networking:** on-prem/VCN/SDDC/workload CIDRs, VLAN plan, DNS, NTP, FastConnect/VPN, BGP and bandwidth.
5. **Security/compliance:** regulations, federation, privileged access, SIEM/logging and key-management decisions.
6. **Migration:** HCX availability, methods, windows, downtime, validation and rollback.
7. **Operations:** monitoring, backup, support, change/capacity management, HA and DR objectives.
8. **Implementation/governance:** provider, scope, RACI, risks, assumptions, obligations and transition.
9. **Commercial catalog:** authoritative BOM part numbers are not currently available from the application price mapping.

## Major template risks

### Blocking risks

- Static sample customer `A Company Making Everything` appears throughout.
- Sample locations and placeholders such as `INSERT REGION`, `DC LOCATION`, `LOCATION` and `ENV NAME` remain.
- Static CIDRs include `10.0.0.0/16`, `10.0.0.0/21` and multiple `/26` networks.
- Static inventory/sizing includes 550/1100 VMs, 1800/3600 vCPU, 23580/47160 memory, 30000/60000 storage, `3+1` nodes and old example shapes.
- BOM contains sample/placeholder entries such as `XXXXX`.
- Oracle Lift implementation commitments are present even though they do not apply to every engagement.
- No business content controls or repeatable-table tags exist.

### Quality and governance risks

- Cover date is March 6, 2024, version history uses September 1, 2022, and copyright years differ between pages.
- The rendered document has 27 pages while the TOC contains references through page 32.
- Product/network/security/HCX statements need current OCVS specialist review before reuse.
- Backup content assumes VEEAM although the customer may use another product or exclude backup design.
- The sample design mostly assumes one cluster; the application now supports one SDDC with up to six target clusters.
- Diagrams and standard text require ownership, versioning and confirmation that they remain current/licensed.

## Data-quality and generation gates

Customer-ready generation must be blocked when:

- the selected business scenario is not Move to OCVS;
- required SDD configuration fields are missing;
- final saved sizing is absent or stale;
- selected-scope totals cannot be reconciled;
- multi-cluster mode is selected but assignments are invalid/unassigned;
- customer/legal name, region, provider or connectivity decision is unresolved;
- CIDRs are invalid, overlap, or equal unresolved sample values;
- required specialist validations are pending;
- any sample token/name/date/value remains;
- the TOC, version/date or footer metadata is inconsistent.

A Draft may be generated only with a visible `DRAFT — NOT FOR CUSTOMER DELIVERY` watermark. Approved non-critical unknowns may display `To be confirmed`; customer-ready output may not.

## Recommended implementation sequence

### Phase 1 — Template preparation

1. Make a controlled copy of the template and remove all sample customer data.
2. Resolve dates, copyright, stale TOC and outdated/duplicated content.
3. Split the document into approved standard and conditional modules.
4. Insert the proposed scalar content controls and repeatable source-cluster, target-cluster, BOM, RACI, risk and assumption tables.
5. Add explicit section markers for topology, storage, connectivity, HCX, HA/DR, backup, provider, pricing and governance modules.
6. Render and visually verify the cleaned template before application work begins.

### Phase 2 — Application data model

1. Add versioned `sdd_configuration` state bound to the saved assessment/final-sizing snapshot.
2. Build the eight-section SDD Configuration workflow.
3. Add validation, specialist approvals, staleness detection and Draft/customer-ready gates.
4. Include configuration in saved and portable assessments.

### Phase 3 — DOCX generation

1. Build a read-only adapter from the frozen final sizing snapshot to the mapped fields.
2. Populate scalar controls and repeatable rows.
3. Apply conditional modules without blank headings/pages.
4. Update document properties, dates, version, footer and TOC.
5. Return an editable `.docx` and preserve the template’s intended styles.

### Phase 4 — Quality assurance

1. Unit-test every AUTO/DERIVED mapping and unit conversion.
2. Test reduced selected scope versus full RVTools inventory.
3. Test single cluster, valid multi-cluster, mixed storage and invalid assignments.
4. Test every conditional section and pricing-unavailable behavior.
5. Detect unresolved content controls, sample phrases, CIDRs and blank required sections.
6. Render the DOCX to PDF/images and visually inspect for overflow, blank pages, table breaks and TOC accuracy.

## Dependencies and risks

- A named OCVS content owner must approve standard architecture, security, networking, HCX and operational wording.
- A document owner must approve the final information architecture and governance/version rules.
- Networking validation needs a reliable CIDR overlap checker.
- BOM part numbers require an authoritative commercial source or an explicit specialist input.
- Word TOC refresh behavior must be tested on the target Office environment; a generator may set fields to update on open but should not assume all viewers recalculate them.
- The generator must never recalculate sizing; it must consume saved final results to preserve auditability.

## Go/no-go

**GO** to build a cleaned, tagged SDD template and the SDD Configuration data model.

**NO-GO** to connect the current sample Word file directly to a customer-ready export. Phase 1 cleanup and content-owner validation are mandatory first.
