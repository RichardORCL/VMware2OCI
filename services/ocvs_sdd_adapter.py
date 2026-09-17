"""Adapt a frozen Move-to-OCVS assessment snapshot to the Draft SDD contract."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from services.ocvs_sdd_review import normalize_review_workflow
from services.ocvs_sdd_delivery import normalize_delivery_governance
from services.ocvs_sdd_handover import normalize_acceptance_handover


NEUTRAL = "Not provided"
WIZARD_SECTIONS = (
    "customer-project", "business-requirements", "network-design",
    "security-compliance", "operations-resilience", "migration-transition",
    "review-generate",
)
WIZARD_LABELS = {
    "customer-project": "Customer & Project",
    "business-requirements": "Business Requirements",
    "network-design": "OCI Network Design",
    "security-compliance": "Security & Compliance",
    "operations-resilience": "Operations & Resilience",
    "migration-transition": "Migration & Transition",
    "review-generate": "Review & Generate",
}
REQUIRED_DOCUMENT_FIELDS = (
    "customer_legal_name", "project_name", "document_author", "document_author_email",
)
REQUIRED_BUSINESS_FIELDS = (
    "customer_business_context", "business_drivers", "solution_scope_summary",
    "business_requirements", "technical_requirements", "compliance_requirements",
    "success_criteria",
)
BUSINESS_OPTIONAL_FIELDS = ("assumptions", "known_risks", "customer_obligations", "out_of_scope")
NETWORK_TEXT_FIELDS = (
    "oci_region", "tenancy_name_or_ocid", "compartment_name_or_ocid", "vcn_name",
    "vcn_cidr", "sddc_cidr", "drg_details", "fastconnect_details",
    "ipsec_vpn_details", "hcx_details",
)
NETWORK_LIST_FIELDS = (
    "workload_cidrs", "management_cidrs", "vmotion_cidrs",
    "replication_cidrs", "hcx_cidrs", "dns_servers", "ntp_servers",
)
SECURITY_FIELDS = (
    "iam_model", "encryption_requirements", "logging_requirements",
    "siem_integration", "monitoring_requirements", "security_requirements",
    "compliance_requirements", "responsibility_notes",
)
OPERATIONS_FIELDS = (
    "operating_model", "monitoring_approach", "backup_requirements",
    "dr_requirements", "ha_requirements", "support_model", "escalation_model",
    "operational_ownership", "service_management_integration",
)
DELIVERY_TEXT_FIELDS = (
    "migration_method", "migration_tooling", "migration_wave_strategy",
    "migration_window", "downtime_tolerance", "validation_approach",
    "rollback_approach", "transition_plan_summary",
)


def _clean_text(value: Any, limit: int = 8000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _clean_multiline(value: Any, limit: int = 8000) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()[:limit]


def _clean_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _clean_list(value: Any, *, limit: int = 500) -> list[str]:
    items = value if isinstance(value, list) else str(value or "").replace(",", "\n").splitlines()
    result: list[str] = []
    for item in items:
        clean = _clean_text(item, limit)
        if clean and clean not in result:
            result.append(clean)
    return result


def _clean_rows(value: Any, fields: tuple[str, ...], *, limit: int = 100) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(value, list):
        return rows
    for raw in value[:limit]:
        if not isinstance(raw, dict):
            continue
        row = {field: _clean_multiline(raw.get(field), 2000) for field in fields}
        if any(row.values()):
            rows.append(row)
    return rows


def _clean_people(value: Any) -> list[dict[str, str]]:
    return _clean_rows(value, ("name", "email", "role", "company"), limit=50)


def normalize_sdd_configuration(value: Any) -> dict[str, Any]:
    """Normalize Phase 3 and Phase 4 configurations into one persisted structure."""
    raw = value if isinstance(value, dict) else {}
    customer = raw.get("customer_document") if isinstance(raw.get("customer_document"), dict) else {}
    business = raw.get("business") if isinstance(raw.get("business"), dict) else {}
    network = raw.get("network") if isinstance(raw.get("network"), dict) else {}
    security = raw.get("security") if isinstance(raw.get("security"), dict) else {}
    operations = raw.get("operations") if isinstance(raw.get("operations"), dict) else {}
    delivery = raw.get("delivery") if isinstance(raw.get("delivery"), dict) else {}
    flags = raw.get("section_flags") if isinstance(raw.get("section_flags"), dict) else {}
    wizard = raw.get("wizard") if isinstance(raw.get("wizard"), dict) else {}
    provider = _clean_text(operations.get("implementation_provider") or raw.get("implementation_provider"), 20).lower()
    if provider not in {"customer", "partner", "oracle"}:
        provider = "customer"
    current_step = _clean_text(wizard.get("current_step"), 80)
    if current_step not in WIZARD_SECTIONS:
        current_step = WIZARD_SECTIONS[0]
    completed_steps = [item for item in _clean_list(wizard.get("completed_steps"), limit=80) if item in WIZARD_SECTIONS]

    normalized_network = {field: _clean_multiline(network.get(field), 4000) for field in NETWORK_TEXT_FIELDS}
    for field in NETWORK_LIST_FIELDS:
        normalized_network[field] = _clean_list(network.get(field))
    normalized_network.update({
        "fastconnect_enabled": _clean_bool(network.get("fastconnect_enabled", (network.get("fastconnect") or {}).get("enabled") if isinstance(network.get("fastconnect"), dict) else False)),
        "ipsec_vpn_enabled": _clean_bool(network.get("ipsec_vpn_enabled", (network.get("ipsec_vpn") or {}).get("enabled") if isinstance(network.get("ipsec_vpn"), dict) else False)),
        "hcx_enabled": _clean_bool(network.get("hcx_enabled", (network.get("hcx") or {}).get("enabled") if isinstance(network.get("hcx"), dict) else False)),
        "segments": _clean_rows(network.get("segments"), ("name", "purpose", "cidr", "vlan", "gateway", "routing_notes", "security_notes")),
    })
    normalized_security = {field: _clean_multiline(security.get(field), 8000) for field in SECURITY_FIELDS}
    normalized_security["include_section"] = _clean_bool(security.get("include_section", flags.get("include_security", False)))
    normalized_operations = {field: _clean_multiline(operations.get(field), 8000) for field in OPERATIONS_FIELDS}
    normalized_operations["implementation_provider"] = provider
    for key in ("backup", "disaster_recovery", "ha"):
        raw_item = operations.get(key) if isinstance(operations.get(key), dict) else {}
        normalized_operations[key] = {
            "status": _clean_text(raw_item.get("status") or ("enabled" if raw_item.get("enabled") else "not_provided"), 30),
            "enabled": _clean_bool(raw_item.get("enabled")),
            "description": _clean_multiline(raw_item.get("description"), 8000),
        }
    normalized_delivery = {field: _clean_multiline(delivery.get(field), 8000) for field in DELIVERY_TEXT_FIELDS}
    normalized_delivery.update({
        "reviewers": _clean_people(delivery.get("reviewers")),
        "approvers": _clean_people(delivery.get("approvers")),
        "project_team": _clean_people(delivery.get("project_team")),
        "document_history": _clean_rows(delivery.get("document_history"), ("version", "author", "date", "comment")),
        "environments": _clean_rows(delivery.get("environments"), ("name", "scope", "location", "assessment_coverage")),
        "assumptions": _clean_rows(delivery.get("assumptions"), ("statement", "owner", "status")),
        "risks": _clean_rows(delivery.get("risks"), ("id", "description", "impact", "mitigation", "owner")),
        "raci": _clean_rows(
            delivery.get("raci"),
            (
                "activity", "customer", "partner", "oracle", "notes",
                "responsible", "accountable", "consulted", "informed",
            ),
        ),
        "customer_obligations": _clean_rows(delivery.get("customer_obligations"), ("statement", "owner", "due_date")),
        "implementation_scope": _clean_rows(delivery.get("implementation_scope"), ("activity", "deliverable", "owner")),
        "transition_milestones": _clean_rows(
            delivery.get("transition_milestones"),
            ("milestone", "owner", "date", "dependency", "status", "notes", "acceptance"),
        ),
    })
    normalized_flags = {
        "include_pricing": _clean_bool(flags.get("include_pricing"), True),
        "include_security": normalized_security["include_section"],
        "include_raci": _clean_bool(flags.get("include_raci")),
        "include_risks": _clean_bool(flags.get("include_risks")),
        "include_transition": _clean_bool(flags.get("include_transition")),
        "include_oracle_lift": _clean_bool(flags.get("include_oracle_lift")),
    }
    review_workflow = normalize_review_workflow(raw.get("review_workflow"))
    delivery_governance = normalize_delivery_governance(raw.get("delivery_governance"))
    acceptance_handover = normalize_acceptance_handover(raw.get("acceptance_handover"))
    # Phase 3/4 reviewers are the safe migration source for Phase 5 assignments.
    if not review_workflow["reviewers"]:
        review_workflow["reviewers"] = [
            {**person, "id": hashlib.sha256(f"reviewer:{person.get('email')}:{person.get('name')}".encode()).hexdigest()[:24], "required": True, "status": "pending", "date": "", "comment": ""}
            for person in normalized_delivery["reviewers"]
        ]
    if not review_workflow["approvers"]:
        review_workflow["approvers"] = [
            {**person, "id": hashlib.sha256(f"approver:{person.get('email')}:{person.get('name')}".encode()).hexdigest()[:24], "required": True, "status": "pending", "date": "", "comment": ""}
            for person in normalized_delivery["approvers"]
        ]
    return {
        "schema_version": "2.0", "status": review_workflow["status"],
        "source_assessment_id": _clean_text(raw.get("source_assessment_id"), 100),
        "source_snapshot_hash": _clean_text(raw.get("source_snapshot_hash"), 128),
        "source_step4_updated_at": _clean_text(raw.get("source_step4_updated_at"), 64),
        "customer_document": {
            "customer_legal_name": _clean_text(customer.get("customer_legal_name"), 240),
            "project_name": _clean_text(customer.get("project_name"), 240),
            "assessment_name": _clean_text(customer.get("assessment_name"), 240),
            "document_author": _clean_text(customer.get("document_author"), 160),
            "document_author_email": _clean_text(customer.get("document_author_email"), 254),
            "version": _clean_text(customer.get("version") or "0.1", 20),
            "version_comment": _clean_multiline(customer.get("version_comment"), 1000),
            "confidentiality_classification": _clean_text(customer.get("confidentiality_classification") or "Oracle Restricted — Employees Only", 240),
        },
        "business": {**{key: _clean_multiline(business.get(key), 8000) for key in REQUIRED_BUSINESS_FIELDS}, **{key: _clean_multiline(business.get(key), 8000) for key in BUSINESS_OPTIONAL_FIELDS}},
        "network": normalized_network, "security": normalized_security,
        "operations": normalized_operations, "delivery": normalized_delivery,
        "section_flags": normalized_flags,
        "wizard": {
            "current_step": current_step, "completed_steps": completed_steps,
            "completion_percentage": max(0, min(100, int(wizard.get("completion_percentage") or 0))),
            "last_saved_section": _clean_text(wizard.get("last_saved_section"), 80),
        },
        "validation_results": deepcopy(raw.get("validation_results")) if isinstance(raw.get("validation_results"), dict) else {},
        "review_workflow": review_workflow,
        "delivery_governance": delivery_governance,
        "acceptance_handover": acceptance_handover,
        "last_saved_at": _clean_text(raw.get("last_saved_at"), 64),
    }


def snapshot_hash(snapshot: dict[str, Any]) -> str:
    stable = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _neutral_list(value: Any) -> list[str]:
    return _clean_list(value)


def _as_status_text(value: Any) -> str:
    return _clean_multiline(value) or NEUTRAL


def build_sdd_payload(
    snapshot: dict[str, Any],
    configuration: dict[str, Any],
    *,
    final: bool = False,
    document_version: str | None = None,
) -> dict[str, Any]:
    """Create the exact Phase 2 payload without running sizing or pricing."""
    config = normalize_sdd_configuration(configuration)
    document, business = config["customer_document"], config["business"]
    source_document = snapshot.get("document") if isinstance(snapshot.get("document"), dict) else {}
    source_scope = deepcopy(snapshot.get("scope")) if isinstance(snapshot.get("scope"), dict) else {}
    source_sizing = deepcopy(snapshot.get("sizing")) if isinstance(snapshot.get("sizing"), dict) else {}
    clusters = deepcopy(snapshot.get("target_clusters")) if isinstance(snapshot.get("target_clusters"), list) else []
    source_commercial = deepcopy(snapshot.get("commercial")) if isinstance(snapshot.get("commercial"), dict) else {}
    network, security = config["network"], config["security"]
    operations, delivery, flags = config["operations"], config["delivery"], config["section_flags"]
    workflow = config["review_workflow"]
    connectivity = []
    if network.get("fastconnect_enabled"):
        connectivity.append("fastconnect")
    if network.get("ipsec_vpn_enabled"):
        connectivity.append("ipsec_vpn")
    network_payload = {
        "oci_region": _clean_text(network.get("oci_region")) or NEUTRAL,
        "tenancy_name_or_ocid": _clean_text(network.get("tenancy_name_or_ocid")) or NEUTRAL,
        "compartment_name_or_ocid": _clean_text(network.get("compartment_name_or_ocid")) or NEUTRAL,
        "vcn_name": _clean_text(network.get("vcn_name")) or NEUTRAL,
        "vcn_cidr": _clean_text(network.get("vcn_cidr")) or NEUTRAL,
        "sddc_cidr": _clean_text(network.get("sddc_cidr")) or NEUTRAL,
        "workload_cidrs": _neutral_list(network.get("workload_cidrs")),
        "management_cidrs": _neutral_list(network.get("management_cidrs")),
        "vmotion_cidrs": _neutral_list(network.get("vmotion_cidrs")),
        "replication_cidrs": _neutral_list(network.get("replication_cidrs")),
        "hcx_cidrs": _neutral_list(network.get("hcx_cidrs")),
        "dns": _neutral_list(network.get("dns_servers")), "ntp": _neutral_list(network.get("ntp_servers")),
        "connectivity": connectivity,
        "fastconnect": {"enabled": bool(network.get("fastconnect_enabled")), "details": _as_status_text(network.get("fastconnect_details"))},
        "ipsec_vpn": {"enabled": bool(network.get("ipsec_vpn_enabled")), "details": _as_status_text(network.get("ipsec_vpn_details"))},
        "drg": _clean_text(network.get("drg_details")) or NEUTRAL,
        "hcx": {"enabled": bool(network.get("hcx_enabled")), "details": _as_status_text(network.get("hcx_details"))},
        "segments": [{"name": row["name"] or NEUTRAL, "cidr": row["cidr"] or NEUTRAL, "purpose": row["purpose"] or NEUTRAL, **{key: val for key, val in row.items() if key not in {"name", "cidr", "purpose"} and val}} for row in network.get("segments", [])],
    }
    backup, dr, ha = operations.get("backup", {}), operations.get("disaster_recovery", {}), operations.get("ha", {})
    operations_payload = {
        "implementation_provider": operations.get("implementation_provider", "customer"),
        "operating_model": _as_status_text(operations.get("operating_model")),
        "monitoring": _as_status_text(operations.get("monitoring_approach")),
        "backup": {"enabled": bool(backup.get("enabled")), "description": _as_status_text(backup.get("description") or operations.get("backup_requirements"))},
        "disaster_recovery": {"enabled": bool(dr.get("enabled")), "description": _as_status_text(dr.get("description") or operations.get("dr_requirements"))},
        "ha": {"enabled": bool(ha.get("enabled")), "description": _as_status_text(ha.get("description") or operations.get("ha_requirements"))},
        "migration_method": _as_status_text(delivery.get("migration_method")),
        "migration_window": _as_status_text(delivery.get("migration_window")),
        "downtime_tolerance": _as_status_text(delivery.get("downtime_tolerance")),
        "validation_and_rollback": _as_status_text("\n".join(filter(None, [delivery.get("validation_approach"), delivery.get("rollback_approach")]))),
        "transition_plan": _as_status_text(delivery.get("transition_plan_summary")),
    }
    if not source_commercial.get("pricing_available"):
        source_commercial["monthly_cost"] = None
        source_commercial["annual_cost"] = None
    assumptions = list(delivery.get("assumptions") or [])
    if business.get("assumptions"):
        assumptions.append({"statement": business["assumptions"], "owner": NEUTRAL, "status": "Review required"})
    risks = list(delivery.get("risks") or [])
    if business.get("known_risks"):
        risks.append({"id": "", "description": business["known_risks"], "impact": NEUTRAL, "mitigation": NEUTRAL, "owner": NEUTRAL})
    obligations = list(delivery.get("customer_obligations") or [])
    if business.get("customer_obligations"):
        obligations.append({"statement": business["customer_obligations"], "owner": NEUTRAL, "due_date": NEUTRAL})
    version = document_version or (workflow.get("final_version") if final else workflow.get("current_revision")) or document["version"] or "0.1"
    approval_history = [
        {
            "version": item.get("version") or version,
            "author": item.get("actor") or document["document_author"],
            "date": item.get("date") or date.today().isoformat(),
            "comment": item.get("comment") or item.get("event", "").replace("_", " ").title(),
        }
        for item in workflow.get("approval_history", [])
        if item.get("event") in {"submitted_for_review", "changes_requested", "approved", "finalized"}
    ]
    return {
        "schema_version": "1.0",
        "document": {
            "customer_name": _clean_text(source_document.get("customer_name")) or NEUTRAL,
            "customer_legal_name": document["customer_legal_name"], "project_name": document["project_name"],
            "assessment_name": document.get("assessment_name") or _clean_text(source_document.get("assessment_name")) or "OCVS assessment",
            "assessment_date": _clean_text(source_document.get("assessment_date")) or date.today().isoformat(),
            "rvtools_file_name": Path(_clean_text(source_document.get("rvtools_file_name")) or "inventory.xlsx").name,
            "generation_date": date.today().isoformat(), "document_version": version,
            "version_comment": document["version_comment"], "document_author": document["document_author"],
            "document_author_email": document["document_author_email"],
            "confidentiality_classification": document["confidentiality_classification"],
            "draft_status": not final, "approval_status": "Finalized" if final else workflow["status"].replace("_", " ").title(),
            "copyright_year": date.today().year,
        },
        "business": {key: business[key] for key in REQUIRED_BUSINESS_FIELDS},
        "scope": source_scope, "sizing": source_sizing, "target_clusters": clusters,
        "network": network_payload,
        "security": {
            "include_section": bool(security.get("include_section")),
            "iam_model": _as_status_text(security.get("iam_model")),
            "encryption": _as_status_text(security.get("encryption_requirements")),
            "logging": _as_status_text("\n".join(filter(None, [security.get("logging_requirements"), security.get("siem_integration")]))),
            "monitoring": _as_status_text(security.get("monitoring_requirements")),
            "requirements": _as_status_text("\n".join(filter(None, [security.get("security_requirements"), security.get("compliance_requirements"), security.get("responsibility_notes")]))),
        },
        "operations": operations_payload, "commercial": source_commercial,
        "delivery": {
            "document_history": approval_history or list(delivery.get("document_history") or []) or [{"version": version, "author": document["document_author"], "date": date.today().strftime("%B %d, %Y"), "comment": document["version_comment"] or "Initial Draft SDD"}],
            "reviewers": list(workflow.get("reviewers") or delivery.get("reviewers") or []), "approvers": list(workflow.get("approvers") or delivery.get("approvers") or []),
            "project_team": list(delivery.get("project_team") or []), "environments": list(delivery.get("environments") or []),
            "assumptions": assumptions,
            "risks": risks,
            "raci": [
                {
                    "activity": row.get("activity") or NEUTRAL,
                    "responsible": row.get("customer") or row.get("responsible") or NEUTRAL,
                    "accountable": row.get("partner") or row.get("accountable") or NEUTRAL,
                    "consulted": row.get("oracle") or row.get("consulted") or NEUTRAL,
                    "informed": row.get("notes") or row.get("informed") or NEUTRAL,
                }
                for row in delivery.get("raci") or []
            ],
            "customer_obligations": obligations, "implementation_scope": list(delivery.get("implementation_scope") or []),
            "transition_milestones": [
                {
                    "milestone": row.get("milestone") or NEUTRAL,
                    "owner": row.get("owner") or NEUTRAL,
                    "date": row.get("date") or NEUTRAL,
                    "acceptance": " | ".join(
                        value
                        for value in (
                            row.get("dependency"), row.get("status"), row.get("notes"), row.get("acceptance")
                        )
                        if value
                    ) or NEUTRAL,
                }
                for row in delivery.get("transition_milestones") or []
            ],
        },
        "section_flags": {
            "include_pricing": bool(flags.get("include_pricing", True)), "include_raci": bool(flags.get("include_raci")),
            "include_risks": bool(flags.get("include_risks")), "include_transition": bool(flags.get("include_transition")),
            "include_oracle_lift": bool(flags.get("include_oracle_lift")),
        },
        "specialist_review_warnings": list(snapshot.get("specialist_review_warnings") or ["Draft output requires specialist validation before customer delivery."]),
    }


def validate_section(section: str, configuration: dict[str, Any]) -> dict[str, list[str]]:
    """Return user-facing errors and warnings for one wizard section."""
    config = normalize_sdd_configuration(configuration)
    errors: list[str] = []
    if section == "customer-project":
        for field in REQUIRED_DOCUMENT_FIELDS:
            if not config["customer_document"].get(field):
                errors.append(f"{field.replace('_', ' ').title()} is required.")
        email = config["customer_document"].get("document_author_email", "")
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Enter a valid document author email address.")
        version = config["customer_document"].get("version", "")
        if version and not re.fullmatch(r"\d+\.\d+", version):
            errors.append("Document version must use a number such as 0.1 or 1.0.")
        for group in ("reviewers", "approvers", "project_team"):
            for person in config["delivery"].get(group, []):
                if person.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", person["email"]):
                    errors.append(f"Enter a valid email address for {person.get('name') or group}.")
    elif section == "business-requirements":
        for field in REQUIRED_BUSINESS_FIELDS:
            if not config["business"].get(field):
                errors.append(f"{field.replace('_', ' ').title()} is required or must be marked Not provided / Not applicable.")
    elif section == "network-design":
        cidrs: list[tuple[str, str]] = []
        for key in ("vcn_cidr", "sddc_cidr"):
            if config["network"].get(key):
                cidrs.append((key, config["network"][key]))
        for key in ("workload_cidrs", "management_cidrs", "vmotion_cidrs", "replication_cidrs", "hcx_cidrs"):
            cidrs.extend((key, val) for val in config["network"].get(key, []))
        cidrs.extend(("network segment", row.get("cidr", "")) for row in config["network"].get("segments", []) if row.get("cidr"))
        for label, value in cidrs:
            try:
                ipaddress.ip_network(value, strict=False)
            except ValueError:
                errors.append(f"{label.replace('_', ' ').title()} contains an invalid CIDR: {value}.")
    elif section == "security-compliance" and config["section_flags"].get("include_security"):
        for field in ("iam_model", "encryption_requirements", "logging_requirements", "security_requirements"):
            if not config["security"].get(field):
                errors.append(f"{field.replace('_', ' ').title()} is required when Security & Compliance is enabled.")
    elif section == "migration-transition":
        if config["section_flags"].get("include_raci") and not config["delivery"].get("raci"):
            errors.append("Add at least one RACI row or disable the RACI section.")
        if config["section_flags"].get("include_risks") and not (config["delivery"].get("risks") or config["business"].get("known_risks")):
            errors.append("Add at least one known risk or disable the Risks section.")
        if config["section_flags"].get("include_transition") and not config["delivery"].get("transition_milestones"):
            errors.append("Add at least one transition milestone or disable the Transition section.")
    return {"errors": list(dict.fromkeys(errors)), "warnings": []}


def readiness(snapshot: dict[str, Any] | None, configuration: dict[str, Any], *, scenario_id: str, generator_errors: list[str] | None = None) -> dict[str, Any]:
    config = normalize_sdd_configuration(configuration)
    blocking: list[str] = []
    warnings: list[str] = []
    missing_required: list[str] = []
    errors_by_step: dict[str, list[str]] = {}
    warnings_by_step: dict[str, list[str]] = {}
    if scenario_id != "ocvs":
        blocking.append("Draft SDD generation is available only for Move to OCVS.")
    if not snapshot:
        blocking.append("Save the final OCVS sizing result before generating the SDD.")
        current_hash = ""
    else:
        current_hash = snapshot_hash(snapshot)
        scope = snapshot.get("scope") if isinstance(snapshot.get("scope"), dict) else {}
        sizing = snapshot.get("sizing") if isinstance(snapshot.get("sizing"), dict) else {}
        clusters = snapshot.get("target_clusters") if isinstance(snapshot.get("target_clusters"), list) else []
        if int(scope.get("selected_vm_count") or 0) < 1:
            blocking.append("Select at least one VM before generating the SDD.")
        source_clusters = scope.get("source_clusters") if isinstance(scope.get("source_clusters"), list) else []
        if source_clusters:
            for scope_key, cluster_key, tolerance in (("selected_vm_count", "vm_count", 0.0), ("powered_on_vm_count", "powered_on", 0.0), ("powered_off_vm_count", "powered_off", 0.0), ("selected_vcpu", "vcpu", 0.0), ("selected_ram_gb", "ram_gb", 0.1), ("selected_storage_tb", "storage_tb", 0.1)):
                if abs(float(scope.get(scope_key) or 0) - sum(float(row.get(cluster_key) or 0) for row in source_clusters)) > tolerance:
                    blocking.append("The selected assessment scope does not reconcile with its source-cluster totals.")
                    break
        if not clusters or int(sizing.get("target_cluster_count") or 0) != len(clusters):
            blocking.append("Save a valid OCVS target-cluster design.")
        if sizing.get("topology") == "multi":
            management = sum(1 for row in clusters if row.get("role") == "unified_management")
            assigned = [name for row in clusters for name in row.get("assigned_source_clusters", [])]
            expected = [row.get("name") for row in source_clusters]
            if management != 1 or len(assigned) != len(set(assigned)) or set(assigned) != set(expected):
                blocking.append("The multi-cluster design has unassigned or duplicated source clusters.")
        for row in clusters:
            total = int(row.get("total_nodes") or 0)
            shape = str(row.get("selected_shape") or "").lower()
            minimum = 3 if row.get("role") == "unified_management" else (3 if "dense" in shape else 1 if "gpu" in shape else 2)
            if total < minimum:
                blocking.append(f"{row.get('name') or 'Target cluster'} requires at least {minimum} hosts.")
        if not snapshot.get("commercial", {}).get("pricing_available"):
            warnings.append("Pricing is unavailable; the Draft SDD will show no invented amounts.")
            warnings_by_step.setdefault("review-generate", []).append(warnings[-1])
    for section in WIZARD_SECTIONS[:-1]:
        result = validate_section(section, config)
        errors_by_step[section] = result["errors"]
        blocking.extend(result["errors"])
    for field in REQUIRED_DOCUMENT_FIELDS:
        if not config["customer_document"].get(field):
            missing_required.append(field.replace("_", " ").title())
    for field in REQUIRED_BUSINESS_FIELDS:
        if not config["business"].get(field):
            missing_required.append(field.replace("_", " ").title())
    stale = bool(current_hash and config.get("source_snapshot_hash") and config.get("source_snapshot_hash") != current_hash)
    if stale:
        blocking.append("The selected workload or sizing has changed. Review and save the Draft SDD configuration again.")
        errors_by_step.setdefault("review-generate", []).append(blocking[-1])
    if not config.get("source_snapshot_hash") and snapshot:
        blocking.append("Save the Draft SDD configuration before generating the document.")
        errors_by_step.setdefault("review-generate", []).append(blocking[-1])
    if generator_errors:
        blocking.append("The Draft SDD data did not pass document validation.")
        errors_by_step.setdefault("review-generate", []).append(blocking[-1])
    step_complete = {section: not errors_by_step.get(section) for section in WIZARD_SECTIONS[:-1]}
    step_complete["review-generate"] = not blocking
    completion = round(100 * sum(1 for section in WIZARD_SECTIONS[:-1] if step_complete.get(section)) / (len(WIZARD_SECTIONS) - 1))
    return {
        "ready": not blocking, "completion_percentage": completion,
        "step_completion": step_complete,
        "blocking_errors": list(dict.fromkeys(blocking)),
        "blocking_errors_by_step": {key: list(dict.fromkeys(val)) for key, val in errors_by_step.items() if val},
        "warnings": list(dict.fromkeys(warnings)),
        "warnings_by_step": {key: list(dict.fromkeys(val)) for key, val in warnings_by_step.items() if val},
        "missing_required_inputs": missing_required, "missing_optional_inputs": [],
        "specialist_review_items": list(snapshot.get("specialist_review_warnings") or []) if snapshot else [],
        "source_snapshot_hash": current_hash, "configuration_is_stale": stale,
    }
