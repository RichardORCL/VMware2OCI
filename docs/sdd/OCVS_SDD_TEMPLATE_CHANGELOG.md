# OCVS SDD automation-ready template changelog

## Files and scope

- Source: `OCVS_SD_Template_v1.docx` (preserved unchanged).
- Output: `document_templates/OCVS_SDD_template_automatable.docx`.
- Rendered pages before: 27.
- Rendered pages after: 26.
- Scope: Phase 1 template cleanup and preparation only; no production generator or Flask integration.

## Removed or neutralized sample content

- Removed the sample customer name, sample people, e-mail addresses and project dates.
- Removed Frankfurt and other engagement-specific location references.
- Removed `INSERT REGION`, data-centre placeholders, sample programme names and sample company facts.
- Replaced sample inventory, sizing, shape, node-count, CIDR, BOM SKU, quantity and pricing values with native Word controls or repeatable rows.
- Replaced fixed sizing-outcome assertions with `target_sizing_summary_narrative` for future approved prose.
- Removed conflicting 2022/2024 copyright dates; the footer and cover now use dynamic year controls.
- No visible `<CUSTOMER>`, `INSERT NAME`, `TBD`, `XXXX` or example CIDR was introduced.

## Corrected document behaviour

- Standardized the document metadata title and set the neutral document version default to `0.1`.
- Added `DRAFT — NOT FOR CUSTOMER DELIVERY` as an editable tagged document element.
- Preserved the approved Oracle confidentiality wording and enabled dynamic copyright year.
- Set Word fields to update on open so TOC and page fields can refresh after conditional generation.
- Preserved the original page size, margins, heading styles, colours, diagrams and overall hierarchy.
- Oracle Lift and delivery-provider detail modules are retained but hidden by default until explicitly enabled.

## Repeatable structures added

- `assumption_rows`
- `bom_rows`
- `customer_obligations`
- `document_approvers`
- `document_change_log`
- `document_reviewers`
- `environments`
- `implementation_scope`
- `network_segments`
- `project_team`
- `raci_rows`
- `risk_rows`
- `source_cluster_rows`
- `target_ocvs_cluster_rows`
- `transition_milestones`

## Conditional sections added

- `section_backup`
- `section_block_volume`
- `section_customer_managed`
- `section_denseio`
- `section_dr`
- `section_fastconnect`
- `section_ha`
- `section_hcx`
- `section_ipsec_vpn`
- `section_multi_cluster`
- `section_oracle_lift`
- `section_oracle_managed`
- `section_partner_managed`
- `section_pricing`
- `section_raci`
- `section_risks`
- `section_security_compliance`
- `section_single_cluster`
- `section_standard_optimized`
- `section_transition`
- `section_vsan`

## Content retained

- Oracle visual identity, cover composition, headers, footers, diagrams and approved confidentiality treatment.
- Standard OCVS product, landing-zone, networking, security, HA/DR, backup, operations, HCX and migration narrative, subject to the validation list below.
- Annex references and OCI security/compliance material.

## Specialist validation required

- OCVS host, cluster and platform limit statements.
- SDDC CIDR rules and the reference network diagrams.
- FastConnect bandwidth/prerequisite wording and IPSec design statements.
- HCX editions, entitlement, migration-method and licensing statements.
- HA, DR, backup and VEEAM product-specific assertions.
- Security, encryption, logging/SIEM and shared-responsibility wording and diagrams.
- OCVS monitoring, operating model and support wording.
- BoQ notes, BYOL statements, part numbers, commercial metrics and any pricing availability.
- Oracle Lift legal, delivery, obligation, RACI, risk and acceptance wording before the module is enabled.

## Oracle Lift handling

- The complete Oracle-specific project implementation module is enclosed by `section_oracle_lift`.
- It is retained in the DOCX for future generation but hidden in the default Draft template.
- Customer-, partner- and Oracle-managed implementation detail modules are separately conditional and hidden by default.

## Diagrams requiring validation

- Current-state VMware architecture diagram.
- OCI landing-zone and physical architecture diagrams.
- Shared security responsibility matrix.
- HA/DR, backup, VPN, FastConnect, SDDC network and HCX diagrams.

## Mapped fields intentionally not placed as editable controls

- `document_title`: retained as approved static cover text and document metadata.
- `table_of_contents`: retained as a native Word TOC field rather than a content control.
- `connectivity_details`: no single unambiguous location; detailed values remain within the repeatable network-segment and conditional connectivity modules.
- `migration_waves`: no approved SDD table was present; defer until the future generator and migration-planning schema are approved.
- `ocvs_product_overview` and `shared_security_model`: retained as curated static modules pending specialist approval rather than dynamic controls.
- `include_*` flags and aggregate list identifiers are generation decisions; their document counterparts are the conditional/repeating wrapper tags listed above.

## Unresolved issues

- Word cannot evaluate business conditions by itself; the future generator must include/remove conditional controls and unhide the selected implementation model.
- Native repeatable-section controls require Microsoft Word-compatible processing in the future generator.
- TOC pagination must be refreshed by Word after the generator removes unused modules.
- Customer-ready generation must remain blocked until mandatory customer, networking, security and migration inputs are approved.

## Complete content-control inventory

| Title | Tag | Word section | Control type | Repeated or scalar | Requirement |
|---|---|---|---|---|---|
| Block Shape | `block_shape` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Block Standard Storage Vpu Detail | `block_standard_storage_vpu_detail` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Block Storage Headroom Pct | `block_storage_headroom_pct` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Block Storage Requirement Tb | `block_storage_requirement_tb` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Block Total Nodes | `block_total_nodes` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Cpu Headroom Pct | `cpu_headroom_pct` | Assumptions and sizing | Editable text/rich text | No | Required |
| Dense Shape | `dense_shape` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Dense Storage Headroom Pct | `dense_storage_headroom_pct` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Dense Storage Requirement Tb | `dense_storage_requirement_tb` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Dense Total Nodes | `dense_total_nodes` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Dense Vsan Usable Pct | `dense_vsan_usable_pct` | Assumptions and sizing | Editable text/rich text | No | Optional / conditional |
| Dense Vsan Usable Pct Detail | `dense_vsan_usable_pct_detail` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Ram Headroom Pct | `ram_headroom_pct` | Assumptions and sizing | Editable text/rich text | No | Required |
| Single Cluster Shape | `single_cluster_shape` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Single Cluster Sizing Driver | `single_cluster_sizing_driver` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Single Cluster Spare Nodes | `single_cluster_spare_nodes` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Single Cluster Storage Architecture | `single_cluster_storage_architecture` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Single Cluster Workload Nodes | `single_cluster_workload_nodes` | Assumptions and sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Standard Storage Vpu | `standard_storage_vpu` | Assumptions and sizing | Editable text/rich text | No | Optional / conditional |
| Storage Headroom Pct | `storage_headroom_pct` | Assumptions and sizing | Editable text/rich text | No | Required |
| Vcpu Per Ocpu | `vcpu_per_ocpu` | Assumptions and sizing | Editable text/rich text | No | Required |
| Bom Commitment Term | `bom_commitment_term` | Bill of Materials | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Bom Metric | `bom_metric` | Bill of Materials | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Bom Part Number | `bom_part_number` | Bill of Materials | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Bom Pricing Availability | `bom_pricing_availability` | Bill of Materials | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Bom Product Name | `bom_product_name` | Bill of Materials | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Bom Quantity | `bom_quantity` | Bill of Materials | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Bom Rows | `bom_rows` | Bill of Materials | Repeating section | Yes | Required |
| Bom Rows Item | `bom_rows_item` | Bill of Materials | Repeating section item | Yes | Optional / conditional |
| Bom Storage Component | `bom_storage_component` | Bill of Materials | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Business Drivers | `business_drivers` | Business context and requirements | Editable text/rich text | No | Required |
| Business Requirements | `business_requirements` | Business context and requirements | Editable text/rich text | No | Required |
| Customer Business Context | `customer_business_context` | Business context and requirements | Editable text/rich text | No | Required |
| Solution Scope Summary | `solution_scope_summary` | Business context and requirements | Editable text/rich text | No | Required |
| Success Criteria | `success_criteria` | Business context and requirements | Editable text/rich text | No | Required |
| Technical Requirements | `technical_requirements` | Business context and requirements | Editable text/rich text | No | Required |
| Annual Cost | `annual_cost` | Commercial Summary | Editable text/rich text | No | Optional / conditional |
| Commitment Term | `commitment_term` | Commercial Summary | Editable text/rich text | No | Required |
| Currency Code | `currency_code` | Commercial Summary | Editable text/rich text | No | Required |
| Iaas Discount Pct | `iaas_discount_pct` | Commercial Summary | Editable text/rich text | No | Optional / conditional |
| Monthly Cost | `monthly_cost` | Commercial Summary | Editable text/rich text | No | Optional / conditional |
| Pricing Availability | `pricing_availability` | Commercial Summary | Editable text/rich text | No | Required |
| Section Backup | `section_backup` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Block Volume | `section_block_volume` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Customer Managed | `section_customer_managed` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Denseio | `section_denseio` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Dr | `section_dr` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Fastconnect | `section_fastconnect` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Ha | `section_ha` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Hcx | `section_hcx` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Ipsec Vpn | `section_ipsec_vpn` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Multi Cluster | `section_multi_cluster` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Oracle Lift | `section_oracle_lift` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Oracle Managed | `section_oracle_managed` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Partner Managed | `section_partner_managed` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Pricing | `section_pricing` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Raci | `section_raci` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Risks | `section_risks` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Security Compliance | `section_security_compliance` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Single Cluster | `section_single_cluster` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Standard Optimized | `section_standard_optimized` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Transition | `section_transition` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Section Vsan | `section_vsan` | Conditional module | Conditional rich-text section | No | Optional / conditional |
| Copyright Year | `copyright_year` | Cover / document metadata | Editable text/rich text | No | Required |
| Cover Customer Name | `cover_customer_name` | Cover / document metadata | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Cover Document Version | `cover_document_version` | Cover / document metadata | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Cover Generation Date | `cover_generation_date` | Cover / document metadata | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Customer Legal Name | `customer_legal_name` | Cover / document metadata | Editable text/rich text | No | Required |
| Customer Name | `customer_name` | Cover / document metadata | Editable text/rich text | No | Required |
| Document Version | `document_version` | Cover / document metadata | Editable text/rich text | No | Required |
| Generation Date | `generation_date` | Cover / document metadata | Editable text/rich text | No | Required |
| Project Name | `project_name` | Cover / document metadata | Editable text/rich text | No | Required |
| Assessment Date | `assessment_date` | Current State Architecture | Editable text/rich text | No | Required |
| Assessment Name | `assessment_name` | Current State Architecture | Editable text/rich text | No | Required |
| Operating System Summary | `operating_system_summary` | Current State Architecture | Editable text/rich text | No | Optional / conditional |
| Powered Off Vm Count | `powered_off_vm_count` | Current State Architecture | Editable text/rich text | No | Required |
| Powered On Vm Count | `powered_on_vm_count` | Current State Architecture | Editable text/rich text | No | Required |
| Rvtools File Name | `rvtools_file_name` | Current State Architecture | Editable text/rich text | No | Required |
| Selected Ram Gb | `selected_ram_gb` | Current State Architecture | Editable text/rich text | No | Required |
| Selected Storage Tb | `selected_storage_tb` | Current State Architecture | Editable text/rich text | No | Required |
| Selected Vcpu | `selected_vcpu` | Current State Architecture | Editable text/rich text | No | Required |
| Selected Vm Count | `selected_vm_count` | Current State Architecture | Editable text/rich text | No | Required |
| Source Cluster Name | `source_cluster_name` | Current State Architecture | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Source Cluster Powered Off | `source_cluster_powered_off` | Current State Architecture | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Source Cluster Powered On | `source_cluster_powered_on` | Current State Architecture | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Source Cluster Ram Gb | `source_cluster_ram_gb` | Current State Architecture | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Source Cluster Rows | `source_cluster_rows` | Current State Architecture | Repeating section | Yes | Required |
| Source Cluster Rows Item | `source_cluster_rows_item` | Current State Architecture | Repeating section item | Yes | Optional / conditional |
| Source Cluster Storage Tb | `source_cluster_storage_tb` | Current State Architecture | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Source Cluster Vcpu | `source_cluster_vcpu` | Current State Architecture | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Source Cluster Vm Count | `source_cluster_vm_count` | Current State Architecture | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Source Datacenters | `source_datacenters` | Current State Architecture | Editable text/rich text | No | Optional / conditional |
| Source Vcenters | `source_vcenters` | Current State Architecture | Editable text/rich text | No | Optional / conditional |
| Approver Company | `approver_company` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Approver Email | `approver_email` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Approver Name | `approver_name` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Approver Role | `approver_role` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Document Approvers | `document_approvers` | Document Control | Repeating section | Yes | Optional / conditional |
| Document Author | `document_author` | Document Control | Editable text/rich text | No | Required |
| Document Author Email | `document_author_email` | Document Control | Editable text/rich text | No | Optional / conditional |
| Document Change Log | `document_change_log` | Document Control | Repeating section | Yes | Required |
| Document Reviewers | `document_reviewers` | Document Control | Repeating section | Yes | Optional / conditional |
| Document Version Comment | `document_version_comment` | Document Control | Editable text/rich text | No | Optional / conditional |
| Project Team | `project_team` | Document Control | Repeating section | Yes | Optional / conditional |
| Project Team Company | `project_team_company` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Project Team Email | `project_team_email` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Project Team Item | `project_team_item` | Document Control | Repeating section item | Yes | Optional / conditional |
| Project Team Name | `project_team_name` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Project Team Role | `project_team_role` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Reviewer Company | `reviewer_company` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Reviewer Email | `reviewer_email` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Reviewer Name | `reviewer_name` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Reviewer Role | `reviewer_role` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Version History Author | `version_history_author` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Version History Comment | `version_history_comment` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Version History Date | `version_history_date` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Version History Version | `version_history_version` | Document Control | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Backup Architecture | `backup_architecture` | HA / DR / backup / operations | Editable text/rich text | No | Optional / conditional |
| Dr Requirements | `dr_requirements` | HA / DR / backup / operations | Editable text/rich text | No | Optional / conditional |
| Ha Requirements | `ha_requirements` | HA / DR / backup / operations | Editable text/rich text | No | Optional / conditional |
| Monitoring Model | `monitoring_model` | HA / DR / backup / operations | Editable text/rich text | No | Optional / conditional |
| Operating Model | `operating_model` | HA / DR / backup / operations | Editable text/rich text | No | Required |
| Implementation Provider | `implementation_provider` | Implementation Approach | Editable text/rich text | No | Required |
| Assumption Owner | `assumption_owner` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Assumption Rows | `assumption_rows` | Implementation governance | Repeating section | Yes | Optional / conditional |
| Assumption Rows Item | `assumption_rows_item` | Implementation governance | Repeating section item | Yes | Optional / conditional |
| Assumption Statement | `assumption_statement` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Assumption Status | `assumption_status` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Customer Obligations | `customer_obligations` | Implementation governance | Repeating section | Yes | Optional / conditional |
| Implementation Scope | `implementation_scope` | Implementation governance | Repeating section | Yes | Optional / conditional |
| Obligation Due Date | `obligation_due_date` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Obligation Owner | `obligation_owner` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Obligation Statement | `obligation_statement` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Raci Accountable | `raci_accountable` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Raci Activity | `raci_activity` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Raci Consulted | `raci_consulted` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Raci Informed | `raci_informed` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Raci Responsible | `raci_responsible` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Raci Rows | `raci_rows` | Implementation governance | Repeating section | Yes | Optional / conditional |
| Raci Rows Item | `raci_rows_item` | Implementation governance | Repeating section item | Yes | Optional / conditional |
| Risk Description | `risk_description` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Risk Id | `risk_id` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Risk Impact | `risk_impact` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Risk Mitigation | `risk_mitigation` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Risk Owner | `risk_owner` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Risk Rows | `risk_rows` | Implementation governance | Repeating section | Yes | Optional / conditional |
| Risk Rows Item | `risk_rows_item` | Implementation governance | Repeating section item | Yes | Optional / conditional |
| Scope Activity | `scope_activity` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Scope Deliverable | `scope_deliverable` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Scope Owner | `scope_owner` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Transition Acceptance | `transition_acceptance` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Transition Date | `transition_date` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Transition Milestone | `transition_milestone` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Transition Milestones | `transition_milestones` | Implementation governance | Repeating section | Yes | Optional / conditional |
| Transition Milestones Item | `transition_milestones_item` | Implementation governance | Repeating section item | Yes | Optional / conditional |
| Transition Owner | `transition_owner` | Implementation governance | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Transition Plan | `transition_plan` | Implementation governance | Editable text/rich text | No | Optional / conditional |
| Compartment Name Or Ocid | `compartment_name_or_ocid` | Networking / OCI target | Editable text/rich text | No | Required |
| Connectivity Type | `connectivity_type` | Networking / OCI target | Editable text/rich text | No | Required |
| Network Segment Cidr | `network_segment_cidr` | Networking / OCI target | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Network Segment Name | `network_segment_name` | Networking / OCI target | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Network Segment Purpose | `network_segment_purpose` | Networking / OCI target | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Network Segments | `network_segments` | Networking / OCI target | Repeating section | Yes | Optional / conditional |
| Oci Region | `oci_region` | Networking / OCI target | Editable text/rich text | No | Required |
| Sddc Cidr | `sddc_cidr` | Networking / OCI target | Editable text/rich text | No | Required |
| Target Region Summary | `target_region_summary` | Networking / OCI target | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Tenancy Name Or Ocid | `tenancy_name_or_ocid` | Networking / OCI target | Editable text/rich text | No | Required |
| Vcn Cidr | `vcn_cidr` | Networking / OCI target | Editable text/rich text | No | Required |
| Workload Cidrs | `workload_cidrs` | Networking / OCI target | Editable text/rich text | No | Optional / conditional |
| Downtime Tolerance | `downtime_tolerance` | OCVS Migration | Editable text/rich text | No | Required |
| Hcx Required | `hcx_required` | OCVS Migration | Editable text/rich text | No | Optional / conditional |
| Migration Method | `migration_method` | OCVS Migration | Editable text/rich text | No | Required |
| Migration Window | `migration_window` | OCVS Migration | Editable text/rich text | No | Required |
| Validation And Rollback | `validation_and_rollback` | OCVS Migration | Editable text/rich text | No | Required |
| Compliance Requirements | `compliance_requirements` | Security and compliance | Editable text/rich text | No | Optional / conditional |
| Encryption Key Management | `encryption_key_management` | Security and compliance | Editable text/rich text | No | Optional / conditional |
| Identity Federation | `identity_federation` | Security and compliance | Editable text/rich text | No | Optional / conditional |
| Logging Siem | `logging_siem` | Security and compliance | Editable text/rich text | No | Optional / conditional |
| Security Requirements | `security_requirements` | Security and compliance | Editable text/rich text | No | Required |
| Assigned Source Clusters | `assigned_source_clusters` | Supporting template field | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Business Scenario | `business_scenario` | Supporting template field | Editable text/rich text | No | Required |
| Copyright Year Cover | `copyright_year_cover` | Supporting template field | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Customer Obligations Item | `customer_obligations_item` | Supporting template field | Repeating section item | Yes | Optional / conditional |
| Document Approvers Item | `document_approvers_item` | Supporting template field | Repeating section item | Yes | Optional / conditional |
| Document Change Log Item | `document_change_log_item` | Supporting template field | Repeating section item | Yes | Optional / conditional |
| Document Reviewers Item | `document_reviewers_item` | Supporting template field | Repeating section item | Yes | Optional / conditional |
| Draft Watermark | `draft_watermark` | Supporting template field | Editable text/rich text | No | Optional / conditional |
| Environment Assessment Coverage | `environment_assessment_coverage` | Supporting template field | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Environment Location | `environment_location` | Supporting template field | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Environment Name | `environment_name` | Supporting template field | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Environment Scope | `environment_scope` | Supporting template field | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Environments | `environments` | Supporting template field | Repeating section | Yes | Optional / conditional |
| Environments Item | `environments_item` | Supporting template field | Repeating section item | Yes | Optional / conditional |
| Implementation Scope Item | `implementation_scope_item` | Supporting template field | Repeating section item | Yes | Optional / conditional |
| Network Segments Item | `network_segments_item` | Supporting template field | Repeating section item | Yes | Optional / conditional |
| Target Ocvs Cluster Rows Item | `target_ocvs_cluster_rows_item` | Supporting template field | Repeating section item | Yes | Optional / conditional |
| Target Sizing Summary Narrative | `target_sizing_summary_narrative` | Supporting template field | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Ocvs Topology | `ocvs_topology` | Target OCVS Architecture Sizing | Editable text/rich text | No | Required |
| Sddc Count | `sddc_count` | Target OCVS Architecture Sizing | Editable text/rich text | No | Required |
| Selected Shape | `selected_shape` | Target OCVS Architecture Sizing | Editable text/rich text | No | Optional / conditional |
| Sizing Driver | `sizing_driver` | Target OCVS Architecture Sizing | Editable text/rich text | No | Required |
| Spare Nodes | `spare_nodes` | Target OCVS Architecture Sizing | Editable text/rich text | No | Required |
| Storage Architecture | `storage_architecture` | Target OCVS Architecture Sizing | Editable text/rich text | No | Required |
| Target Cluster Count | `target_cluster_count` | Target OCVS Architecture Sizing | Editable text/rich text | No | Required |
| Target Cluster Monthly Cost | `target_cluster_monthly_cost` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Name | `target_cluster_name` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Role | `target_cluster_role` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Shape | `target_cluster_shape` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Sizing Driver | `target_cluster_sizing_driver` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Spare Nodes | `target_cluster_spare_nodes` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Storage Architecture | `target_cluster_storage_architecture` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Storage Tb | `target_cluster_storage_tb` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Total Nodes | `target_cluster_total_nodes` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Vm Count | `target_cluster_vm_count` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Cluster Workload Nodes | `target_cluster_workload_nodes` | Target OCVS Architecture Sizing | Editable text/rich text | Yes when inside repeated row | Optional / conditional |
| Target Ocvs Cluster Rows | `target_ocvs_cluster_rows` | Target OCVS Architecture Sizing | Repeating section | Yes | Required |
| Total Ocvs Nodes | `total_ocvs_nodes` | Target OCVS Architecture Sizing | Editable text/rich text | No | Required |
| Workload Capacity Storage Tb | `workload_capacity_storage_tb` | Target OCVS Architecture Sizing | Editable text/rich text | No | Required |
| Workload Nodes | `workload_nodes` | Target OCVS Architecture Sizing | Editable text/rich text | No | Required |

## Verification

- Total content controls: 219.
- Repeatable structures: 15.
- Conditional sections: 21.
- Automated validation checks required tags, unique scalar tags, repeat nesting, conditional markers, forbidden samples, private sample CIDRs, Oracle Lift enclosure and DOCX package validity.
- The final DOCX was rendered and visually inspected page by page; no overlaps, clipping, broken tables, blank pages or orphaned headings were found.
- The source checksum remains unchanged and no production application file was modified.
