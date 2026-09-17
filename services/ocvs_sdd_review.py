"""Controlled technical review and finalization for the Move-to-OCVS SDD."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


STATUSES = ("draft", "in_review", "changes_requested", "approved", "finalized", "delivered", "superseded")
COMMENT_SEVERITIES = ("informational", "warning", "blocking")
COMMENT_STATUSES = ("open", "resolved")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _email(value: Any) -> str:
    value = _text(value, 254)
    return value if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) else ""


def _person(value: Any, *, kind: str) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    status_options = {"pending", "completed"} if kind == "reviewer" else {"pending", "approved"}
    status = _text(raw.get("status"), 30).lower()
    return {
        "id": _text(raw.get("id"), 80) or uuid4().hex,
        "name": _text(raw.get("name"), 160),
        "email": _email(raw.get("email")),
        "role": _text(raw.get("role"), 160),
        "company": _text(raw.get("company"), 160),
        "required": bool(raw.get("required", True)),
        "status": status if status in status_options else "pending",
        "date": _text(raw.get("date"), 64),
        "comment": _text(raw.get("comment"), 2000),
    }


def normalize_review_workflow(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    status = _text(raw.get("status"), 40).lower()
    if status not in STATUSES:
        status = "draft"
    revision = _text(raw.get("current_revision"), 20)
    if not re.fullmatch(r"\d+\.\d+", revision):
        revision = "0.1"
    comments: list[dict[str, Any]] = []
    for item in raw.get("comments", []) if isinstance(raw.get("comments"), list) else []:
        if not isinstance(item, dict):
            continue
        severity = _text(item.get("severity"), 30).lower()
        comment_status = _text(item.get("status"), 30).lower()
        comments.append({
            "id": _text(item.get("id"), 80) or uuid4().hex,
            "section": _text(item.get("section"), 160) or "General",
            "author": _text(item.get("author"), 160),
            "comment": _text(item.get("comment"), 4000),
            "severity": severity if severity in COMMENT_SEVERITIES else "informational",
            "status": comment_status if comment_status in COMMENT_STATUSES else "open",
            "created_at": _text(item.get("created_at"), 64) or _now(),
            "resolved_at": _text(item.get("resolved_at"), 64),
            "resolution_note": _text(item.get("resolution_note"), 2000),
        })
    history = []
    for item in raw.get("approval_history", []) if isinstance(raw.get("approval_history"), list) else []:
        if not isinstance(item, dict):
            continue
        history.append({
            "id": _text(item.get("id"), 80) or uuid4().hex,
            "event": _text(item.get("event"), 80),
            "status": _text(item.get("status"), 40),
            "actor": _text(item.get("actor"), 160),
            "date": _text(item.get("date"), 64),
            "version": _text(item.get("version"), 20),
            "comment": _text(item.get("comment"), 2000),
            "source_snapshot_hash": _text(item.get("source_snapshot_hash"), 128),
        })
    return {
        "status": status,
        "submitted_at": _text(raw.get("submitted_at"), 64),
        "submitted_by": _text(raw.get("submitted_by"), 160),
        "current_revision": revision,
        "reviewers": [_person(item, kind="reviewer") for item in raw.get("reviewers", []) if isinstance(item, dict)] if isinstance(raw.get("reviewers"), list) else [],
        "approvers": [_person(item, kind="approver") for item in raw.get("approvers", []) if isinstance(item, dict)] if isinstance(raw.get("approvers"), list) else [],
        "comments": comments,
        "approval_history": history,
        "finalized_at": _text(raw.get("finalized_at"), 64),
        "finalized_by": _text(raw.get("finalized_by"), 160),
        "final_version": _text(raw.get("final_version"), 20),
        "source_snapshot_hash": _text(raw.get("source_snapshot_hash"), 128),
        "content_hash": _text(raw.get("content_hash"), 128),
        "stale_reason": _text(raw.get("stale_reason"), 1000),
    }


def review_content_hash(snapshot: dict[str, Any], configuration: dict[str, Any]) -> str:
    config = deepcopy(configuration if isinstance(configuration, dict) else {})
    config.pop("review_workflow", None)
    config.pop("delivery_governance", None)
    for key in ("validation_results", "last_saved_at", "status"):
        config.pop(key, None)
    customer = config.get("customer_document")
    if isinstance(customer, dict):
        customer.pop("version", None)
        customer.pop("version_comment", None)
    wizard = config.get("wizard")
    if isinstance(wizard, dict):
        config["wizard"] = {"completed_steps": sorted(wizard.get("completed_steps") or [])}
    stable = json.dumps({"snapshot": snapshot, "configuration": config}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _history(workflow: dict[str, Any], event: str, actor: str, *, comment: str = "", version: str = "") -> None:
    workflow["approval_history"].append({
        "id": uuid4().hex, "event": event, "status": workflow["status"],
        "actor": _text(actor, 160), "date": _now(),
        "version": version or workflow["current_revision"], "comment": _text(comment, 2000),
        "source_snapshot_hash": workflow.get("source_snapshot_hash", ""),
    })


def _next_draft(version: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)", version or "")
    if not match or int(match.group(1)) > 0:
        return "0.1"
    return f"0.{int(match.group(2)) + 1}"


def _next_final(workflow: dict[str, Any]) -> str:
    approved = [item.get("version", "") for item in workflow.get("approval_history", []) if item.get("event") in {"approved", "finalized"}]
    parsed = [tuple(map(int, value.split("."))) for value in approved if re.fullmatch(r"\d+\.\d+", value)]
    finals = [value for value in parsed if value[0] >= 1]
    if not finals:
        return "1.0"
    major, minor = max(finals)
    return f"{major}.{minor + 1}"


def invalidate_if_stale(configuration: dict[str, Any], snapshot: dict[str, Any], reason: str = "The selected workload, sizing, pricing, topology, or SDD configuration changed.") -> tuple[dict[str, Any], bool]:
    config = deepcopy(configuration)
    workflow = normalize_review_workflow(config.get("review_workflow"))
    current_hash = review_content_hash(snapshot, config)
    changed = bool(workflow.get("content_hash") and workflow["content_hash"] != current_hash)
    if changed and workflow["status"] in {"finalized", "delivered", "superseded"}:
        governance = deepcopy(config.get("delivery_governance")) if isinstance(config.get("delivery_governance"), dict) else {}
        governance["unpublished_changes"] = True
        workflow["stale_reason"] = "The assessment changed after finalization. Start a new SDD revision to publish the changes."
        config["delivery_governance"] = governance
    elif changed and workflow["status"] in {"in_review", "approved"}:
        workflow["status"] = "changes_requested"
        workflow["stale_reason"] = reason
        for approver in workflow["approvers"]:
            approver.update({"status": "pending", "date": "", "comment": ""})
        _history(workflow, "approval_invalidated", "System", comment=reason)
    config["review_workflow"] = workflow
    config["status"] = workflow["status"]
    return config, changed


def summary(configuration: dict[str, Any], snapshot: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    workflow = normalize_review_workflow(configuration.get("review_workflow"))
    current_hash = review_content_hash(snapshot, configuration) if snapshot else ""
    stale = bool(workflow.get("content_hash") and current_hash and workflow["content_hash"] != current_hash)
    blocking = [item for item in workflow["comments"] if item["severity"] == "blocking" and item["status"] == "open"]
    required_reviewers = [item for item in workflow["reviewers"] if item.get("required", True)]
    completed_reviewers = [item for item in required_reviewers if item["status"] == "completed"]
    approved = [item for item in workflow["approvers"] if item["status"] == "approved"]
    return {
        "workflow": workflow, "status": workflow["status"], "stale": stale,
        "open_comments": [item for item in workflow["comments"] if item["status"] == "open"],
        "open_blocking_comments": blocking,
        "reviewer_completed": len(completed_reviewers), "reviewer_required": len(required_reviewers),
        "approver_completed": len(approved), "approver_total": len(workflow["approvers"]),
        "can_submit": bool(readiness.get("ready") and not stale and workflow["reviewers"] and workflow["status"] in {"draft", "changes_requested"}),
        "can_approve": bool(workflow["status"] == "in_review" and readiness.get("ready") and not stale and not blocking and required_reviewers and len(completed_reviewers) == len(required_reviewers) and workflow["approvers"]),
        "can_finalize": bool(workflow["status"] == "approved" and readiness.get("ready") and not stale),
        "current_hash": current_hash,
    }


def submit(configuration: dict[str, Any], snapshot: dict[str, Any], readiness: dict[str, Any], actor: str) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration)
    workflow = normalize_review_workflow(config.get("review_workflow"))
    errors = []
    if not readiness.get("ready"):
        errors.extend(readiness.get("blocking_errors") or ["The SDD is not ready for review."])
    if not workflow["reviewers"]:
        errors.append("Assign at least one technical reviewer before submission.")
    if workflow["status"] not in {"draft", "changes_requested"}:
        errors.append("Only a Draft or Changes Requested SDD can be submitted.")
    if errors:
        return config, list(dict.fromkeys(errors))
    if workflow["status"] == "changes_requested":
        workflow["current_revision"] = _next_draft(workflow["current_revision"])
    workflow.update({
        "status": "in_review", "submitted_at": _now(), "submitted_by": _text(actor, 160),
        "source_snapshot_hash": str(readiness.get("source_snapshot_hash") or ""),
        "content_hash": review_content_hash(snapshot, config), "stale_reason": "",
    })
    for person in workflow["reviewers"]:
        person.update({"status": "pending", "date": "", "comment": ""})
    for person in workflow["approvers"]:
        person.update({"status": "pending", "date": "", "comment": ""})
    _history(workflow, "submitted_for_review", actor)
    config.update({"review_workflow": workflow, "status": workflow["status"]})
    config.setdefault("customer_document", {})["version"] = workflow["current_revision"]
    return config, []


def add_comment(configuration: dict[str, Any], *, section: str, author: str, comment: str, severity: str) -> tuple[dict[str, Any], str]:
    config = deepcopy(configuration)
    workflow = normalize_review_workflow(config.get("review_workflow"))
    if workflow["status"] not in {"in_review", "changes_requested"} or not _text(comment):
        return config, "A review comment can only be added during review and cannot be empty."
    severity = severity if severity in COMMENT_SEVERITIES else "informational"
    workflow["comments"].append({
        "id": uuid4().hex, "section": _text(section, 160) or "General", "author": _text(author, 160),
        "comment": _text(comment), "severity": severity, "status": "open", "created_at": _now(),
        "resolved_at": "", "resolution_note": "",
    })
    _history(workflow, "comment_added", author, comment=f"{severity.title()} comment added to {_text(section, 160) or 'General'}.")
    config["review_workflow"] = workflow
    return config, ""


def resolve_comment(configuration: dict[str, Any], comment_id: str, actor: str, note: str) -> tuple[dict[str, Any], str]:
    config = deepcopy(configuration)
    workflow = normalize_review_workflow(config.get("review_workflow"))
    if not _text(note):
        return config, "A resolution note is required."
    target = next((item for item in workflow["comments"] if item["id"] == comment_id), None)
    if not target:
        return config, "The selected review comment was not found."
    target.update({"status": "resolved", "resolved_at": _now(), "resolution_note": _text(note, 2000)})
    _history(workflow, "comment_resolved", actor, comment=f"Comment in {target['section']} resolved.")
    config["review_workflow"] = workflow
    return config, ""


def complete_review(configuration: dict[str, Any], reviewer_id: str, actor: str, comment: str = "") -> tuple[dict[str, Any], str]:
    config = deepcopy(configuration)
    workflow = normalize_review_workflow(config.get("review_workflow"))
    if workflow["status"] != "in_review":
        return config, "Reviewer completion is available only while the SDD is In Review."
    target = next((item for item in workflow["reviewers"] if item["id"] == reviewer_id), None)
    if not target:
        return config, "The selected reviewer was not found."
    target.update({"status": "completed", "date": _now(), "comment": _text(comment, 2000)})
    _history(workflow, "review_completed", actor or target["name"], comment=f"Review completed by {target['name']}.")
    config["review_workflow"] = workflow
    return config, ""


def request_changes(configuration: dict[str, Any], actor: str, comment: str = "") -> tuple[dict[str, Any], str]:
    config = deepcopy(configuration)
    workflow = normalize_review_workflow(config.get("review_workflow"))
    if workflow["status"] != "in_review":
        return config, "Changes can be requested only while the SDD is In Review."
    workflow["status"] = "changes_requested"
    _history(workflow, "changes_requested", actor, comment=comment)
    config.update({"review_workflow": workflow, "status": workflow["status"]})
    return config, ""


def approve(configuration: dict[str, Any], snapshot: dict[str, Any], readiness: dict[str, Any], approver_id: str, actor: str, comment: str = "") -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration)
    state = summary(config, snapshot, readiness)
    workflow = state["workflow"]
    errors = []
    if not state["can_approve"]:
        if workflow["status"] != "in_review": errors.append("The SDD must be In Review before approval.")
        if state["stale"] or not readiness.get("ready"): errors.append("The SDD configuration or sizing is stale or not ready.")
        if state["open_blocking_comments"]: errors.append("Resolve every blocking review comment before approval.")
        if state["reviewer_completed"] != state["reviewer_required"]: errors.append("Every mandatory reviewer must complete their review.")
        if not workflow["approvers"]: errors.append("Assign at least one approver.")
    target = next((item for item in workflow["approvers"] if item["id"] == approver_id), None)
    if not target:
        errors.append("Select a configured approver.")
    if errors:
        return config, list(dict.fromkeys(errors))
    version = _next_final(workflow)
    target.update({"status": "approved", "date": _now(), "comment": _text(comment, 2000)})
    workflow.update({"status": "approved", "current_revision": version, "content_hash": state["current_hash"], "stale_reason": ""})
    _history(workflow, "approved", actor or target["name"], comment=comment, version=version)
    config.update({"review_workflow": workflow, "status": workflow["status"]})
    config.setdefault("customer_document", {})["version"] = version
    return config, []


def final_validation(configuration: dict[str, Any], snapshot: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    state = summary(configuration, snapshot, readiness)
    workflow = state["workflow"]
    errors: list[str] = []
    if workflow["status"] != "approved": errors.append("Approve the SDD before finalization.")
    if state["stale"] or not readiness.get("ready"): errors.append("The approved SDD is stale or no longer passes readiness validation.")
    if state["open_blocking_comments"]: errors.append("Resolve every blocking review comment before finalization.")
    if not any(item["status"] == "approved" for item in workflow["approvers"]): errors.append("A configured approver must approve the SDD.")
    customer = configuration.get("customer_document", {}) if isinstance(configuration.get("customer_document"), dict) else {}
    sample_pattern = re.compile(r"\b(sample|fictional|example|test customer|acme)\b", re.I)
    for field in ("customer_legal_name", "project_name", "document_author"):
        value = _text(customer.get(field), 500)
        if not value or sample_pattern.search(value): errors.append(f"Replace sample or missing {field.replace('_', ' ')} before finalization.")
    email = _email(customer.get("document_author_email"))
    if not email or email.lower().endswith("@example.com"): errors.append("Provide a valid non-sample document author email before finalization.")
    return list(dict.fromkeys(errors))


def finalize(configuration: dict[str, Any], snapshot: dict[str, Any], readiness: dict[str, Any], actor: str) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration)
    errors = final_validation(config, snapshot, readiness)
    if errors:
        return config, errors
    workflow = normalize_review_workflow(config.get("review_workflow"))
    version = workflow["current_revision"] if re.fullmatch(r"[1-9]\d*\.\d+", workflow["current_revision"]) else _next_final(workflow)
    workflow.update({"status": "finalized", "finalized_at": _now(), "finalized_by": _text(actor, 160), "final_version": version})
    _history(workflow, "finalized", actor, version=version)
    config.update({"review_workflow": workflow, "status": workflow["status"]})
    config.setdefault("customer_document", {})["version"] = version
    return config, []
