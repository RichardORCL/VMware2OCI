# OCVS SDD field mapping

## Scope and evidence

This specification covers the `Move to OCVS / Oracle Cloud VMware Solution` scenario and the future generation of an editable customer-specific SDD from `OCVS_SD_Template_v1.docx`.

Evidence reviewed:

- all 27 rendered pages, 408 paragraphs, 15 tables, headers, footers and embedded diagrams in the Word template;
- application state, RVTools parsing, selected-scope logic, OCVS sizing, multi-cluster sizing, pricing and exports in `app.py`;
- no production code, sizing formula, database schema, export or Word template was modified.

The current Word document has no usable business content-control tags. Proposed tags below are future stable `snake_case` identifiers.

## Mapping matrix

| ID | SDD section | Proposed tag | SDD field or content | Example currently in template | Classification | Application source | Code location | Data type | Format/unit | Required | Default value | Validation rule | Conditional rule | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DOC-01 | Cover | `customer_name` | Customer display name | A Company Making Everything | AUTO | `session.customer_name`; saved as snapshot `customer_name` | `app.py:451`, `app.py:1188-1221` | text | 1–120 chars | Yes | none | Not blank; reject sample names | Always | READY | Existing value is a display name; legal name remains separate input. |
| DOC-02 | Cover | `customer_legal_name` | Legal customer entity | Sample company | USER_INPUT | Future SDD configuration | — | text | 1–200 chars | Yes | customer name | User confirms legal entity | Always | MISSING | May equal display name after confirmation. |
| DOC-03 | Cover | `project_name` | Engagement/project name | Strategic program FY23 EXAMPLE | USER_INPUT | Future SDD configuration; `active_assessment_name` can prefill | `app.py:1090`, `app.py:1188-1221` | text | 1–160 chars | Yes | assessment name | Not blank | Always | PARTIAL | Assessment name is a useful prefill, not authoritative project name. |
| DOC-04 | Cover | `document_title` | Document title | Solution Definition Document | STATIC_APPROVED | Template standard | Word template | text | fixed | Yes | OCVS Solution Definition Document | Locked approved value | Always | READY | Keep editable only if governance requires it. |
| DOC-05 | Cover | `document_version` | Version | 1.0 | USER_INPUT | Future SDD configuration | — | text | semantic/document version | Yes | 0.1 Draft | Pattern such as `0.1`, `1.0` | Always | MISSING | Must drive version history too. |
| DOC-06 | Cover | `generation_date` | Generation date | March 6, 2024 | DERIVED | Generation timestamp | future generator; timestamps already used in `app.py:1188-1221` | date | `MMMM d, yyyy` | Yes | current date | Valid date | Always | READY | Do not reuse the saved sample date. |
| DOC-07 | Cover/footer | `copyright_year` | Copyright year | 2022 and 2024 | DERIVED | Generation year | future generator | integer | YYYY | Yes | current year | Same value everywhere | Always | READY | Template years currently conflict. |
| DOC-08 | Document control | `document_author` | Author name | Name Surname | USER_INPUT | Future SDD configuration | — | text | name | Yes | none | Not blank | Always | MISSING | No authenticated author identity in the current app. |
| DOC-09 | Document control | `document_author_email` | Author email | example@example.com | USER_INPUT | Future SDD configuration | — | email | RFC-like email | No | none | Valid email if present | Always | MISSING | Block only if governance requires it. |
| DOC-10 | Document control | `document_reviewers` | Reviewer rows | Name Surname | USER_INPUT | Repeatable future configuration | — | list | name/email/role/company | No | empty | No sample row; unique emails | If review workflow enabled | MISSING | Repeatable structure. |
| DOC-11 | Document control | `document_approvers` | Approver rows | Not explicit | USER_INPUT | Repeatable future configuration | — | list | name/email/role/company | No | empty | Unique approvers | If approval workflow enabled | MISSING | Specialist/management approval. |
| DOC-12 | Document control | `document_change_log` | Version history rows | Sep 1, 2022 Initial version | USER_INPUT | Generated current row + prior saved versions later | — | list | version/author/date/comment | Yes | generation row | Version/date consistency | Always | PARTIAL | Current app has no SDD version history. |
| DOC-13 | TOC | `table_of_contents` | Table of contents | Page references through 32 | DERIVED | Word fields after section removal | future generator | Word field | automatic | Yes | update on open | No stale page numbers | Always | PARTIAL | Generator must update or mark TOC for update. |
| BUS-01 | Business context | `customer_business_context` | Customer overview | Frankfurt, 2500 employees, millions in sales | USER_INPUT | Future SDD configuration | — | rich text | paragraphs | Yes | none | No sample company/location | Always | MISSING | Customer-owned narrative. |
| BUS-02 | Business context | `business_drivers` | Drivers and program goals | FY23 EXAMPLE; reduce spend 15% | USER_INPUT | Future SDD configuration | — | rich text/list | paragraphs | Yes | none | At least one approved driver | Always | MISSING | Do not infer savings targets. |
| BUS-03 | Business context | `solution_scope_summary` | Agreed solution scope | Move workloads to INSERT REGION | SPECIALIST_VALIDATION | Proposed from scenario + selected scope | `app.py:466-504`, `app.py:11399-11796` | rich text | paragraph | Yes | generated proposal | Specialist approval | Always | PARTIAL | Combine application facts with approved prose. |
| BUS-04 | Requirements | `business_requirements` | Business requirements | Generic cost/time-to-market statements | USER_INPUT | Future SDD configuration | — | list | requirement rows | Yes | empty | At least one requirement | Always | MISSING | Avoid unverified generic claims. |
| BUS-05 | Requirements | `technical_requirements` | Technical requirements | Generic OCVS requirements | USER_INPUT | Future SDD configuration | — | list | requirement rows | Yes | empty | At least one requirement | Always | MISSING | Selected shape is a result, not the requirement itself. |
| BUS-06 | Requirements | `success_criteria` | Acceptance/success criteria | Generic Lift completion statement | USER_INPUT | Future SDD configuration | — | list | measurable criteria | Yes | empty | Each criterion measurable | Always | MISSING | Needed for customer-ready SDD. |
| INV-01 | Current state | `rvtools_file_name` | Inventory source file | RVTools data | AUTO | `session.selected_rvtools_file`; portable source file name | `app.py:1188-1221`, `app.py:1423-1499` | text | filename only | Yes | none | Strip local path; file must exist at analysis time | Always | READY | Never expose local filesystem path. |
| INV-02 | Current state | `assessment_name` | Assessment name | None | AUTO | saved snapshot `name` / active assessment name | `app.py:1090`, `app.py:1188-1221` | text | text | Yes | generated assessment name | Not blank | Always | READY | Distinct from project name. |
| INV-03 | Current state | `assessment_date` | Analysis date | Sample dates | DERIVED | `updated_at`/generation date; future explicit field preferred | `app.py:1188-1221` | date | ISO internally; localized display | Yes | generation date | Specialist confirms date meaning | Always | PARTIAL | Decision needed: import date, last sizing save or generation date. |
| INV-04 | Current state | `selected_vm_count` | Selected VMs | 1100 / 550 samples | AUTO | selected VM rows from `app_state.selected_vm_names` | `app.py:557-589`, `app.py:11399-11796` | integer | count | Yes | 0 | Must equal current selected scope | Always | READY | Never use full RVTools count after scope reduction. |
| INV-05 | Current state | `powered_on_vm_count` | Powered-on selected VMs | Not consistently shown | DERIVED | `build_workload_summary(...).powered_on_count` | `app.py:5632-5683` | integer | count | Yes | 0 | On + off + unknown = selected VMs | Always | READY | Selected rows only. |
| INV-06 | Current state | `powered_off_vm_count` | Powered-off selected VMs | Not consistently shown | DERIVED | `build_workload_summary(...).powered_off_count` | `app.py:5632-5683` | integer | count | Yes | 0 | Reconcile with selected count | Always | READY | Unknown power must remain distinct if present. |
| INV-07 | Current state | `selected_vcpu` | Selected vCPU | 3600 sample | DERIVED | sum `row.cpus` for selected VM rows | `app.py:3003-3105`, `app.py:5387-5581` | integer | vCPU | Yes | 0 | Non-negative; flag missing/zero source rows | Always | READY | `build_ocvs_price_summary().totals.vcpus`. |
| INV-08 | Current state | `selected_ram_gb` | Selected RAM | 47160 sample | DERIVED | selected `memory_gb`; RVTools `memory_mb` converted | `app.py:3003-3105`, `app.py:5387-5581` | integer | GB | Yes | 0 | 1 GB = 1024 MB | Always | READY | Quality warnings available for missing RAM. |
| INV-09 | Current state | `selected_storage_tb` | Selected provisioned storage | 60000 sample | DERIVED | selected `provisioned_gb`; totals `storage_gb` | `app.py:3003-3105`, `app.py:5387-5581` | decimal | TB, 1 TB = 1024 GB | Yes | 0 | Do not double-convert; flag missing storage | Always | READY | Keep raw GB for calculations and display TB. |
| INV-10 | Current state | `operating_system_summary` | OS distribution | Generic server inventory | DERIVED | selected rows `raw_os` / `mapped_os` | `app.py:3003-3105` | list | OS/count | No | empty | Include unknown count | If inventory available | READY | Repeatable summary recommended. |
| INV-11 | Current state | `source_datacenters` | Datacenter/location list | DC LOCATION | DERIVED | selected rows `source_datacenter` | `app.py:3003-3105` | list | names | No | Unassigned | No sample value | If supplied by RVTools | PARTIAL | Values depend on RVTools source quality. |
| INV-12 | Current state | `source_vcenters` | vCenter list | Not mapped | DERIVED | selected rows `source_vcenter` | `app.py:3003-3105` | list | names | No | empty | No duplicate display names | If supplied | READY | Useful in architecture appendix. |
| OCVS-01 | Future state | `business_scenario` | Selected scenario | Move to OCVS | AUTO | `session.business_scenario` normalized to `ocvs` | `app.py:174-229`, `app.py:466-504` | enum | id/label | Yes | none | Must equal `ocvs` for this generator | Always | READY | Reject wrong-scenario generation. |
| OCVS-02 | Future state | `ocvs_topology` | Single/multi cluster mode | Single-cluster assumptions | AUTO | `app_state.step4_ocvs_topology` | `app.py:557-589`, `app.py:5141-5144` | enum | `single`/`multi` | Yes | single | Must match saved final sizing | Always | READY | Never silently fall back to single. |
| OCVS-03 | Future state | `sddc_count` | SDDC count | 1 | DERIVED | multi summary `sddc_count`; single result implies 1 | `app.py:5294-5384` | integer | count | Yes | 1 | Positive when workload present | Always | READY | Current multi-cluster model is one SDDC, up to six clusters. |
| OCVS-04 | Future state | `target_cluster_count` | Target cluster count | 1 | DERIVED | multi summary `cluster_count`; single = 1 | `app.py:5294-5384` | integer | count | Yes | 1 | 1–6 | Always | READY | Conditional repeated table below. |
| OCVS-05 | Future state | `total_ocvs_nodes` | Total host/node count | 3+1 sample | DERIVED | multi `total_hosts`; single `selected.host_count` | `app.py:5294-5384`, `app.py:5387-5581` | integer | nodes | Yes | 0 | Sum target-cluster totals | Always | READY | Includes configured spare/DR nodes. |
| OCVS-06 | Future state | `selected_shape` | Selected OCVS shape | DenseIO2.52 / BM.Standard3.48 | AUTO | single `analysis.ocvs.selected.shape` | `app.py:5387-5581`, `app.py:6670-6889` | text | official shape | Yes | none | Must exist in `OCVS_HOST_PROFILES` | Single cluster | READY | Multi-cluster uses per-cluster shape. |
| OCVS-07 | Future state | `sizing_driver` | Binding sizing constraint | 80% target sample | DERIVED | `selected.constraint` (`minimum/cpu/memory/storage`) | `app.py:5387-5581` | enum | label | Yes | none | Must match saved result | Always | READY | Per cluster in multi-cluster. |
| OCVS-08 | Future state | `workload_nodes` | Workload/base nodes | 3 | AUTO | `selected.base_host_count` | `app.py:5387-5581` | integer | nodes | Yes | 0 | Non-negative | Always | READY | Before additional DR/spare nodes. |
| OCVS-09 | Future state | `spare_nodes` | Additional spare/DR nodes | +1 | AUTO | `selected.dr_node_count`; state `step4_ocvs_dr_nodes` | `app.py:557-589`, `app.py:5387-5581` | integer | nodes | Yes | 0 | Allowed normalized range | If resilience nodes configured | READY | UI calls these additional spare nodes in places. |
| OCVS-10 | Future state | `storage_architecture` | vSAN or OCI Block Volume | Both alternatives shown | DERIVED | `_presentation_storage_type(selected.shape)` | `app.py:5294-5384`, `app.py:6929+` | enum | label | Yes | none | DenseIO→vSAN; Standard/Optimized→Block Volume | Always | READY | Per cluster for mixed multi-cluster. |
| OCVS-11 | Future state | `workload_capacity_storage_tb` | Final workload storage requirement | 122 TB / 50 TB samples | DERIVED | `analysis.ocvs.totals.storage_gb` converted to TB | `app.py:5387-5581` | decimal | TB | Yes | 0 | 1 TB = 1024 GB | Always | READY | Distinguish from usable/raw platform capacity. |
| OCVS-12 | Methodology | `vcpu_per_ocpu` | vCPU per OCPU | 1:2 | AUTO | `analysis.ocvs.policy.vcpu_per_ocpu` | `app.py:5387-5581` | decimal | ratio | Yes | policy default | >0 | Always | READY | Display as `x:1` or approved convention. |
| OCVS-13 | Methodology | `cpu_headroom_pct` | CPU headroom | 20% | AUTO | policy `cpu_headroom_pct` | `app.py:5387-5581` | decimal | % | Yes | policy default | 0–99 | Always | READY | Saved final policy only. |
| OCVS-14 | Methodology | `ram_headroom_pct` | RAM headroom | 20% | AUTO | policy `memory_headroom_pct` | `app.py:5387-5581` | decimal | % | Yes | policy default | 0–99 | Always | READY | Tag uses RAM wording; key uses memory. |
| OCVS-15 | Methodology | `storage_headroom_pct` | Storage headroom | 25% | AUTO | policy `storage_headroom_pct` | `app.py:5387-5581` | decimal | % | Yes | policy default | 0–99 | Always | READY | Applies to sizing. |
| OCVS-16 | Methodology | `dense_vsan_usable_pct` | Dense vSAN usable capacity | 50% | AUTO | policy `dense_vsan_usable_pct` | `app.py:5387-5581` | decimal | % | Yes when vSAN | policy default | 1–100 | DenseIO/vSAN | READY | Remove for Block Volume-only design. |
| OCVS-17 | Methodology | `standard_storage_vpu` | Block Volume performance | 10 VPU/GB | AUTO | policy `standard_storage_vpu` | `app.py:5387-5581` | integer | VPU/GB | Yes when Block | 10 | 10–120 in code | Standard/Optimized | READY | Remove for vSAN-only design. |
| NET-01 | OCI target | `oci_region` | Target OCI region | INSERT REGION / Frankfurt | USER_INPUT | Future SDD configuration | — | enum/text | OCI region name/key | Yes | none | Valid enabled OCI region | Always | MISSING | Current price list currency is not a region. |
| NET-02 | OCI target | `tenancy_name_or_ocid` | Tenancy | Not provided | USER_INPUT | Future SDD configuration | — | text | name or OCID | Yes | none | OCID syntax if OCID | Always | MISSING | Sensitive display policy required. |
| NET-03 | OCI target | `compartment_name_or_ocid` | Compartment | Not provided | USER_INPUT | Future SDD configuration | — | text | name or OCID | Yes | none | Validate OCID when used | Always | MISSING | — |
| NET-04 | Networking | `vcn_cidr` | VCN CIDR | 10.0.0.0/16 | USER_INPUT | Future SDD configuration | — | CIDR | IPv4/IPv6 CIDR | Yes | none | Valid CIDR; no overlap | Always | MISSING | Sample must never survive. |
| NET-05 | Networking | `sddc_cidr` | SDDC CIDR | 10.0.0.0/21 | USER_INPUT | Future SDD configuration | — | CIDR | CIDR | Yes | none | Valid supported range; no overlap | Always | MISSING | Requires specialist validation. |
| NET-06 | Networking | `network_segments` | VLAN/subnet rows | 10.0.0.0/26 etc. | USER_INPUT | Repeatable future configuration | — | list | name/CIDR/purpose | Yes | empty | Unique, valid, non-overlapping CIDRs | Always | MISSING | Repeatable table. |
| NET-07 | Networking | `connectivity_type` | FastConnect or VPN | Both described as definite | USER_INPUT | Future SDD configuration | — | enum | FastConnect/IPSec/Both/TBD | Yes | To be confirmed (draft only) | Select one approved option | Always | MISSING | Controls networking modules. |
| NET-08 | Networking | `connectivity_details` | Bandwidth/BGP/provider | FastConnect 10 Gbps sample | USER_INPUT | Future SDD configuration | — | object | structured | Conditional | empty | Validate bandwidth, BGP ASN/IPs | FastConnect/VPN | MISSING | Avoid invented bandwidth. |
| SEC-01 | Security | `security_requirements` | Customer security requirements | Generic baseline | USER_INPUT | Future SDD configuration | — | list/rich text | requirements | Yes | approved baseline proposal | Customer/specialist approval | Always | MISSING | Standard guidance can accompany it. |
| SEC-02 | Security | `compliance_requirements` | Regulations/compliance | Generic text | USER_INPUT | Future SDD configuration | — | list | frameworks | No | none | Approved values only | If applicable | MISSING | Hide section if none and approved. |
| SEC-03 | Security | `identity_federation` | IAM/federation design | Generic IAM guidance | USER_INPUT | Future SDD configuration | — | object | provider/domains/MFA | No | To be confirmed | Specialist validation | If security module included | MISSING | — |
| SEC-04 | Security | `logging_siem` | Logging/SIEM integration | Generic SIEM recommendation | USER_INPUT | Future SDD configuration | — | object | product/endpoints/retention | No | To be confirmed | Specialist validation | If applicable | MISSING | — |
| SEC-05 | Security | `encryption_key_management` | KMS/encryption requirements | Generic OCVS encryption text | USER_INPUT | Future SDD configuration | — | object | choices/notes | No | OCI/OCVS defaults proposed | Explicit approval | If security section | MISSING | Do not claim customer requirement without input. |
| MIG-01 | Migration | `hcx_required` | HCX use | HCX assumed | USER_INPUT | Future SDD configuration | — | boolean | Yes/No/TBD | Yes | proposed Yes | Confirm license/connectivity compatibility | Migration module | MISSING | Scenario alone does not prove HCX availability. |
| MIG-02 | Migration | `migration_method` | HCX method | Bulk, vMotion, DR described | USER_INPUT | Future SDD configuration | — | enum/list | approved methods | Yes | To be confirmed | Compatible with workload/connectivity | Migration module | MISSING | — |
| MIG-03 | Migration | `migration_waves` | Migration wave plan | Generic workplan | DERIVED | `build_migration_waves` / `build_migration_plan_records` | `app.py:5953+`, `app.py:6040+` | list | wave rows | No | generated proposal | Specialist/customer validation | If wave planning enabled | PARTIAL | Current waves are a planning proposal, not approval. |
| MIG-04 | Migration | `migration_window` | Window and schedule | Contract expiry narrative | USER_INPUT | Future SDD configuration | — | text/date range | timezone-aware | Yes | none | Valid dates/timezone | Migration module | MISSING | — |
| MIG-05 | Migration | `downtime_tolerance` | Permitted outage | Minimal interruption | USER_INPUT | Future SDD configuration | — | duration/text | minutes/hours | Yes | none | Non-negative, per workload if needed | Migration module | MISSING | — |
| MIG-06 | Migration | `validation_and_rollback` | Validation/rollback criteria | Generic testing obligations | USER_INPUT | Future SDD configuration | — | rich text/list | steps/owners | Yes | none | Has owner and exit criteria | Migration module | MISSING | — |
| OPS-01 | HA/DR | `ha_requirements` | High availability requirements | Generic OCVS HA | USER_INPUT | Future SDD configuration | — | rich text/list | requirements | No | OCVS standard proposal | Specialist approval | If HA required | MISSING | Separate requirements from standard product description. |
| OPS-02 | HA/DR | `dr_requirements` | DR/RPO/RTO | Generic DR section | USER_INPUT | Future SDD configuration | — | object | RPO/RTO/location | No | none | Numeric RPO/RTO if enabled | If DR required | MISSING | Move-to-OCVS does not imply DR. |
| OPS-03 | Backup | `backup_architecture` | Backup solution | VEEAM assumed | USER_INPUT | Future SDD configuration | — | object | product, retention, repository | No | To be confirmed | Do not assume VEEAM/BYOL | If backup included | MISSING | Existing VEEAM content is conditional. |
| OPS-04 | Operations | `operating_model` | Operations ownership | Generic customer ownership | USER_INPUT | Future SDD configuration | — | rich text/RACI | text | Yes | customer-managed proposal | Named owners | Always | MISSING | — |
| OPS-05 | Operations | `monitoring_model` | Monitoring/tooling | Generic monitoring | USER_INPUT | Future SDD configuration | — | object | tools/alerts/owners | No | OCI baseline proposal | Specialist validation | If operations section | MISSING | — |
| IMP-01 | Implementation | `implementation_provider` | Delivery provider | Oracle Lift assumed | USER_INPUT | Future SDD configuration | — | enum/text | Customer/Oracle/Partner | Yes | Customer/partner | Explicit choice | Always | MISSING | Controls entire implementation module. |
| IMP-02 | Implementation | `implementation_scope` | Delivery scope/workplan | Oracle Lift workplan | USER_INPUT | Future SDD configuration | — | repeatable list | task/deliverable/owner | Conditional | empty | Approved scope only | If implementation included | MISSING | — |
| IMP-03 | Implementation | `raci_rows` | RACI matrix | Static sample rows | USER_INPUT | Future repeatable configuration | — | list | activity/R/A/C/I | No | approved starter rows | One accountable party per row | If RACI included | MISSING | Specialist/customer validation. |
| IMP-04 | Risks | `risk_rows` | Risks and mitigations | RI01–RI08 samples | USER_INPUT | Future repeatable configuration | — | list | id/risk/impact/mitigation/owner | No | empty | No sample risks; owner required | If risks included | MISSING | Standard suggestions may be offered, never auto-approved. |
| IMP-05 | Assumptions | `assumption_rows` | Assumptions/obligations | Static Oracle Lift obligations | SPECIALIST_VALIDATION | Standard candidate rows + user edits | — | list | statement/owner/status | No | scenario starter set | Explicit validation | If included | MISSING | Do not treat standard text as customer fact. |
| IMP-06 | Transition | `transition_plan` | Handover and closure | Oracle Lift handover | USER_INPUT | Future SDD configuration | — | rich text/list | activities/owners/dates | No | empty | Must match provider model | If transition included | MISSING | — |
| BOM-01 | Sizing/BOM | `bom_rows` | Bill of Materials | XXXXX; static SKUs | CONDITIONAL | OCVS result + price-list display names; part numbers not available | `app.py:5387-5581`, `app.py:2031-2048` | list | product/metric/qty/term/storage/availability | Yes | generated rows | No false SKU or amount | If sizing result exists | PARTIAL | Official part number needs a new source or manual validation. |
| PRICE-01 | Pricing | `currency_code` | Currency | Not consistently stated | AUTO | `session.selected_currency` | `app.py:1188-1221`, `app.py:6670-6889` | enum | ISO 4217 | Yes | USD | Supported currency only | If pricing included | READY | — |
| PRICE-02 | Pricing | `iaas_discount_pct` | IaaS discount | Not in template | AUTO | `app_state.step4_iaas_discount_pct` | `app.py:557-589`, `app.py:6670-6889` | decimal | % | No | 0 | 0–100 | If pricing included | READY | Commercially sensitive; optional SDD display. |
| PRICE-03 | Pricing | `commitment_term` | Commitment term | Not explicit | AUTO | `step4_ocvs_commitment_term`; analysis label | `app.py:557-589`, `app.py:5387-5581` | enum | Pay as you go/1-year/3-year | Yes | payg | Supported term | If pricing included | READY | — |
| PRICE-04 | Pricing | `monthly_cost` | Monthly modeled cost | Static BOM only | DERIVED | `selected.selection_monthly_cost`; multi `total_monthly_cost` | `app.py:5294-5384`, `app.py:5387-5581` | money | currency/month | No | Not available | Show only when pricing_available | If pricing included | READY | No fabricated amount. |
| PRICE-05 | Pricing | `annual_cost` | Annual modeled cost | Not explicit | DERIVED | monthly × 12; multi `total_annual_cost` | `app.py:5294-5384` | money | currency/year | No | Not available | Reconcile to monthly | If pricing included | READY | — |
| PRICE-06 | Pricing | `pricing_availability` | Pricing completeness | Not explicit | DERIVED | selected `pricing_available` | `app.py:5387-5581` | boolean | Available/Not available | Yes | false | All required SKU prices present | If pricing module | READY | Controls amounts versus `Not available`. |
| STATIC-01 | Product overview | `ocvs_product_overview` | Standard OCVS description | Long product narrative | STATIC_APPROVED | Curated approved content | Word template after technical review | rich text | paragraphs | No | approved library | Owner/version/date required | Always | REQUIRES_DECISION | Current wording must be checked against current OCI documentation. |
| STATIC-02 | Security | `shared_security_model` | OCI shared responsibility | Standard diagrams/text | STATIC_APPROVED | Curated approved content | Word template | module | section | No | approved library | Security review/versioning | If security included | REQUIRES_DECISION | Keep diagrams only if current and licensed. |
| REMOVE-01 | Entire document | — | Sample company, regions, names, dates, CIDRs and quantities | A Company…, INSERT REGION, 10.0.0.0/16, 550 VMs | REMOVE | Template sample content | Word template | mixed | n/a | Yes | remove | Unresolved sample detector must return zero | Always | OUTDATED | Blocking cleanup. |
| REMOVE-02 | Implementation | — | Unconditional Oracle Lift content | Only for Oracle Implementations | CONDITIONAL | Future `implementation_provider` / include flag | — | section | n/a | No | excluded | Include only after explicit enablement | Oracle/Lift only | NOT_APPLICABLE | Remove cleanly otherwise. |

## Repeatable structures

### `source_cluster_rows`

Source: selected VM rows grouped by `source_cluster` through `build_source_cluster_summaries()` (`app.py:5145-5199`). In the SDD generator, pass the selected rows, not the complete inventory.

| Proposed child tag | Source/calculation | Format |
|---|---|---|
| `source_cluster_name` | summary `name` | text |
| `source_cluster_vm_count` | selected rows in cluster | integer |
| `source_cluster_vcpu` | sum `cpus` | integer vCPU |
| `source_cluster_ram_gb` | sum memory, ceil GB | integer GB |
| `source_cluster_storage_tb` | `storage_gb / 1024` | decimal TB |
| `source_cluster_powered_on` | count `is_powered_on(row)` | integer |
| `source_cluster_powered_off` | count `is_powered_off(row)` | integer |

The current summary function exposes cluster totals and selected count when called with full inventory. The future SDD adapter must explicitly build it from selected rows or filter all measures by `selected_vm_names`.

### `target_ocvs_cluster_rows`

Source: `analysis.ocvs_multi_cluster.clusters` from `build_ocvs_multi_cluster_summary()` (`app.py:5294-5384`). Maximum six rows.

| Proposed child tag | Source/calculation |
|---|---|
| `target_cluster_name` | cluster `name` |
| `target_cluster_role` | `Unified Management Cluster` when `is_management`, otherwise `Workload Cluster` |
| `assigned_source_clusters` | cluster `source_clusters` |
| `target_cluster_vm_count` | cluster `vm_count` |
| `target_cluster_shape` | cluster `selected.shape` |
| `target_cluster_workload_nodes` | cluster `selected.base_host_count` |
| `target_cluster_spare_nodes` | cluster `selected.dr_node_count` |
| `target_cluster_total_nodes` | cluster `selected.host_count` |
| `target_cluster_sizing_driver` | cluster `selected.constraint` |
| `target_cluster_storage_tb` | cluster `totals.storage_gb / 1024` |
| `target_cluster_storage_architecture` | cluster `storage_architecture` |
| `target_cluster_monthly_cost` | cluster `monthly_cost`, only when `pricing_available` |

Minimum host rules already implemented: management cluster 3; Dense workload cluster 3; Standard workload cluster 2. Single-cluster uses the original single result. Multi-cluster generation is allowed only when `is_valid` is true and `unassigned_vm_names` is empty.

### `bom_rows`

| Child tag | Rule |
|---|---|
| `bom_part_number` | `To be confirmed` only in Draft unless an authoritative SKU source is added |
| `bom_product_name` | selected profile display/price-list display name |
| `bom_metric` | host, OCPU-hour, GB-month, VPU/GB-month or approved commercial metric |
| `bom_quantity` | nodes, OCPUs, GB or other exact sizing quantity |
| `bom_commitment_term` | saved OCVS commitment label |
| `bom_storage_component` | vSAN included or OCI Block Volume/performance component |
| `bom_pricing_availability` | derived from `selected.pricing_available` |

### RACI, risks and assumptions

- RACI: repeatable user-entered rows, optionally seeded from an approved library; always customer/specialist validated.
- Risks: user-entered or specialist-proposed repeatable rows; never copy the eight sample risks blindly.
- Assumptions/obligations: approved standard candidate rows may be suggested based on provider and modules, but each row needs explicit validation and an owner.

## Conditional-section matrix

| Module | Controlling value | Include when | Exclude when | Unknown fallback |
|---|---|---|---|---|
| Single-cluster architecture | `step4_ocvs_topology` | `single` | `multi` | Block customer-ready generation |
| Multi-cluster architecture/table | `step4_ocvs_topology`, `ocvs_multi_cluster.is_valid` | `multi` and valid saved assignments | `single` | Block; never fall back to single |
| Unified Management Cluster | first multi-cluster row `is_management` | Multi-cluster | Single-cluster | Block if missing in multi mode |
| Workload clusters | subsequent target rows | Multi and rows exist | No workload clusters | Omit cleanly |
| vSAN design | selected shape/cluster storage architecture | DenseIO/vSAN | all Block Volume | Mixed topology: render per-cluster storage rows and both relevant explanations |
| OCI Block Volume design | selected shape/cluster storage architecture | Standard/Optimized | all DenseIO | Mixed topology: include both, clearly scoped |
| DenseIO sizing | selected shape prefix/type | Dense/DenseIO | Standard/Optimized | Block sizing section if shape unknown |
| Standard/Optimized sizing | selected host type | Standard/Optimized | DenseIO | Block sizing section if shape unknown |
| FastConnect | `connectivity_type` | FastConnect/Both | VPN only | Draft: TBC; customer-ready: block |
| IPSec VPN | `connectivity_type` | IPSec/Both | FastConnect only | Draft: TBC; customer-ready: block |
| HCX | `hcx_required` | Yes | No | Draft TBC; block customer-ready migration design |
| High availability | `ha_requirements.enabled` | Enabled | Explicitly not required | Draft TBC or omit only after approval |
| Disaster recovery | `dr_requirements.enabled` | Enabled | Explicitly excluded | Do not infer from scenario; Draft TBC |
| Backup architecture | `backup_architecture.enabled` | Enabled and product/approach chosen | Explicitly excluded | Draft TBC; never assume VEEAM |
| Customer-managed implementation | `implementation_provider` | Customer | Oracle-only delivery | Draft TBC |
| Oracle/partner implementation | `implementation_provider` | Oracle or Partner | Customer-managed | Draft TBC |
| Oracle Lift project section | `include_oracle_lift` + provider | Explicit true and Oracle engagement | otherwise | Exclude |
| Pricing amounts | `pricing_available` | true | false | Show `Not available`, never zero as a price |
| Security/compliance detail | include flags + entered requirements | enabled | explicitly excluded | Draft TBC summary; customer-ready requires decision |
| RACI | `include_raci` | true and rows validated | false | Omit cleanly |
| Risks | `include_risks` | true and rows validated | false | Omit cleanly |
| Transition | `include_transition` | true and plan supplied | false | Omit cleanly |

## Generation integrity rules

1. Use the saved final assessment state and selected VM rows only.
2. Refuse customer-ready output if the scenario is not `ocvs`, final sizing is absent, or multi-cluster assignments are invalid.
3. Do not carry any sample company, person, location, date, CIDR, quantity, shape, price or implementation statement into output.
4. Render repeatable rows without empty sample rows; remove unused modules without empty headings or blank pages.
5. Mark draft documents visibly and reserve `To be confirmed` for approved non-blocking fields.
6. Rebuild/update the TOC, headers, footers, version, generation date and copyright consistently.
