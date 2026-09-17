#!/usr/bin/env python3
"""Generate an editable draft OCVS SDD from structured JSON data.

The generator deliberately operates on Word content-control tags and never on
visible text or page positions.  It is standalone and has no Flask dependency.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W15_NS = "http://schemas.microsoft.com/office/word/2012/wordml"
NS = {"w": W_NS, "w15": W15_NS}
W = f"{{{W_NS}}}"

REPEAT_CHILDREN: dict[str, tuple[str, ...]] = {
    "document_change_log": ("version_history_version", "version_history_author", "version_history_date", "version_history_comment"),
    "document_reviewers": ("reviewer_name", "reviewer_email", "reviewer_role", "reviewer_company"),
    "document_approvers": ("approver_name", "approver_email", "approver_role", "approver_company"),
    "project_team": ("project_team_name", "project_team_email", "project_team_role", "project_team_company"),
    "environments": ("environment_name", "environment_scope", "environment_location", "environment_assessment_coverage"),
    "source_cluster_rows": ("source_cluster_name", "source_cluster_vm_count", "source_cluster_vcpu", "source_cluster_ram_gb", "source_cluster_storage_tb", "source_cluster_powered_on", "source_cluster_powered_off"),
    "target_ocvs_cluster_rows": ("target_cluster_name", "target_cluster_role", "assigned_source_clusters", "target_cluster_vm_count", "target_cluster_shape", "target_cluster_workload_nodes", "target_cluster_spare_nodes", "target_cluster_total_nodes", "target_cluster_sizing_driver", "target_cluster_storage_tb", "target_cluster_storage_architecture", "target_cluster_monthly_cost"),
    "bom_rows": ("bom_part_number", "bom_product_name", "bom_metric", "bom_quantity", "bom_commitment_term", "bom_storage_component", "bom_pricing_availability"),
    "raci_rows": ("raci_activity", "raci_responsible", "raci_accountable", "raci_consulted", "raci_informed"),
    "risk_rows": ("risk_id", "risk_description", "risk_impact", "risk_mitigation", "risk_owner"),
    "assumption_rows": ("assumption_statement", "assumption_owner", "assumption_status"),
    "customer_obligations": ("obligation_statement", "obligation_owner", "obligation_due_date"),
    "implementation_scope": ("scope_activity", "scope_deliverable", "scope_owner"),
    "transition_milestones": ("transition_milestone", "transition_owner", "transition_date", "transition_acceptance"),
    "network_segments": ("network_segment_name", "network_segment_cidr", "network_segment_purpose"),
}

CONDITIONALS = {
    "section_single_cluster", "section_multi_cluster", "section_vsan", "section_block_volume",
    "section_denseio", "section_standard_optimized", "section_fastconnect", "section_ipsec_vpn",
    "section_hcx", "section_ha", "section_dr", "section_backup", "section_security_compliance",
    "section_customer_managed", "section_partner_managed", "section_oracle_managed",
    "section_oracle_lift", "section_pricing", "section_raci", "section_risks", "section_transition",
}

FORBIDDEN = (
    "a company making everything", "example@example.com", "insert region", "dc location",
    "env name", "name surname", "xxxxx", "<customer>", "insert name", "tbd",
    "10.0.0.0/16", "bm.denseio2.52", "bm.standard3.48",
)


class GenerationError(ValueError):
    """Raised when data is unsafe or inconsistent for document generation."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_sha256(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def compact_number(value: Any, decimals: int = 1) -> str:
    if value is None or value == "":
        return "Not provided"
    number = float(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.{decimals}f}".rstrip("0").rstrip(".")


def percent(value: Any) -> str:
    return f"{compact_number(value)}%"


def money(value: Any, currency: str, available: bool) -> str:
    if not available or value is None:
        return "Not available"
    return f"{currency} {float(value):,.2f}"


def customer_date(value: Any) -> str:
    if not value:
        return "Not provided"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%B %-d, %Y")
    except (ValueError, TypeError):
        return str(value)


def require(obj: dict[str, Any], path: str, errors: list[str]) -> Any:
    current: Any = obj
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current or current[part] in (None, "", []):
            errors.append(f"Missing mandatory field: {path}")
            return None
        current = current[part]
    return current


def validate_input(data: dict[str, Any]) -> list[str]:
    """Return all input errors; never silently repair topology or commercial data."""
    errors: list[str] = []
    mandatory = (
        "document.customer_name", "document.customer_legal_name", "document.project_name",
        "document.assessment_name", "document.assessment_date", "document.rvtools_file_name",
        "document.document_author", "document.document_author_email",
        "business.customer_business_context", "business.business_drivers",
        "business.solution_scope_summary", "business.business_requirements",
        "business.technical_requirements", "business.success_criteria",
        "scope.selected_vm_count", "scope.selected_vcpu", "scope.selected_ram_gb",
        "scope.selected_storage_tb", "sizing.business_scenario", "sizing.topology",
        "sizing.sddc_count", "sizing.target_cluster_count", "sizing.selected_shape",
        "sizing.sizing_driver", "sizing.total_nodes", "sizing.storage_architecture",
        "sizing.workload_capacity_storage_tb", "commercial.currency_code",
        "commercial.pricing_available", "commercial.commitment_term",
        "operations.implementation_provider",
    )
    for path in mandatory:
        require(data, path, errors)

    sizing = data.get("sizing", {})
    topology = sizing.get("topology")
    if sizing.get("business_scenario") != "ocvs":
        errors.append("sizing.business_scenario must be 'ocvs'")
    if topology not in {"single", "multi"}:
        errors.append("sizing.topology must be 'single' or 'multi'")
    clusters = data.get("target_clusters") or []
    if not 1 <= len(clusters) <= 6:
        errors.append("target_clusters must contain between one and six clusters")
    if sizing.get("target_cluster_count") != len(clusters):
        errors.append("sizing.target_cluster_count must equal the number of target_clusters")
    if topology == "single" and len(clusters) != 1:
        errors.append("Single-cluster topology requires exactly one target cluster")
    management = [c for c in clusters if c.get("role") == "unified_management"]
    if topology == "multi" and len(management) != 1:
        errors.append("Multi-cluster topology requires exactly one unified management cluster")

    names: set[str] = set()
    for index, cluster in enumerate(clusters):
        label = f"target_clusters[{index}]"
        for key in ("name", "role", "assigned_source_clusters", "assigned_vm_count", "selected_profile", "selected_shape", "sizing_driver", "workload_nodes", "spare_nodes", "total_nodes", "storage_requirement_tb", "storage_architecture"):
            if key not in cluster or cluster[key] in (None, "", []):
                errors.append(f"Missing mandatory field: {label}.{key}")
        name = str(cluster.get("name", ""))
        if name in names:
            errors.append(f"Duplicate target cluster name: {name}")
        names.add(name)
        workload = int(cluster.get("workload_nodes") or 0)
        spare = int(cluster.get("spare_nodes") or 0)
        total = int(cluster.get("total_nodes") or 0)
        if total != workload + spare:
            errors.append(f"{label}.total_nodes must equal workload_nodes + spare_nodes")
        shape = str(cluster.get("selected_shape", "")).lower()
        role = cluster.get("role")
        minimum = 3 if role == "unified_management" else (3 if "dense" in shape else 1 if "gpu" in shape else 2)
        if total < minimum:
            errors.append(f"{label}.total_nodes must be at least {minimum} for its role and shape")

    source_rows = data.get("scope", {}).get("source_clusters") or []
    if source_rows:
        checks = {
            "vm_count": data.get("scope", {}).get("selected_vm_count"),
            "vcpu": data.get("scope", {}).get("selected_vcpu"),
            "ram_gb": data.get("scope", {}).get("selected_ram_gb"),
            "storage_tb": data.get("scope", {}).get("selected_storage_tb"),
        }
        for key, expected in checks.items():
            actual = sum(float(row.get(key) or 0) for row in source_rows)
            if expected is not None and abs(actual - float(expected)) > (0.11 if key == "storage_tb" else 0.01):
                errors.append(f"scope.source_clusters {key} total ({actual:g}) does not reconcile with scope ({expected})")

    commercial = data.get("commercial", {})
    pricing = bool(commercial.get("pricing_available"))
    if pricing and (commercial.get("monthly_cost") is None or commercial.get("annual_cost") is None):
        errors.append("Available pricing requires commercial.monthly_cost and annual_cost")
    if not pricing and any(commercial.get(k) is not None for k in ("monthly_cost", "annual_cost")):
        errors.append("Pricing amounts must be absent when commercial.pricing_available is false")

    provider = data.get("operations", {}).get("implementation_provider")
    if provider not in {"customer", "partner", "oracle"}:
        errors.append("operations.implementation_provider must be customer, partner, or oracle")
    flags = data.get("section_flags", {})
    if flags.get("include_oracle_lift") and provider != "oracle":
        errors.append("Oracle Lift can only be enabled for an Oracle implementation provider")

    raw = json.dumps(data, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN:
        if forbidden in raw:
            errors.append(f"Forbidden sample or placeholder value in input: {forbidden}")
    return errors


def section_plan(data: dict[str, Any]) -> dict[str, bool]:
    sizing = data["sizing"]
    flags = data.get("section_flags", {})
    network = data.get("network", {})
    security = data.get("security", {})
    operations = data.get("operations", {})
    topology = sizing["topology"]
    architectures = {str(c.get("storage_architecture", "")).lower() for c in data["target_clusters"]}
    shapes = {str(c.get("selected_shape", "")).lower() for c in data["target_clusters"]}
    has_vsan = any("vsan" in item for item in architectures)
    has_block = any("block" in item for item in architectures)
    has_dense = any("dense" in item for item in shapes)
    connectivity = {str(x).lower() for x in network.get("connectivity", [])}
    provider = operations["implementation_provider"]
    return {
        "section_single_cluster": topology == "single",
        "section_multi_cluster": topology == "multi",
        "section_vsan": has_vsan,
        "section_block_volume": has_block,
        "section_denseio": has_dense,
        "section_standard_optimized": not has_dense or any("standard" in x or "optimized" in x for x in shapes),
        "section_fastconnect": "fastconnect" in connectivity,
        "section_ipsec_vpn": "ipsec_vpn" in connectivity,
        "section_hcx": bool(network.get("hcx", {}).get("enabled")),
        "section_ha": bool(operations.get("ha", {}).get("enabled")),
        "section_dr": bool(operations.get("disaster_recovery", {}).get("enabled")),
        "section_backup": bool(operations.get("backup", {}).get("enabled")),
        "section_security_compliance": bool(security.get("include_section", True)),
        "section_customer_managed": provider == "customer",
        "section_partner_managed": provider == "partner",
        "section_oracle_managed": provider == "oracle",
        "section_oracle_lift": provider == "oracle" and bool(flags.get("include_oracle_lift")),
        "section_pricing": bool(flags.get("include_pricing")),
        "section_raci": bool(flags.get("include_raci")),
        "section_risks": bool(flags.get("include_risks")),
        "section_transition": bool(flags.get("include_transition")),
    }


def scalar_values(data: dict[str, Any]) -> dict[str, str]:
    d, b, s, z = data["document"], data["business"], data["scope"], data["sizing"]
    n, sec, ops, com = data.get("network", {}), data.get("security", {}), data.get("operations", {}), data["commercial"]
    gen_date = d.get("generation_date") or date.today().isoformat()
    values: dict[str, Any] = {
        "customer_name": d["customer_name"], "customer_legal_name": d["customer_legal_name"],
        "project_name": d["project_name"], "document_version": d.get("document_version", "0.1"),
        "generation_date": customer_date(gen_date), "copyright_year": d.get("copyright_year", date.today().year),
        "document_author": d["document_author"], "document_author_email": d["document_author_email"],
        "document_version_comment": d.get("version_comment", "Initial draft generated for specialist review"),
        "customer_business_context": b["customer_business_context"], "business_drivers": b["business_drivers"],
        "solution_scope_summary": b["solution_scope_summary"], "business_requirements": b["business_requirements"],
        "technical_requirements": b["technical_requirements"], "success_criteria": b["success_criteria"],
        "rvtools_file_name": Path(d["rvtools_file_name"]).name, "assessment_name": d["assessment_name"],
        "assessment_date": customer_date(d["assessment_date"]), "selected_vm_count": compact_number(s["selected_vm_count"]),
        "powered_on_vm_count": compact_number(s.get("powered_on_vm_count", 0)), "powered_off_vm_count": compact_number(s.get("powered_off_vm_count", 0)),
        "selected_vcpu": compact_number(s["selected_vcpu"]), "selected_ram_gb": compact_number(s["selected_ram_gb"]),
        "selected_storage_tb": compact_number(s["selected_storage_tb"]), "operating_system_summary": s.get("operating_system_summary", "Not provided"),
        "source_datacenters": ", ".join(s.get("source_datacenters", [])) or "Not provided",
        "source_vcenters": ", ".join(s.get("source_vcenters", [])) or "Not provided",
        "business_scenario": "Move to OCVS", "ocvs_topology": "Multi-cluster" if z["topology"] == "multi" else "Single-cluster",
        "sddc_count": compact_number(z["sddc_count"]), "target_cluster_count": compact_number(z["target_cluster_count"]),
        "total_ocvs_nodes": compact_number(z["total_nodes"]), "selected_shape": z["selected_shape"],
        "sizing_driver": z["sizing_driver"], "workload_nodes": compact_number(z.get("workload_nodes", z["total_nodes"])),
        "spare_nodes": compact_number(z.get("spare_nodes", 0)), "storage_architecture": z["storage_architecture"],
        "workload_capacity_storage_tb": compact_number(z["workload_capacity_storage_tb"]),
        "vcpu_per_ocpu": compact_number(z.get("vcpu_per_ocpu", 4)), "cpu_headroom_pct": percent(z.get("cpu_headroom_pct", 20)),
        "ram_headroom_pct": percent(z.get("ram_headroom_pct", 20)), "storage_headroom_pct": percent(z.get("storage_headroom_pct", 25)),
        "dense_vsan_usable_pct": percent(z.get("dense_vsan_usable_pct", 50)), "standard_storage_vpu": f"{compact_number(z.get('standard_storage_vpu', 10))} VPU/GB",
        "oci_region": n.get("oci_region", "Not provided"), "tenancy_name_or_ocid": n.get("tenancy_name_or_ocid", "Not provided"),
        "compartment_name_or_ocid": n.get("compartment_name_or_ocid", "Not provided"), "vcn_cidr": n.get("vcn_cidr", "Not provided"),
        "sddc_cidr": n.get("sddc_cidr", "Not provided"), "workload_cidrs": ", ".join(n.get("workload_cidrs", [])) or "Not provided",
        "connectivity_type": ", ".join(n.get("connectivity", [])) or "Not provided",
        "security_requirements": sec.get("requirements", "Not provided"), "compliance_requirements": b.get("compliance_requirements", "Not provided"),
        "identity_federation": sec.get("iam_model", "Not provided"), "logging_siem": sec.get("logging", "Not provided"),
        "encryption_key_management": sec.get("encryption", "Not provided"), "hcx_required": "Yes" if n.get("hcx", {}).get("enabled") else "No",
        "migration_method": ops.get("migration_method", "Not provided"), "migration_window": ops.get("migration_window", "Not provided"),
        "downtime_tolerance": ops.get("downtime_tolerance", "Not provided"), "validation_and_rollback": ops.get("validation_and_rollback", "Not provided"),
        "ha_requirements": ops.get("ha", {}).get("description", "Not applicable"), "dr_requirements": ops.get("disaster_recovery", {}).get("description", "Not applicable"),
        "backup_architecture": ops.get("backup", {}).get("description", "Not applicable"), "operating_model": ops.get("operating_model", "Not provided"),
        "monitoring_model": ops.get("monitoring", "Not provided"), "implementation_provider": ops["implementation_provider"].title(),
        "transition_plan": ops.get("transition_plan", "Not provided"), "currency_code": com["currency_code"],
        "iaas_discount_pct": percent(com.get("iaas_discount_pct", 0)), "commitment_term": com["commitment_term"],
        "monthly_cost": money(com.get("monthly_cost"), com["currency_code"], com["pricing_available"]),
        "annual_cost": money(com.get("annual_cost"), com["currency_code"], com["pricing_available"]),
        "pricing_availability": "Available" if com["pricing_available"] else "Not available",
        "draft_watermark": "DRAFT — NOT FOR CUSTOMER DELIVERY" if d.get("draft_status", True) else "",
        "cover_customer_name": d["customer_name"], "cover_document_version": d.get("document_version", "0.1"),
        "cover_generation_date": customer_date(gen_date), "copyright_year_cover": d.get("copyright_year", date.today().year),
        "target_region_summary": n.get("oci_region", "Not provided"),
        "single_cluster_shape": z["selected_shape"], "single_cluster_workload_nodes": compact_number(z.get("workload_nodes", z["total_nodes"])),
        "single_cluster_spare_nodes": compact_number(z.get("spare_nodes", 0)), "single_cluster_sizing_driver": z["sizing_driver"],
        "single_cluster_storage_architecture": z["storage_architecture"], "target_sizing_summary_narrative": z.get("summary_narrative", "Sizing is based on the selected assessment scope and saved capacity policy."),
        "dense_shape": z["selected_shape"], "dense_total_nodes": compact_number(z["total_nodes"]),
        "dense_storage_requirement_tb": compact_number(z["workload_capacity_storage_tb"]), "dense_storage_headroom_pct": percent(z.get("storage_headroom_pct", 25)),
        "dense_vsan_usable_pct_detail": percent(z.get("dense_vsan_usable_pct", 50)), "block_shape": z["selected_shape"],
        "block_total_nodes": compact_number(z["total_nodes"]), "block_storage_requirement_tb": compact_number(z["workload_capacity_storage_tb"]),
        "block_storage_headroom_pct": percent(z.get("storage_headroom_pct", 25)), "block_standard_storage_vpu_detail": f"{compact_number(z.get('standard_storage_vpu', 10))} VPU/GB",
    }
    return {key: str(value) for key, value in values.items()}


def repeat_values(data: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    d, s, delivery, com = data["document"], data["scope"], data.get("delivery", {}), data["commercial"]
    clusters = []
    for c in data["target_clusters"]:
        clusters.append({
            "target_cluster_name": c["name"], "target_cluster_role": "Unified Management Cluster" if c["role"] == "unified_management" else "Workload Cluster",
            "assigned_source_clusters": ", ".join(c["assigned_source_clusters"]), "target_cluster_vm_count": compact_number(c["assigned_vm_count"]),
            "target_cluster_shape": c["selected_shape"], "target_cluster_workload_nodes": compact_number(c["workload_nodes"]),
            "target_cluster_spare_nodes": compact_number(c["spare_nodes"]), "target_cluster_total_nodes": compact_number(c["total_nodes"]),
            "target_cluster_sizing_driver": c["sizing_driver"], "target_cluster_storage_tb": compact_number(c["storage_requirement_tb"]),
            "target_cluster_storage_architecture": c["storage_architecture"],
            "target_cluster_monthly_cost": money(c.get("monthly_cost"), com["currency_code"], com["pricing_available"]),
        })
    source = [{
        "source_cluster_name": r["name"], "source_cluster_vm_count": compact_number(r["vm_count"]),
        "source_cluster_vcpu": compact_number(r["vcpu"]), "source_cluster_ram_gb": compact_number(r["ram_gb"]),
        "source_cluster_storage_tb": compact_number(r["storage_tb"]), "source_cluster_powered_on": compact_number(r["powered_on"]),
        "source_cluster_powered_off": compact_number(r["powered_off"]),
    } for r in s.get("source_clusters", [])]
    repeat = {
        "document_change_log": delivery.get("document_history", [{"version": d.get("document_version", "0.1"), "author": d["document_author"], "date": d.get("generation_date", date.today().isoformat()), "comment": d.get("version_comment", "Initial draft")}]),
        "document_reviewers": delivery.get("reviewers", []), "document_approvers": delivery.get("approvers", []),
        "project_team": delivery.get("project_team", []), "environments": delivery.get("environments", []),
        "source_cluster_rows": source, "target_ocvs_cluster_rows": clusters, "bom_rows": com.get("bom_rows", []),
        "raci_rows": delivery.get("raci", []), "risk_rows": delivery.get("risks", []), "assumption_rows": delivery.get("assumptions", []),
        "customer_obligations": delivery.get("customer_obligations", []), "implementation_scope": delivery.get("implementation_scope", []),
        "transition_milestones": delivery.get("transition_milestones", []), "network_segments": data.get("network", {}).get("segments", []),
    }
    aliases = {
        "document_change_log": {"version": "version_history_version", "author": "version_history_author", "date": "version_history_date", "comment": "version_history_comment"},
        "document_reviewers": {"name": "reviewer_name", "email": "reviewer_email", "role": "reviewer_role", "company": "reviewer_company"},
        "document_approvers": {"name": "approver_name", "email": "approver_email", "role": "approver_role", "company": "approver_company"},
        "project_team": {"name": "project_team_name", "email": "project_team_email", "role": "project_team_role", "company": "project_team_company"},
        "environments": {"name": "environment_name", "scope": "environment_scope", "location": "environment_location", "assessment_coverage": "environment_assessment_coverage"},
        "bom_rows": {"part_number": "bom_part_number", "product_name": "bom_product_name", "metric": "bom_metric", "quantity": "bom_quantity", "commitment_term": "bom_commitment_term", "storage_component": "bom_storage_component", "pricing_availability": "bom_pricing_availability"},
        "raci_rows": {"activity": "raci_activity", "responsible": "raci_responsible", "accountable": "raci_accountable", "consulted": "raci_consulted", "informed": "raci_informed"},
        "risk_rows": {"id": "risk_id", "description": "risk_description", "impact": "risk_impact", "mitigation": "risk_mitigation", "owner": "risk_owner"},
        "assumption_rows": {"statement": "assumption_statement", "owner": "assumption_owner", "status": "assumption_status"},
        "customer_obligations": {"statement": "obligation_statement", "owner": "obligation_owner", "due_date": "obligation_due_date"},
        "implementation_scope": {"activity": "scope_activity", "deliverable": "scope_deliverable", "owner": "scope_owner"},
        "transition_milestones": {"milestone": "transition_milestone", "owner": "transition_owner", "date": "transition_date", "acceptance": "transition_acceptance"},
        "network_segments": {"name": "network_segment_name", "cidr": "network_segment_cidr", "purpose": "network_segment_purpose"},
    }
    normalized: dict[str, list[dict[str, str]]] = {}
    for group, rows in repeat.items():
        mapping = aliases.get(group, {})
        normalized[group] = [{mapping.get(k, k): str(v) for k, v in row.items()} for row in rows]
    return normalized


def tag_of(sdt: etree._Element) -> str | None:
    values = sdt.xpath("./w:sdtPr/w:tag/@w:val", namespaces=NS)
    return values[0] if values else None


def set_control_text(sdt: etree._Element, value: str) -> None:
    content = sdt.find(f"{W}sdtContent")
    if content is None:
        return
    texts = content.xpath(".//w:t", namespaces=NS)
    if texts:
        texts[0].text = value
        texts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        for node in texts[1:]:
            node.text = ""
        return
    paragraph = content.find(f".//{W}p")
    if paragraph is None:
        paragraph = etree.SubElement(content, f"{W}p")
    run = etree.SubElement(paragraph, f"{W}r")
    text = etree.SubElement(run, f"{W}t")
    text.text = value


def remove_node(node: etree._Element) -> None:
    parent = node.getparent()
    if parent is not None:
        parent.remove(node)


def unwrap(node: etree._Element) -> None:
    parent = node.getparent()
    content = node.find(f"{W}sdtContent")
    if parent is None or content is None:
        return
    index = parent.index(node)
    for child in list(content):
        content.remove(child)
        parent.insert(index, child)
        index += 1
    parent.remove(node)


def unhide(node: etree._Element) -> None:
    for hidden in node.xpath(".//w:vanish|.//w:hidden", namespaces=NS):
        remove_node(hidden)


def populate_xml(root: etree._Element, scalars: dict[str, str], repeats: dict[str, list[dict[str, str]]], sections: dict[str, bool]) -> tuple[list[str], dict[str, int]]:
    populated: list[str] = []
    counts: dict[str, int] = {}
    for wrapper_tag, rows in repeats.items():
        wrappers = root.xpath(f'.//w:sdt[w:sdtPr/w:tag[@w:val="{wrapper_tag}"]]', namespaces=NS)
        if not wrappers:
            continue
        wrapper = wrappers[0]
        items = wrapper.xpath(f'.//w:sdt[w:sdtPr/w:tag[@w:val="{wrapper_tag}_item"]]', namespaces=NS)
        if not items:
            continue
        seed = items[0]
        parent = seed.getparent()
        index = parent.index(seed)
        for old in items:
            parent.remove(old)
        for row in rows:
            clone = copy.deepcopy(seed)
            for child in clone.xpath('.//w:sdt', namespaces=NS):
                child_tag = tag_of(child)
                if child_tag in row:
                    set_control_text(child, row[child_tag])
                    populated.append(child_tag)
            parent.insert(index, clone)
            index += 1
        counts[wrapper_tag] = len(rows)
        if not rows:
            remove_node(wrapper)

    for sdt in root.xpath('.//w:sdt', namespaces=NS):
        tag = tag_of(sdt)
        if tag in scalars:
            set_control_text(sdt, scalars[tag])
            populated.append(tag)

    conditional_nodes = [s for s in root.xpath('.//w:sdt', namespaces=NS) if tag_of(s) in CONDITIONALS]
    conditional_nodes.sort(key=lambda n: len(n.xpath('ancestor::*')), reverse=True)
    for node in conditional_nodes:
        tag = tag_of(node)
        if node.getparent() is None:
            continue
        if sections.get(tag, False):
            unhide(node)
            unwrap(node)
        else:
            remove_node(node)
    return populated, counts


def ensure_update_fields(settings_path: Path) -> None:
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.parse(str(settings_path), parser).getroot()
    nodes = root.xpath('./w:updateFields', namespaces=NS)
    node = nodes[0] if nodes else etree.SubElement(root, f"{W}updateFields")
    node.set(f"{W}val", "true")
    settings_path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))


def generate(template: Path, data_path: Path, output: Path, schema_path: Path | None = None) -> dict[str, Any]:
    if not template.is_file() or not zipfile.is_zipfile(template):
        raise GenerationError(f"Template is not a valid DOCX: {template}")
    if output.resolve() == template.resolve():
        raise GenerationError("Output must not overwrite the master template")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    errors = validate_input(data)
    if errors:
        raise GenerationError("Input validation failed:\n- " + "\n- ".join(errors))

    scalars, repeats, sections = scalar_values(data), repeat_values(data), section_plan(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    template_hash = sha256(template)
    with tempfile.TemporaryDirectory(prefix="ocvs-sdd-") as temp:
        expanded = Path(temp)
        with zipfile.ZipFile(template) as archive:
            archive.extractall(expanded)
        populated: list[str] = []
        repeated_counts: dict[str, int] = {}
        parser = etree.XMLParser(resolve_entities=False, remove_blank_text=False)
        for xml_path in sorted((expanded / "word").rglob("*.xml")):
            try:
                root = etree.parse(str(xml_path), parser).getroot()
            except etree.XMLSyntaxError:
                continue
            done, counts = populate_xml(root, scalars, repeats, sections)
            populated.extend(done)
            repeated_counts.update(counts)
            xml_path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))
        ensure_update_fields(expanded / "word" / "settings.xml")
        temp_output = expanded / "generated.docx"
        with zipfile.ZipFile(temp_output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(expanded.rglob("*")):
                if path.is_file() and path != temp_output:
                    archive.write(path, path.relative_to(expanded))
        shutil.copy2(temp_output, output)

    omitted = sorted(k for k, value in scalars.items() if value in {"Not provided", "Not applicable", "Not available"})
    report = {
        "generation_status": "success", "source_template": str(template), "output_document": str(output),
        "source_template_checksum": template_hash, "generated_document_checksum": sha256(output),
        "input_data_checksum": json_sha256(data), "schema": str(schema_path) if schema_path else None,
        "populated_controls": sorted(set(populated)), "missing_mandatory_fields": [],
        "omitted_optional_fields": omitted, "enabled_conditional_sections": sorted(k for k, v in sections.items() if v),
        "excluded_conditional_sections": sorted(k for k, v in sections.items() if not v),
        "repeated_row_counts": repeated_counts,
        "warnings_requiring_specialist_review": data.get("specialist_review_warnings", ["Draft output requires specialist validation before customer delivery."]),
    }
    report_path = output.with_suffix(".validation.json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if sha256(template) != template_hash:
        raise GenerationError("Master template checksum changed during generation")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--schema", type=Path, default=Path("schemas/ocvs_sdd_generation.schema.json"))
    args = parser.parse_args()
    try:
        report = generate(args.template, args.data, args.output, args.schema)
    except (GenerationError, json.JSONDecodeError, OSError) as exc:
        print(f"OCVS SDD generation FAILED: {exc}", file=sys.stderr)
        return 2
    print(f"Generated: {args.output}")
    print(f"Validation report: {args.output.with_suffix('.validation.json')}")
    print(f"SHA-256: {report['generated_document_checksum']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
