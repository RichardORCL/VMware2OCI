"""Customer acceptance, implementation readiness, and handover for delivered OCVS SDDs."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from copy import deepcopy
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.ocvs_sdd_delivery import (
    artifact_integrity,
    delivery_manifest,
    find_version,
    read_artifact,
    safe_component,
)


ACCEPTANCE_STATUSES = {
    "acceptance_pending", "accepted", "accepted_with_conditions", "rejected",
    "handover_ready", "handed_over",
}
CHECKLIST_STATUSES = {"not_started", "in_progress", "complete", "not_applicable", "blocked"}
ACTION_STATUSES = {"open", "in_progress", "blocked", "closed"}
ACTION_SOURCES = {
    "customer_condition", "technical_prerequisite", "commercial_prerequisite",
    "security_prerequisite", "migration_prerequisite",
}
ACTION_PRIORITIES = {"blocking", "high", "medium", "low"}


CHECKLIST_DEFINITIONS = (
    ("Governance and approvals", (
        "Delivered SDD accepted", "Commercial approval completed", "Project sponsor confirmed",
        "Implementation owner assigned", "Change-management process confirmed",
    )),
    ("OCI prerequisites", (
        "OCI tenancy and target region confirmed", "Required compartments confirmed",
        "IAM groups and policies confirmed", "Service limits and quotas validated",
        "Required OCVS capacity available", "Required subscriptions and agreements confirmed",
    )),
    ("Network and connectivity", (
        "VCN and subnet design validated", "CIDR ranges confirmed", "DRG and routing design validated",
        "DNS and NTP requirements confirmed", "FastConnect or VPN connectivity confirmed",
        "Firewall rules and required ports validated", "HCX connectivity requirements validated",
    )),
    ("OCVS platform", (
        "Target SDDC topology confirmed", "Single-cluster or multi-cluster design confirmed",
        "OCVS shapes and node counts confirmed", "Storage architecture confirmed",
        "Commitment term confirmed", "vCenter, NSX and HCX responsibilities assigned",
    )),
    ("Migration preparation", (
        "Final VM scope confirmed", "Application owners identified", "Application dependencies reviewed",
        "Migration wave planning required", "Backup and rollback strategy confirmed",
        "Testing and validation owners assigned", "Business outage constraints documented",
    )),
    ("Operations and support", (
        "Monitoring approach confirmed", "Backup approach confirmed",
        "Security operations ownership confirmed", "OCI support process confirmed",
        "Post-migration operating model confirmed", "Knowledge-transfer requirements confirmed",
    )),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _multiline(value: Any, limit: int = 8000) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()[:limit]


def _email(value: Any) -> str:
    candidate = _text(value, 254)
    return candidate if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", candidate) else ""


def _valid_date(value: Any, *, required: bool = False) -> tuple[str, bool]:
    candidate = _text(value, 20)
    if not candidate:
        return "", not required
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
        return candidate, True
    except ValueError:
        return candidate, False


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:70]


def default_checklist() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category, labels in CHECKLIST_DEFINITIONS:
        for label in labels:
            rows.append({
                "id": _slug(f"{category}-{label}"), "category": category, "label": label,
                "mandatory": True, "status": "not_started", "owner": "", "target_date": "",
                "comment": "", "evidence": "", "updated_at": "", "updated_by": "",
            })
    return rows


def _checklist_item(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    status = _text(raw.get("status"), 30).lower()
    return {
        "id": _text(raw.get("id"), 100), "category": _text(raw.get("category"), 120),
        "label": _text(raw.get("label"), 240), "mandatory": bool(raw.get("mandatory", True)),
        "status": status if status in CHECKLIST_STATUSES else "not_started",
        "owner": _text(raw.get("owner"), 160), "target_date": _text(raw.get("target_date"), 20),
        "comment": _multiline(raw.get("comment"), 2000), "evidence": _text(raw.get("evidence"), 500),
        "updated_at": _text(raw.get("updated_at"), 64), "updated_by": _text(raw.get("updated_by"), 160),
    }


def _action(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    source = _text(raw.get("source"), 50).lower()
    priority = _text(raw.get("priority"), 30).lower()
    status = _text(raw.get("status"), 30).lower()
    return {
        "id": _text(raw.get("id"), 80) or uuid4().hex,
        "action_identifier": _text(raw.get("action_identifier"), 40),
        "category": _text(raw.get("category"), 120), "description": _multiline(raw.get("description"), 3000),
        "source": source if source in ACTION_SOURCES else "technical_prerequisite",
        "owner": _text(raw.get("owner"), 160), "due_date": _text(raw.get("due_date"), 20),
        "priority": priority if priority in ACTION_PRIORITIES else "medium",
        "status": status if status in ACTION_STATUSES else "open",
        "resolution_comment": _multiline(raw.get("resolution_comment"), 2000),
        "closed_date": _text(raw.get("closed_date"), 20), "created_at": _text(raw.get("created_at"), 64),
        "created_by": _text(raw.get("created_by"), 160), "updated_at": _text(raw.get("updated_at"), 64),
        "updated_by": _text(raw.get("updated_by"), 160),
    }


def _audit_event(value: Any) -> dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    return {
        "id": _text(raw.get("id"), 80) or uuid4().hex, "event": _text(raw.get("event"), 100),
        "timestamp": _text(raw.get("timestamp"), 64), "actor": _text(raw.get("actor"), 160),
        "version": _text(raw.get("version"), 20), "assessment_id": _text(raw.get("assessment_id"), 100),
        "description": _text(raw.get("description"), 500),
    }


def _record(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    status = _text(raw.get("status"), 40).lower()
    checklist = [_checklist_item(item) for item in raw.get("checklist", []) if isinstance(item, dict)] if isinstance(raw.get("checklist"), list) else []
    if not checklist:
        checklist = default_checklist()
    return {
        "id": _text(raw.get("id"), 80) or uuid4().hex, "artifact_id": _text(raw.get("artifact_id"), 80),
        "sdd_version": _text(raw.get("sdd_version"), 20), "assessment_id": _text(raw.get("assessment_id"), 100),
        "status": status if status in ACCEPTANCE_STATUSES else "acceptance_pending",
        "started_at": _text(raw.get("started_at"), 64), "started_by": _text(raw.get("started_by"), 160),
        "acceptance": deepcopy(raw.get("acceptance")) if isinstance(raw.get("acceptance"), dict) else {},
        "checklist": checklist, "actions": [_action(item) for item in raw.get("actions", []) if isinstance(item, dict)] if isinstance(raw.get("actions"), list) else [],
        "implementation_owner": _text(raw.get("implementation_owner"), 160),
        "migration_planning_owner": _text(raw.get("migration_planning_owner"), 160),
        "readiness": deepcopy(raw.get("readiness")) if isinstance(raw.get("readiness"), dict) else {},
        "handover": deepcopy(raw.get("handover")) if isinstance(raw.get("handover"), dict) else {},
        "baseline_superseded": bool(raw.get("baseline_superseded", False)),
        "superseded_by_version": _text(raw.get("superseded_by_version"), 20),
        "copied_from_acceptance_id": _text(raw.get("copied_from_acceptance_id"), 80),
        "migration_planning_payload": deepcopy(raw.get("migration_planning_payload")) if isinstance(raw.get("migration_planning_payload"), dict) else {},
    }


def normalize_acceptance_handover(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    records = [_record(item) for item in raw.get("records", []) if isinstance(item, dict)] if isinstance(raw.get("records"), list) else []
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in records:
        if item["artifact_id"] and item["artifact_id"] not in seen:
            seen.add(item["artifact_id"])
            unique.append(item)
    return {
        "schema_version": "1.0", "records": unique,
        "audit_events": [_audit_event(item) for item in raw.get("audit_events", []) if isinstance(item, dict)] if isinstance(raw.get("audit_events"), list) else [],
        "active_acceptance_id": _text(raw.get("active_acceptance_id"), 80),
    }


def _audit(governance: dict[str, Any], record: dict[str, Any], event: str, actor: str, description: str) -> None:
    governance["audit_events"].append({
        "id": uuid4().hex, "event": event, "timestamp": _now(), "actor": _text(actor, 160),
        "version": record["sdd_version"], "assessment_id": record["assessment_id"],
        "description": _text(description, 500),
    })


def find_acceptance(governance: dict[str, Any], *, acceptance_id: str = "", artifact_id: str = "") -> dict[str, Any] | None:
    data = normalize_acceptance_handover(governance)
    return next((item for item in data["records"] if (acceptance_id and item["id"] == acceptance_id) or (artifact_id and item["artifact_id"] == artifact_id)), None)


def start_acceptance(configuration: dict[str, Any], root: Path, artifact_id: str, actor: str, *, copy_previous: bool = False) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration)
    delivery = config.get("delivery_governance") if isinstance(config.get("delivery_governance"), dict) else {}
    artifact = find_version(delivery, artifact_id=artifact_id)
    governance = normalize_acceptance_handover(config.get("acceptance_handover"))
    errors: list[str] = []
    if not artifact or artifact.get("status") != "delivered":
        errors.append("Only a delivered, non-superseded SDD can enter customer acceptance.")
    if not _text(actor, 160):
        errors.append("The person starting customer acceptance is required.")
    if artifact and not artifact_integrity(root, artifact)["valid"]:
        errors.append("Artifact integrity validation failed; customer acceptance is blocked.")
    if find_acceptance(governance, artifact_id=artifact_id):
        errors.append("Customer acceptance already exists for this delivered SDD version.")
    if errors:
        return config, errors
    previous = governance["records"][-1] if governance["records"] else None
    record = _record({
        "id": uuid4().hex, "artifact_id": artifact_id, "sdd_version": artifact["version"],
        "assessment_id": artifact["assessment_id"], "status": "acceptance_pending",
        "started_at": _now(), "started_by": actor,
        "checklist": deepcopy(previous["checklist"]) if copy_previous and previous else default_checklist(),
        "actions": deepcopy(previous["actions"]) if copy_previous and previous else [],
        "copied_from_acceptance_id": previous["id"] if copy_previous and previous else "",
    })
    if copy_previous:
        for item in record["checklist"]:
            item.update({"updated_at": "", "updated_by": ""})
        for item in record["actions"]:
            item.update({"id": uuid4().hex, "action_identifier": "", "status": "open", "closed_date": "", "resolution_comment": ""})
    governance["records"].append(record)
    governance["active_acceptance_id"] = record["id"]
    _audit(governance, record, "acceptance_started", actor, "Customer acceptance opened for the delivered SDD baseline.")
    config["acceptance_handover"] = governance
    return config, []


def record_acceptance_decision(configuration: dict[str, Any], root: Path, acceptance_id: str, fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration)
    governance = normalize_acceptance_handover(config.get("acceptance_handover"))
    record = find_acceptance(governance, acceptance_id=acceptance_id)
    if not record:
        return config, ["The customer-acceptance record was not found."]
    target = next(item for item in governance["records"] if item["id"] == acceptance_id)
    errors: list[str] = []
    if target["status"] != "acceptance_pending" or target["acceptance"]:
        errors.append("A customer acceptance decision has already been recorded for this SDD version.")
    artifact = find_version(config.get("delivery_governance", {}), artifact_id=target["artifact_id"])
    if not artifact or artifact.get("status") != "delivered":
        errors.append("The delivered SDD baseline is no longer eligible for acceptance.")
    elif not artifact_integrity(root, artifact)["valid"]:
        errors.append("Artifact integrity validation failed; customer acceptance is blocked.")
    decision = _text(fields.get("decision"), 40).lower()
    if decision not in {"accepted", "accepted_with_conditions", "rejected"}:
        errors.append("Choose Accepted, Accepted with conditions, or Rejected.")
    representative = _text(fields.get("customer_representative"), 160)
    company = _text(fields.get("customer_company"), 200)
    recorder = _text(fields.get("recorded_by"), 160)
    if not representative: errors.append("Customer representative is required.")
    if not company: errors.append("Customer company is required.")
    if not recorder: errors.append("Internal recorder is required.")
    decision_date, valid_decision_date = _valid_date(fields.get("decision_date"), required=True)
    recording_date, valid_recording_date = _valid_date(fields.get("recording_date"), required=True)
    if not valid_decision_date: errors.append("A valid customer decision date is required.")
    if not valid_recording_date: errors.append("A valid internal recording date is required.")
    email = _text(fields.get("customer_email"), 254)
    if email and not _email(email): errors.append("Provide a valid customer e-mail address or leave it blank.")
    conditions = [line.strip() for line in _multiline(fields.get("conditions"), 8000).splitlines() if line.strip()]
    comments = _multiline(fields.get("comments"), 4000)
    if decision == "accepted_with_conditions" and not conditions:
        errors.append("Accepted with conditions requires at least one condition or reservation.")
    if decision == "rejected" and not (comments or conditions):
        errors.append("Rejected requires a reason.")
    if errors:
        return config, errors
    target["acceptance"] = {
        "decision": decision, "customer_representative": representative,
        "customer_role": _text(fields.get("customer_role"), 160), "customer_company": company,
        "decision_date": decision_date, "customer_email": _email(email), "comments": comments,
        "conditions": conditions, "evidence_reference": _text(fields.get("evidence_reference"), 500),
        "recorded_by": recorder, "recording_date": recording_date, "recorded_at": _now(),
    }
    target["status"] = decision
    accepted_item = next((item for item in target["checklist"] if item["label"] == "Delivered SDD accepted"), None)
    if accepted_item:
        accepted_item.update({"status": "complete" if decision != "rejected" else "blocked", "owner": representative, "updated_at": _now(), "updated_by": recorder})
    for condition in conditions:
        action = _action({
            "id": uuid4().hex, "action_identifier": f"COND-{len(target['actions']) + 1:03d}",
            "category": "Customer acceptance", "description": condition, "source": "customer_condition",
            "priority": "medium", "status": "open", "created_at": _now(), "created_by": recorder,
        })
        target["actions"].append(action)
        _audit(governance, target, "acceptance_condition_added", recorder, f"Customer condition {action['action_identifier']} added.")
    _audit(governance, target, "acceptance_decision_recorded", recorder, f"Customer decision recorded as {decision.replace('_', ' ')}.")
    config["acceptance_handover"] = governance
    config = recalculate_readiness(config, root, acceptance_id, actor=recorder)
    return config, []


def update_checklist_item(configuration: dict[str, Any], root: Path, acceptance_id: str, item_id: str, fields: dict[str, Any], actor: str) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration); governance = normalize_acceptance_handover(config.get("acceptance_handover"))
    record = next((item for item in governance["records"] if item["id"] == acceptance_id), None)
    if not record: return config, ["The customer-acceptance record was not found."]
    item = next((row for row in record["checklist"] if row["id"] == item_id), None)
    if not item: return config, ["The readiness checklist item was not found."]
    if record["status"] == "handed_over" and item["status"] in {"complete", "not_applicable"}:
        return config, ["Completed checklist items are locked after implementation handover."]
    status = _text(fields.get("status"), 30).lower()
    if status not in CHECKLIST_STATUSES: return config, ["Choose a valid checklist status."]
    target_date, valid_date = _valid_date(fields.get("target_date"))
    if not valid_date: return config, ["Provide a valid target date or leave it blank."]
    item.update({
        "status": status, "owner": _text(fields.get("owner"), 160), "target_date": target_date,
        "comment": _multiline(fields.get("comment"), 2000), "evidence": _text(fields.get("evidence"), 500),
        "updated_at": _now(), "updated_by": _text(actor, 160),
    })
    _audit(governance, record, "checklist_item_updated", actor, f"{item['label']} set to {status.replace('_', ' ')}.")
    config["acceptance_handover"] = governance
    return recalculate_readiness(config, root, acceptance_id, actor=actor), []


def set_readiness_owners(configuration: dict[str, Any], root: Path, acceptance_id: str, implementation_owner: str, migration_owner: str, actor: str) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration); governance = normalize_acceptance_handover(config.get("acceptance_handover"))
    record = next((item for item in governance["records"] if item["id"] == acceptance_id), None)
    if not record: return config, ["The customer-acceptance record was not found."]
    record["implementation_owner"] = _text(implementation_owner, 160)
    record["migration_planning_owner"] = _text(migration_owner, 160)
    _audit(governance, record, "readiness_owners_updated", actor, "Implementation and migration-planning ownership updated.")
    config["acceptance_handover"] = governance
    return recalculate_readiness(config, root, acceptance_id, actor=actor), []


def create_action(configuration: dict[str, Any], root: Path, acceptance_id: str, fields: dict[str, Any], actor: str) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration); governance = normalize_acceptance_handover(config.get("acceptance_handover"))
    record = next((item for item in governance["records"] if item["id"] == acceptance_id), None)
    if not record: return config, ["The customer-acceptance record was not found."]
    description = _multiline(fields.get("description"), 3000)
    if not description: return config, ["Action description is required."]
    due_date, valid_date = _valid_date(fields.get("due_date"))
    if not valid_date: return config, ["Provide a valid action due date or leave it blank."]
    action = _action({**fields, "id": uuid4().hex, "description": description, "due_date": due_date,
                      "action_identifier": _text(fields.get("action_identifier"), 40) or f"ACT-{len(record['actions']) + 1:03d}",
                      "created_at": _now(), "created_by": actor, "updated_at": _now(), "updated_by": actor})
    record["actions"].append(action)
    _audit(governance, record, "action_created", actor, f"Action {action['action_identifier']} created.")
    config["acceptance_handover"] = governance
    return recalculate_readiness(config, root, acceptance_id, actor=actor), []


def update_action(configuration: dict[str, Any], root: Path, acceptance_id: str, action_id: str, fields: dict[str, Any], actor: str) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration); governance = normalize_acceptance_handover(config.get("acceptance_handover"))
    record = next((item for item in governance["records"] if item["id"] == acceptance_id), None)
    if not record: return config, ["The customer-acceptance record was not found."]
    action = next((item for item in record["actions"] if item["id"] == action_id), None)
    if not action: return config, ["The action was not found."]
    status = _text(fields.get("status"), 30).lower() or action["status"]
    if status not in ACTION_STATUSES: return config, ["Choose a valid action status."]
    due_date, valid_date = _valid_date(fields.get("due_date", action["due_date"]))
    if not valid_date: return config, ["Provide a valid action due date or leave it blank."]
    for key, limit in (("category", 120), ("owner", 160), ("resolution_comment", 2000)):
        if key in fields: action[key] = _multiline(fields[key], limit)
    priority = _text(fields.get("priority", action["priority"]), 30).lower()
    if priority in ACTION_PRIORITIES: action["priority"] = priority
    action.update({"status": status, "due_date": due_date, "updated_at": _now(), "updated_by": _text(actor, 160)})
    if status == "closed":
        closed_date, valid_closed = _valid_date(fields.get("closed_date") or date.today().isoformat(), required=True)
        if not valid_closed: return config, ["A valid closed date is required."]
        action["closed_date"] = closed_date
    event = "action_closed" if status == "closed" else "action_updated"
    _audit(governance, record, event, actor, f"Action {action['action_identifier']} updated to {status.replace('_', ' ')}.")
    config["acceptance_handover"] = governance
    return recalculate_readiness(config, root, acceptance_id, actor=actor), []


def readiness_decision(configuration: dict[str, Any], root: Path, record: dict[str, Any]) -> dict[str, Any]:
    artifact = find_version(configuration.get("delivery_governance", {}), artifact_id=record["artifact_id"])
    integrity = artifact_integrity(root, artifact) if artifact else {"valid": False, "errors": ["Delivered SDD baseline not found."]}
    blockers: list[str] = []
    decision = _text(record.get("acceptance", {}).get("decision"), 40)
    if not decision: blockers.append("Customer acceptance decision is pending.")
    if decision == "rejected": blockers.append("The customer rejected this SDD version; start a governed revision.")
    incomplete = [item for item in record["checklist"] if item["mandatory"] and item["status"] not in {"complete", "not_applicable"}]
    for item in incomplete:
        blockers.append(f"Mandatory checklist item incomplete: {item['label']}.")
    blocking_actions = [item for item in record["actions"] if item["status"] != "closed" and (item["priority"] == "blocking" or item["status"] == "blocked")]
    if blocking_actions: blockers.append(f"{len(blocking_actions)} blocking action(s) remain open.")
    if not integrity["valid"]: blockers.append("Delivered SDD artifact integrity validation failed.")
    if not record.get("implementation_owner"): blockers.append("Implementation owner is not assigned.")
    if not record.get("migration_planning_owner"): blockers.append("Migration-planning owner is not assigned.")
    open_conditions = [item for item in record["actions"] if item["source"] == "customer_condition" and item["status"] != "closed"]
    unowned_conditions = [item for item in open_conditions if not item["owner"]]
    if decision == "accepted_with_conditions" and unowned_conditions:
        blockers.append(f"{len(unowned_conditions)} customer condition(s) do not have an owner.")
    status = "Not ready"
    if not blockers and decision == "accepted_with_conditions": status = "Ready with conditions"
    elif not blockers and decision == "accepted": status = "Ready for implementation"
    return {
        "status": status, "blockers": blockers, "artifact_integrity": integrity,
        "mandatory_completed": sum(1 for item in record["checklist"] if item["mandatory"] and item["status"] in {"complete", "not_applicable"}),
        "mandatory_total": sum(1 for item in record["checklist"] if item["mandatory"]),
        "open_actions": sum(1 for item in record["actions"] if item["status"] != "closed"),
        "blocking_actions": len(blocking_actions), "overdue_actions": sum(1 for item in record["actions"] if action_overdue(item)),
        "calculated_at": _now(),
    }


def recalculate_readiness(configuration: dict[str, Any], root: Path, acceptance_id: str, *, actor: str = "System") -> dict[str, Any]:
    config = deepcopy(configuration); governance = normalize_acceptance_handover(config.get("acceptance_handover"))
    record = next((item for item in governance["records"] if item["id"] == acceptance_id), None)
    if not record: return config
    previous = _text(record.get("readiness", {}).get("status"), 60)
    record["readiness"] = readiness_decision(config, root, record)
    if record["status"] != "handed_over" and record["readiness"]["status"] in {"Ready with conditions", "Ready for implementation"}:
        record["status"] = "handover_ready"
    elif record["status"] == "handover_ready" and record["readiness"]["status"] == "Not ready":
        record["status"] = _text(record.get("acceptance", {}).get("decision"), 40) or "acceptance_pending"
    if previous != record["readiness"]["status"]:
        _audit(governance, record, "readiness_recalculated", actor, f"Implementation readiness: {record['readiness']['status']}.")
    config["acceptance_handover"] = governance
    return config


def action_overdue(action: dict[str, Any], today: date | None = None) -> bool:
    if action.get("status") == "closed" or not action.get("due_date"): return False
    try: due = datetime.strptime(str(action["due_date"]), "%Y-%m-%d").date()
    except ValueError: return False
    return due < (today or date.today())


def confirm_handover(configuration: dict[str, Any], root: Path, acceptance_id: str, fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration)
    initial = normalize_acceptance_handover(config.get("acceptance_handover"))
    initial_record = next((item for item in initial["records"] if item["id"] == acceptance_id), None)
    if initial_record:
        initial_record["implementation_owner"] = _text(fields.get("implementation_owner"), 160)
        initial_record["migration_planning_owner"] = _text(fields.get("migration_planning_owner"), 160)
        config["acceptance_handover"] = initial
    config = recalculate_readiness(config, root, acceptance_id, actor=_text(fields.get("handed_over_by"), 160) or "System")
    governance = normalize_acceptance_handover(config.get("acceptance_handover"))
    record = next((item for item in governance["records"] if item["id"] == acceptance_id), None)
    if not record: return config, ["The customer-acceptance record was not found."]
    errors: list[str] = []
    if record["status"] == "handed_over": errors.append("Implementation handover has already been confirmed.")
    if record.get("readiness", {}).get("status") not in {"Ready with conditions", "Ready for implementation"}: errors.append("Resolve the implementation-readiness blockers before handover.")
    required = {
        "handed_over_by": "Handed-over-by identity", "received_by": "Receiving person",
        "receiving_company": "Receiving team or company", "implementation_owner": "Implementation owner",
        "migration_planning_owner": "Migration-planning owner",
    }
    for key, label in required.items():
        if not _text(fields.get(key), 200): errors.append(f"{label} is required.")
    handover_date, valid_handover = _valid_date(fields.get("handover_date"), required=True)
    planned_date, valid_planned = _valid_date(fields.get("planned_start_date"))
    if not valid_handover: errors.append("A valid handover date is required.")
    if not valid_planned: errors.append("Provide a valid planned implementation start date or leave it blank.")
    if errors: return config, errors
    record["implementation_owner"] = _text(fields.get("implementation_owner"), 160)
    record["migration_planning_owner"] = _text(fields.get("migration_planning_owner"), 160)
    record["handover"] = {
        "id": uuid4().hex, "handed_over_by": _text(fields.get("handed_over_by"), 160),
        "received_by": _text(fields.get("received_by"), 160), "receiving_company": _text(fields.get("receiving_company"), 200),
        "handover_date": handover_date, "implementation_owner": record["implementation_owner"],
        "migration_planning_owner": record["migration_planning_owner"], "planned_start_date": planned_date,
        "comments": _multiline(fields.get("comments"), 4000), "confirmed_at": _now(),
        "baseline_artifact_id": record["artifact_id"], "baseline_version": record["sdd_version"],
    }
    record["status"] = "handed_over"
    _audit(governance, record, "implementation_handover_confirmed", record["handover"]["handed_over_by"], "Accepted SDD baseline handed over for implementation.")
    config["acceptance_handover"] = governance
    return config, []


def invalidate_for_new_revision(configuration: dict[str, Any], actor: str, new_version: str) -> dict[str, Any]:
    config = deepcopy(configuration); governance = normalize_acceptance_handover(config.get("acceptance_handover"))
    for record in governance["records"]:
        if record["status"] in {"accepted", "accepted_with_conditions", "handover_ready", "handed_over"} and not record["baseline_superseded"]:
            record["baseline_superseded"] = True; record["superseded_by_version"] = _text(new_version, 20)
            _audit(governance, record, "acceptance_invalidated_by_revision", actor, f"Historical acceptance retained; v{new_version} requires a new decision.")
    governance["active_acceptance_id"] = ""
    config["acceptance_handover"] = governance
    return config


def build_migration_planning_payload(configuration: dict[str, Any], snapshot: dict[str, Any], acceptance_id: str) -> tuple[dict[str, Any], list[str]]:
    governance = normalize_acceptance_handover(configuration.get("acceptance_handover")); record = find_acceptance(governance, acceptance_id=acceptance_id)
    if not record or record["status"] != "handed_over": return {}, ["Confirm implementation handover before starting migration planning."]
    scope = snapshot.get("scope") if isinstance(snapshot.get("scope"), dict) else {}
    clusters = snapshot.get("target_clusters") if isinstance(snapshot.get("target_clusters"), list) else []
    payload = {
        "schema_version": "1.0", "acceptance_id": record["id"], "assessment_id": record["assessment_id"],
        "accepted_sdd_version": record["sdd_version"], "selected_vm_names": list(snapshot.get("selected_vm_names") or []),
        "selected_scope": deepcopy(scope), "source_clusters": deepcopy(scope.get("source_clusters") or []),
        "target_ocvs_clusters": deepcopy(clusters),
        "vm_to_target_cluster_assignments": deepcopy(snapshot.get("vm_to_target_cluster_assignments") or snapshot.get("assignments") or []),
        "ocvs_shapes_and_nodes": [{"name": c.get("name"), "shape": c.get("shape") or c.get("selected_shape"), "nodes": c.get("nodes") or c.get("total_nodes")} for c in clusters],
        "storage_architecture": deepcopy(snapshot.get("sizing", {}).get("storage_architecture") if isinstance(snapshot.get("sizing"), dict) else ""),
        "application_dependencies": deepcopy(snapshot.get("application_dependencies") or []),
        "owners": {"implementation": record["implementation_owner"], "migration_planning": record["migration_planning_owner"]},
        "constraints": [item["comment"] for item in record["checklist"] if item["comment"]],
        "open_actions": deepcopy([item for item in record["actions"] if item["status"] != "closed"]),
        "proposed_implementation_date": record.get("handover", {}).get("planned_start_date", ""),
    }
    return payload, []


def _xlsx(rows: list[list[Any]], widths: list[int]) -> bytes:
    """Build a small standards-compliant XLSX without storing host paths or formulas."""
    def cell(row: int, col: int, value: Any, style: int = 0) -> str:
        letters = ""; n = col
        while n: n, rem = divmod(n - 1, 26); letters = chr(65 + rem) + letters
        return f'<c r="{letters}{row}" t="inlineStr" s="{style}"><is><t>{escape(str(value or ""))}</t></is></c>'
    sheet_rows = []
    for r_idx, values in enumerate(rows, 1):
        sheet_rows.append(f'<row r="{r_idx}">' + "".join(cell(r_idx, c_idx, value, 1 if r_idx == 1 else 0) for c_idx, value in enumerate(values, 1)) + "</row>")
    cols = "".join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>' for i, width in enumerate(widths, 1))
    sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols><sheetData>{''.join(sheet_rows)}</sheetData><autoFilter ref="A1:{chr(64 + min(len(widths),26))}{len(rows)}"/></worksheet>'''
    parts = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
        "xl/workbook.xml": '''<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Register" sheetId="1" r:id="rId1"/></sheets></workbook>''',
        "xl/_rels/workbook.xml.rels": '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>''',
        "xl/styles.xml": '''<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="0"/><fonts count="2"><font><sz val="10"/><name val="Aptos"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="10"/><name val="Aptos"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF005239"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles><dxfs count="0"/><tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/></styleSheet>''',
        "xl/worksheets/sheet1.xml": sheet,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items(): archive.writestr(name, content.encode("utf-8"))
    return output.getvalue()


def _summary_pdf(configuration: dict[str, Any], record: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    output = io.BytesIO(); customer = configuration.get("customer_document", {})
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet(); story = [Paragraph("OCVS Implementation Handover Summary", styles["Title"]), Spacer(1, 6*mm)]
    acceptance = record.get("acceptance", {}); handover = record.get("handover", {}); readiness = record.get("readiness", {})
    rows = [
        ["Customer", customer.get("customer_legal_name", "")], ["Project", customer.get("project_name", "")],
        ["Assessment", record["assessment_id"]], ["Accepted SDD version", record["sdd_version"]],
        ["Acceptance", acceptance.get("decision", "").replace("_", " ").title()], ["Decision date", acceptance.get("decision_date", "")],
        ["Readiness", readiness.get("status", "")], ["Handover date", handover.get("handover_date", "")],
        ["Implementation owner", record.get("implementation_owner", "")], ["Migration-planning owner", record.get("migration_planning_owner", "")],
        ["Open actions", readiness.get("open_actions", 0)], ["Blocking actions", readiness.get("blocking_actions", 0)],
    ]
    table = Table(rows, colWidths=[55*mm, 105*mm], repeatRows=0)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#E8F3EF")),("TEXTCOLOR",(0,0),(0,-1),colors.HexColor("#005239")),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#D9D9D9")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story.extend([table, Spacer(1, 7*mm), Paragraph("This package preserves the accepted SDD as the implementation baseline. Open actions remain governed in the acceptance workspace until closure.", styles["BodyText"])])
    doc.build(story); return output.getvalue()


def build_handover_package(root: Path, configuration: dict[str, Any], snapshot: dict[str, Any], acceptance_id: str) -> tuple[bytes, str, dict[str, Any]]:
    governance = normalize_acceptance_handover(configuration.get("acceptance_handover")); record = find_acceptance(governance, acceptance_id=acceptance_id)
    if not record or record["status"] != "handed_over": raise ValueError("Confirm implementation handover before generating the handover package.")
    artifact = find_version(configuration.get("delivery_governance", {}), artifact_id=record["artifact_id"])
    if not artifact or not artifact_integrity(root, artifact)["valid"]: raise ValueError("The delivered SDD failed integrity validation.")
    docx = read_artifact(root, artifact, "docx"); pdf = read_artifact(root, artifact, "pdf")
    d_manifest = delivery_manifest(configuration, snapshot, artifact)
    d_json = json.dumps(d_manifest, indent=2, ensure_ascii=False, sort_keys=True).encode()
    d_md = ("# OCVS SDD Delivery Manifest\n\n" + "\n".join(f"- **{k.replace('_',' ').title()}**: {v}" for k,v in d_manifest.items() if not isinstance(v, dict)) + "\n").encode()
    acceptance_json = json.dumps({"schema_version":"1.0", "acceptance_id":record["id"], "sdd_version":record["sdd_version"], **record["acceptance"]}, indent=2, ensure_ascii=False, sort_keys=True).encode()
    checklist_rows = [["Category","Item","Mandatory","Status","Owner","Target date","Comment","Evidence"]] + [[i["category"],i["label"],"Yes" if i["mandatory"] else "No",i["status"].replace("_"," ").title(),i["owner"],i["target_date"],i["comment"],i["evidence"]] for i in record["checklist"]]
    actions_rows = [["Action ID","Category","Description","Source","Owner","Due date","Priority","Status","Resolution","Closed date"]] + [[i["action_identifier"],i["category"],i["description"],i["source"].replace("_"," ").title(),i["owner"],i["due_date"],i["priority"].title(),i["status"].replace("_"," ").title(),i["resolution_comment"],i["closed_date"]] for i in record["actions"]]
    checklist_xlsx = _xlsx(checklist_rows, [24,42,12,16,22,14,36,28]); actions_xlsx = _xlsx(actions_rows, [14,22,46,24,22,14,12,15,34,14]); summary_pdf = _summary_pdf(configuration, record)
    files = {
        artifact["docx_filename"]: docx, artifact["pdf_filename"]: pdf,
        "delivery-manifest.json": d_json, "delivery-manifest.md": d_md,
        "customer-acceptance.json": acceptance_json, "implementation-readiness-checklist.xlsx": checklist_xlsx,
        "open-action-register.xlsx": actions_xlsx, "implementation-handover-summary.pdf": summary_pdf,
    }
    customer = configuration.get("customer_document") if isinstance(configuration.get("customer_document"), dict) else {}
    manifest = {
        "schema_version":"1.0", "customer":_text(customer.get("customer_legal_name"),240), "project":_text(customer.get("project_name"),240),
        "assessment_id":record["assessment_id"], "sdd_version":record["sdd_version"],
        "acceptance_status":record.get("acceptance",{}).get("decision", ""), "acceptance_date":record.get("acceptance",{}).get("decision_date", ""),
        "readiness_status":record.get("readiness",{}).get("status", ""), "completed_checklist_items":sum(1 for i in record["checklist"] if i["status"] in {"complete","not_applicable"}),
        "open_actions":sum(1 for i in record["actions"] if i["status"] != "closed"), "blocking_actions":sum(1 for i in record["actions"] if i["status"] != "closed" and (i["priority"] == "blocking" or i["status"] == "blocked")),
        "implementation_owner":record["implementation_owner"], "migration_planning_owner":record["migration_planning_owner"],
        "handover_date":record.get("handover",{}).get("handover_date", ""),
        "artifacts":{name:{"sha256":hashlib.sha256(data).hexdigest(),"size":len(data)} for name,data in files.items()},
    }
    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode(); files["handover-manifest.json"] = manifest_bytes
    output = io.BytesIO()
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items(): archive.writestr(Path(name).name, data)
    filename = f"{safe_component(customer.get('customer_legal_name'),'Customer')}_{safe_component(customer.get('project_name'),'Project')}_OCVS_SDD_v{record['sdd_version']}_Implementation_Handover.zip"
    return output.getvalue(), filename, manifest


def summary(configuration: dict[str, Any], root: Path) -> dict[str, Any]:
    governance = normalize_acceptance_handover(configuration.get("acceptance_handover"))
    records = []
    for record in reversed(governance["records"]):
        item = deepcopy(record); item["overdue_actions"] = [a["id"] for a in item["actions"] if action_overdue(a)]
        artifact = find_version(configuration.get("delivery_governance", {}), artifact_id=item["artifact_id"])
        item["artifact_integrity"] = artifact_integrity(root, artifact) if artifact else {"valid":False,"errors":["Baseline not found."]}
        item["delivery"] = {
            "date": _text((artifact or {}).get("delivery_date"), 20),
            "delivered_at": _text((artifact or {}).get("delivered_at"), 64),
            "delivered_by": _text((artifact or {}).get("delivered_by"), 160),
            "recipient_name": _text((artifact or {}).get("recipient_name"), 160),
            "recipient_company": _text((artifact or {}).get("recipient_company"), 200),
            "recipient_email": _text((artifact or {}).get("recipient_email"), 254),
        }
        item["outstanding_conditions"] = sum(
            1 for action in item["actions"]
            if action["source"] == "customer_condition" and action["status"] != "closed"
        )
        records.append(item)
    active = next((item for item in records if item["id"] == governance["active_acceptance_id"]), records[0] if records else None)
    return {**governance, "records":records, "active":active}
