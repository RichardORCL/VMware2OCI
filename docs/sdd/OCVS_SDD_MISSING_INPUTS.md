# OCVS SDD missing inputs

These inputs are not authoritative in the current VMware2OCI state. They must be collected or explicitly confirmed before customer-ready SDD generation. `TBC` is permitted only in a watermarked Draft and only for fields marked non-blocking.

## 1. Customer and engagement

| Field label | Proposed key | Input type | Required | Default/prefill | Validation | Help text | SDD destination |
|---|---|---|---|---|---|---|---|
| Legal customer name | `customer_legal_name` | text | Yes | Current customer display name | 1–200 chars; reject sample names | Legal entity shown in the document | Cover, context, obligations |
| Project name | `project_name` | text | Yes | Assessment name | 1–160 chars | Customer engagement/program name | Cover, implementation |
| Document author | `document_author` | text | Yes | none | Non-empty | Person responsible for the SDD | Document control |
| Author email | `document_author_email` | email | No | none | Valid email | Business contact for document questions | Document control |
| Reviewers | `document_reviewers` | repeatable people | No | empty | Unique valid emails | Technical and customer reviewers | Document control |
| Approvers | `document_approvers` | repeatable people | No | empty | Unique valid emails | Formal approvers where required | Document control |
| Document version | `document_version` | text | Yes | `0.1` | Version pattern | Use `0.x` for drafts and approved convention for final | Cover, history, footer |
| Version comment | `document_version_comment` | text | Yes | Initial generated draft | 1–250 chars | Summary of this version | Version history |
| Customer contacts/team | `customer_contacts` | repeatable people | No | empty | Name, role and company | Customer SMEs and owners | Project team |
| Business context | `customer_business_context` | rich text | Yes | none | Must not contain samples | Concise business and estate context | Business context |
| Business drivers | `business_drivers` | repeatable text | Yes | empty | At least one | Why the migration is being undertaken | Business context |
| Business requirements | `business_requirements` | repeatable text | Yes | empty | At least one | Outcomes the solution must support | Requirements |
| Technical requirements | `technical_requirements` | repeatable text | Yes | empty | At least one | Constraints and technical objectives | Requirements |
| Success criteria | `success_criteria` | repeatable text | Yes | empty | Measurable criteria | Conditions for acceptance | Requirements, transition |

## 2. OCI target information

| Field label | Proposed key | Input type | Required | Default/prefill | Validation | Help text | SDD destination |
|---|---|---|---|---|---|---|---|
| Tenancy name or OCID | `tenancy_name_or_ocid` | text | Yes | none | Valid OCID if prefixed `ocid1.` | Target OCI tenancy | Future state |
| Compartment name or OCID | `compartment_name_or_ocid` | text | Yes | none | Valid OCID when used | Target compartment for OCVS resources | Future state |
| OCI region | `oci_region` | searchable select | Yes | none | Enabled OCI region | Region where the SDDC will be deployed | Cover/context/future state |
| Availability domain | `availability_domain` | select/text | Conditional | none | Valid for selected region | Planned AD where applicable | Future state |
| Environment names | `environment_names` | repeatable text | No | Production | Unique names | Production, non-production, DR, etc. | Current/future state |
| Landing-zone status | `landing_zone_status` | select | Yes | To be confirmed | Existing / Planned / Not in scope | Identifies prerequisites and ownership | OCI architecture |
| Target naming standard | `resource_naming_standard` | text | No | none | No invalid OCI characters | Customer naming convention | OCI architecture |
| Tags | `defined_tags` | repeatable key/value | No | empty | Valid namespace/key | Governance and chargeback tags | OCI architecture |

## 3. Networking

| Field label | Proposed key | Input type | Required | Default | Validation | Help text | SDD destination |
|---|---|---|---|---|---|---|---|
| On-premises CIDRs | `onprem_cidrs` | repeatable CIDR | Yes | empty | Valid, unique, non-overlapping | Networks that require connectivity | Current state/networking |
| VCN CIDR | `vcn_cidr` | CIDR | Yes | empty | Valid; no overlap | Target VCN range | OCI networking |
| SDDC CIDR | `sddc_cidr` | CIDR | Yes | empty | Supported prefix; no overlap | Reserved OCVS management range | OCVS networking |
| Workload CIDRs | `workload_cidrs` | repeatable CIDR | Yes | empty | Valid, unique, non-overlapping | NSX workload segments | OCVS networking |
| VLAN/subnet plan | `network_segments` | repeatable structured rows | Yes | empty | Name, purpose, CIDR; no overlaps | Management, vMotion, vSAN, HCX, uplinks, etc. | Network tables |
| DNS servers/domains | `dns_configuration` | structured | Yes | empty | Valid IPs/domain names | DNS resolvers and search domains | Networking |
| NTP servers | `ntp_servers` | repeatable IP/FQDN | Yes | empty | Valid IP/FQDN | Time sources | Networking |
| Connectivity type | `connectivity_type` | select | Yes | To be confirmed | FastConnect / IPSec / Both | Target connectivity pattern | Networking conditional modules |
| FastConnect details | `fastconnect_details` | structured | Conditional | empty | Provider, bandwidth, redundancy, BGP | Complete when FastConnect is selected | FastConnect section |
| VPN details | `vpn_details` | structured | Conditional | empty | CPE, tunnels, BGP/static routing | Complete when IPSec is selected | VPN section |
| Bandwidth requirement | `migration_bandwidth_mbps` | number | Yes | none | >0 | Required/available migration throughput | Network/migration |
| Routing/firewall notes | `routing_security_requirements` | rich text | Yes | none | Specialist approval | Route propagation, NSGs, firewall path | Networking/security |

## 4. Security and compliance

| Field label | Proposed key | Input type | Required | Default | Validation | Help text | SDD destination |
|---|---|---|---|---|---|---|---|
| Applicable regulations | `compliance_requirements` | multi-select/text | No | None declared | Explicit confirmation | GDPR, PCI DSS, internal standards, etc. | Security/compliance |
| Security requirements | `security_requirements` | repeatable text | Yes | OCI baseline proposal | Specialist/customer approval | Customer-specific security controls | Security |
| Identity federation | `identity_federation` | structured | No | To be confirmed | Provider, domains, MFA, groups | Identity integration | IAM |
| Privileged access model | `privileged_access_model` | rich text | Yes | none | Named owners/process | Administrative access and approvals | IAM/operations |
| Logging and SIEM | `logging_siem` | structured | No | To be confirmed | Product, endpoints, retention | Security telemetry integration | Monitoring/security |
| Encryption and key management | `encryption_key_management` | structured | Yes | OCI/OCVS defaults proposed | Explicit decision on Oracle/customer-managed keys | Data at rest/in transit requirements | Data security |
| Vulnerability/compliance monitoring | `security_monitoring` | rich text | No | none | Owner and tool if enabled | Scanning and posture-management design | Security |

## 5. Migration

| Field label | Proposed key | Input type | Required | Default | Validation | Help text | SDD destination |
|---|---|---|---|---|---|---|---|
| HCX available/required | `hcx_required` | tri-state | Yes | Proposed Yes | Confirm version/license/connectivity | Whether HCX is part of the migration | HCX module |
| HCX license/edition | `hcx_edition` | select/text | Conditional | To be confirmed | Compatible option | Required capabilities and ownership | HCX module |
| Migration methods | `migration_methods` | multi-select | Yes | To be confirmed | Compatible with selected workloads | Bulk, vMotion, cold, replication-assisted, etc. | Migration design |
| Migration window | `migration_window` | date/time range | Yes | none | Timezone and valid range | Approved execution window | Migration plan |
| Downtime tolerance | `downtime_tolerance` | duration/text | Yes | none | Non-negative | Maximum accepted outage | Migration requirements |
| Wave strategy | `wave_strategy` | select/rich text | Yes | Application-generated proposal | Specialist/customer approval | Grouping, sequence and constraints | Migration waves |
| Dependencies | `migration_dependencies` | repeatable relations | No | empty | Valid VM/application references | Application and infrastructure dependencies | Migration waves |
| Validation criteria | `migration_validation_criteria` | repeatable text | Yes | empty | Owner and pass/fail result | Technical and application checks | Migration/transition |
| Rollback criteria/process | `rollback_requirements` | rich text | Yes | none | Trigger, owner and time limit | Conditions and process for rollback | Migration plan |
| Data transfer constraints | `data_transfer_constraints` | rich text | No | none | Specialist validation | Seeding, bandwidth, blackout periods | Migration design |

## 6. Operations

| Field label | Proposed key | Input type | Required | Default | Validation | Help text | SDD destination |
|---|---|---|---|---|---|---|---|
| Operating model | `operating_model` | rich text | Yes | Customer-managed proposal | Named responsibilities | Day-2 ownership and processes | Operations |
| Monitoring platform | `monitoring_model` | structured | No | OCI baseline proposal | Tools, alerts, owners | Monitoring and event response | Monitoring |
| Backup in scope | `backup_enabled` | boolean | Yes | To be confirmed | Explicit decision | Whether backup architecture is included | Backup module |
| Backup product/design | `backup_architecture` | structured | Conditional | none | Product, retention, repository, RPO | Do not assume VEEAM | Backup module |
| Support ownership | `support_ownership` | RACI-like | Yes | none | Customer/Oracle/partner roles | Incident and service ownership | Operations/support |
| Patch/change management | `change_management` | rich text | Yes | none | Process and owners | ESXi/VMware/OCI change governance | Operations |
| Capacity management | `capacity_management` | rich text | No | periodic review proposal | Thresholds and owner | Growth and expansion process | Operations |
| DR enabled and targets | `dr_requirements` | structured | No | Disabled/TBC | RPO, RTO, target location if enabled | Customer recovery objectives | HA/DR |

## 7. Implementation

| Field label | Proposed key | Input type | Required | Default | Validation | Help text | SDD destination |
|---|---|---|---|---|---|---|---|
| Implementation provider | `implementation_provider` | select | Yes | Customer/partner | Customer / Oracle / Partner | Controls implementation content | Implementation |
| Include Oracle Lift section | `include_oracle_lift` | boolean | Yes | false | May be true only for an approved Oracle Lift engagement | Prevents accidental Lift commitments | Project implementation |
| Implementation scope | `implementation_scope` | repeatable deliverables | Conditional | empty | Approved task/owner/deliverable | What the delivery team will do | Workplan |
| Out of scope | `implementation_out_of_scope` | repeatable text | Conditional | empty | Explicit customer approval | Scope boundaries | Workplan |
| RACI rows | `raci_rows` | repeatable matrix | No | approved starter set | Exactly one Accountable per activity | Project responsibilities | RACI |
| Risks | `risk_rows` | repeatable structured rows | No | empty | ID, impact, mitigation, owner | Customer-specific risks only | Risks |
| Assumptions | `assumption_rows` | repeatable structured rows | No | proposed standard rows | Explicitly accepted | Delivery assumptions | Assumptions |
| Customer obligations | `customer_obligations` | repeatable text | Conditional | empty | Owner and due date | Prerequisites owned by customer | Obligations |
| Transition/handover plan | `transition_plan` | repeatable milestones | No | empty | Owner/date/acceptance | Knowledge transfer and operational handover | Transition |
| Support model after handover | `post_implementation_support` | rich text | No | none | Provider/route/severity model | Support following project closure | Transition |

## Blocking versus non-blocking

Customer-ready generation is blocked by any missing required field above, invalid CIDR/overlap, absent final saved sizing, invalid multi-cluster assignment, unresolved provider model, or unresolved sample content. Optional values may be `To be confirmed` only in a Draft when the corresponding module is explicitly retained and the unresolved field is clearly highlighted.
