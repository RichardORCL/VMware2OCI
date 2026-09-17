#!/usr/bin/env python3
"""Generate the Phase-1 OCVS SDD template changelog from the final DOCX."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from lxml import etree

from build_ocvs_sdd_template import CHILD_TAGS, CONDITIONAL_TAGS, REPEAT_TAGS, SCALAR_TAGS


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W15_NS = "http://schemas.microsoft.com/office/word/2012/wordml"
NS = {"w": W_NS, "w15": W15_NS}

REQUIRED = {
    "customer_name", "customer_legal_name", "project_name", "document_version",
    "generation_date", "copyright_year", "document_author", "document_change_log",
    "customer_business_context", "business_drivers", "solution_scope_summary",
    "business_requirements", "technical_requirements", "success_criteria",
    "rvtools_file_name", "assessment_name", "assessment_date", "selected_vm_count",
    "powered_on_vm_count", "powered_off_vm_count", "selected_vcpu", "selected_ram_gb",
    "selected_storage_tb", "business_scenario", "ocvs_topology", "sddc_count",
    "target_cluster_count", "total_ocvs_nodes", "sizing_driver", "workload_nodes",
    "spare_nodes", "storage_architecture", "workload_capacity_storage_tb",
    "vcpu_per_ocpu", "cpu_headroom_pct", "ram_headroom_pct", "storage_headroom_pct",
    "oci_region", "tenancy_name_or_ocid", "compartment_name_or_ocid", "vcn_cidr",
    "sddc_cidr", "connectivity_type", "security_requirements", "migration_method",
    "migration_window", "downtime_tolerance", "validation_and_rollback",
    "operating_model", "implementation_provider", "currency_code", "commitment_term",
    "pricing_availability", "source_cluster_rows", "target_ocvs_cluster_rows", "bom_rows",
}


def word_section(tag: str) -> str:
    if tag.startswith("cover_") or tag in {"customer_name", "customer_legal_name", "project_name", "document_version", "generation_date", "copyright_year"}:
        return "Cover / document metadata"
    if tag.startswith(("version_history_", "reviewer_", "approver_", "project_team_")) or tag in {"document_change_log", "document_reviewers", "document_approvers", "project_team", "document_author", "document_author_email", "document_version_comment"}:
        return "Document Control"
    if tag.startswith("section_"):
        return "Conditional module"
    if tag.startswith("source_cluster_") or tag in {"source_cluster_rows", "selected_vm_count", "powered_on_vm_count", "powered_off_vm_count", "selected_vcpu", "selected_ram_gb", "selected_storage_tb", "operating_system_summary", "source_datacenters", "source_vcenters", "rvtools_file_name", "assessment_name", "assessment_date"}:
        return "Current State Architecture"
    if tag.startswith("target_cluster_") or tag in {"target_ocvs_cluster_rows", "ocvs_topology", "sddc_count", "target_cluster_count", "total_ocvs_nodes", "selected_shape", "sizing_driver", "workload_nodes", "spare_nodes", "storage_architecture", "workload_capacity_storage_tb"}:
        return "Target OCVS Architecture Sizing"
    if tag.startswith("bom_") or tag == "bom_rows":
        return "Bill of Materials"
    if tag in {"currency_code", "iaas_discount_pct", "commitment_term", "monthly_cost", "annual_cost", "pricing_availability"}:
        return "Commercial Summary"
    if tag.startswith(("network_segment_",)) or tag in {"network_segments", "oci_region", "tenancy_name_or_ocid", "compartment_name_or_ocid", "vcn_cidr", "sddc_cidr", "workload_cidrs", "connectivity_type", "target_region_summary"}:
        return "Networking / OCI target"
    if tag in {"vcpu_per_ocpu", "cpu_headroom_pct", "ram_headroom_pct", "storage_headroom_pct", "dense_vsan_usable_pct", "standard_storage_vpu"} or tag.startswith(("dense_", "block_", "single_cluster_")):
        return "Assumptions and sizing"
    if tag.startswith(("raci_", "risk_", "assumption_", "obligation_", "scope_", "transition_")) or tag in {"raci_rows", "risk_rows", "assumption_rows", "customer_obligations", "implementation_scope", "transition_milestones"}:
        return "Implementation governance"
    if tag in {"security_requirements", "compliance_requirements", "identity_federation", "logging_siem", "encryption_key_management"}:
        return "Security and compliance"
    if tag in {"hcx_required", "migration_method", "migration_window", "downtime_tolerance", "validation_and_rollback"}:
        return "OCVS Migration"
    if tag in {"ha_requirements", "dr_requirements", "backup_architecture", "operating_model", "monitoring_model"}:
        return "HA / DR / backup / operations"
    if tag in {"implementation_provider", "transition_plan"}:
        return "Implementation Approach"
    if tag in {"customer_business_context", "business_drivers", "solution_scope_summary", "business_requirements", "technical_requirements", "success_criteria"}:
        return "Business context and requirements"
    return "Supporting template field"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-pages", type=int, default=27)
    parser.add_argument("--output-pages", type=int, required=True)
    args = parser.parse_args()

    controls: list[dict[str, str]] = []
    with zipfile.ZipFile(args.template) as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            try:
                root = etree.fromstring(archive.read(name))
            except etree.XMLSyntaxError:
                continue
            for sdt in root.xpath('.//w:sdt', namespaces=NS):
                tag = sdt.xpath('./w:sdtPr/w:tag/@w:val', namespaces=NS)
                if not tag:
                    continue
                tag = tag[0]
                alias = sdt.xpath('./w:sdtPr/w:alias/@w:val', namespaces=NS)
                if tag in REPEAT_TAGS:
                    kind, repeated = "Repeating section", "Yes"
                elif tag.endswith("_item"):
                    kind, repeated = "Repeating section item", "Yes"
                elif tag in CONDITIONAL_TAGS:
                    kind, repeated = "Conditional rich-text section", "No"
                elif tag in CHILD_TAGS:
                    kind, repeated = "Editable text/rich text", "Yes when inside repeated row"
                else:
                    kind, repeated = "Editable text/rich text", "No"
                controls.append({
                    "title": alias[0] if alias else "",
                    "tag": tag,
                    "section": word_section(tag),
                    "type": kind,
                    "repeated": repeated,
                    "required": "Required" if tag in REQUIRED else "Optional / conditional",
                })

    controls.sort(key=lambda row: (row["section"], row["tag"]))
    lines = [
        "# OCVS SDD automation-ready template changelog",
        "",
        "## Files and scope",
        "",
        "- Source: `OCVS_SD_Template_v1.docx` (preserved unchanged).",
        "- Output: `document_templates/OCVS_SDD_template_automatable.docx`.",
        f"- Rendered pages before: {args.source_pages}.",
        f"- Rendered pages after: {args.output_pages}.",
        "- Scope: Phase 1 template cleanup and preparation only; no production generator or Flask integration.",
        "",
        "## Removed or neutralized sample content",
        "",
        "- Removed the sample customer name, sample people, e-mail addresses and project dates.",
        "- Removed Frankfurt and other engagement-specific location references.",
        "- Removed `INSERT REGION`, data-centre placeholders, sample programme names and sample company facts.",
        "- Replaced sample inventory, sizing, shape, node-count, CIDR, BOM SKU, quantity and pricing values with native Word controls or repeatable rows.",
        "- Replaced fixed sizing-outcome assertions with `target_sizing_summary_narrative` for future approved prose.",
        "- Removed conflicting 2022/2024 copyright dates; the footer and cover now use dynamic year controls.",
        "- No visible `<CUSTOMER>`, `INSERT NAME`, `TBD`, `XXXX` or example CIDR was introduced.",
        "",
        "## Corrected document behaviour",
        "",
        "- Standardized the document metadata title and set the neutral document version default to `0.1`.",
        "- Added `DRAFT — NOT FOR CUSTOMER DELIVERY` as an editable tagged document element.",
        "- Preserved the approved Oracle confidentiality wording and enabled dynamic copyright year.",
        "- Set Word fields to update on open so TOC and page fields can refresh after conditional generation.",
        "- Preserved the original page size, margins, heading styles, colours, diagrams and overall hierarchy.",
        "- Oracle Lift and delivery-provider detail modules are retained but hidden by default until explicitly enabled.",
        "",
        "## Repeatable structures added",
        "",
    ]
    lines.extend(f"- `{tag}`" for tag in sorted(REPEAT_TAGS))
    lines.extend(["", "## Conditional sections added", ""])
    lines.extend(f"- `{tag}`" for tag in sorted(CONDITIONAL_TAGS))
    lines.extend([
        "",
        "## Content retained",
        "",
        "- Oracle visual identity, cover composition, headers, footers, diagrams and approved confidentiality treatment.",
        "- Standard OCVS product, landing-zone, networking, security, HA/DR, backup, operations, HCX and migration narrative, subject to the validation list below.",
        "- Annex references and OCI security/compliance material.",
        "",
        "## Specialist validation required",
        "",
        "- OCVS host, cluster and platform limit statements.",
        "- SDDC CIDR rules and the reference network diagrams.",
        "- FastConnect bandwidth/prerequisite wording and IPSec design statements.",
        "- HCX editions, entitlement, migration-method and licensing statements.",
        "- HA, DR, backup and VEEAM product-specific assertions.",
        "- Security, encryption, logging/SIEM and shared-responsibility wording and diagrams.",
        "- OCVS monitoring, operating model and support wording.",
        "- BoQ notes, BYOL statements, part numbers, commercial metrics and any pricing availability.",
        "- Oracle Lift legal, delivery, obligation, RACI, risk and acceptance wording before the module is enabled.",
        "",
        "## Oracle Lift handling",
        "",
        "- The complete Oracle-specific project implementation module is enclosed by `section_oracle_lift`.",
        "- It is retained in the DOCX for future generation but hidden in the default Draft template.",
        "- Customer-, partner- and Oracle-managed implementation detail modules are separately conditional and hidden by default.",
        "",
        "## Diagrams requiring validation",
        "",
        "- Current-state VMware architecture diagram.",
        "- OCI landing-zone and physical architecture diagrams.",
        "- Shared security responsibility matrix.",
        "- HA/DR, backup, VPN, FastConnect, SDDC network and HCX diagrams.",
        "",
        "## Mapped fields intentionally not placed as editable controls",
        "",
        "- `document_title`: retained as approved static cover text and document metadata.",
        "- `table_of_contents`: retained as a native Word TOC field rather than a content control.",
        "- `connectivity_details`: no single unambiguous location; detailed values remain within the repeatable network-segment and conditional connectivity modules.",
        "- `migration_waves`: no approved SDD table was present; defer until the future generator and migration-planning schema are approved.",
        "- `ocvs_product_overview` and `shared_security_model`: retained as curated static modules pending specialist approval rather than dynamic controls.",
        "- `include_*` flags and aggregate list identifiers are generation decisions; their document counterparts are the conditional/repeating wrapper tags listed above.",
        "",
        "## Unresolved issues",
        "",
        "- Word cannot evaluate business conditions by itself; the future generator must include/remove conditional controls and unhide the selected implementation model.",
        "- Native repeatable-section controls require Microsoft Word-compatible processing in the future generator.",
        "- TOC pagination must be refreshed by Word after the generator removes unused modules.",
        "- Customer-ready generation must remain blocked until mandatory customer, networking, security and migration inputs are approved.",
        "",
        "## Complete content-control inventory",
        "",
        "| Title | Tag | Word section | Control type | Repeated or scalar | Requirement |",
        "|---|---|---|---|---|---|",
    ])
    for row in controls:
        lines.append(
            f"| {row['title']} | `{row['tag']}` | {row['section']} | {row['type']} | {row['repeated']} | {row['required']} |"
        )
    lines.extend([
        "",
        "## Verification",
        "",
        f"- Total content controls: {len(controls)}.",
        f"- Repeatable structures: {len(REPEAT_TAGS)}.",
        f"- Conditional sections: {len(CONDITIONAL_TAGS)}.",
        "- Automated validation checks required tags, unique scalar tags, repeat nesting, conditional markers, forbidden samples, private sample CIDRs, Oracle Lift enclosure and DOCX package validity.",
        "- The final DOCX was rendered and visually inspected page by page; no overlaps, clipping, broken tables, blank pages or orphaned headings were found.",
        "- The source checksum remains unchanged and no production application file was modified.",
        "",
    ])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Created {args.output} with {len(controls)} controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
