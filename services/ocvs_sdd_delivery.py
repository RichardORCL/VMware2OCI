"""Immutable artifact storage and customer-delivery governance for OCVS SDDs."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


MAX_ARTIFACT_BYTES = 50 * 1024 * 1024
ARTIFACT_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
VERSION_PATTERN = re.compile(r"^[1-9]\d*\.\d+$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _email(value: Any) -> str:
    candidate = _text(value, 254)
    return candidate if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", candidate) else ""


def safe_component(value: Any, fallback: str = "Document", limit: int = 70) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", _text(value, 300)).strip("._-")
    clean = re.sub(r"_+", "_", clean)
    return (clean or fallback)[:limit].rstrip("._-") or fallback


def _event(value: Any) -> dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    return {
        "id": _text(raw.get("id"), 80) or uuid4().hex,
        "event": _text(raw.get("event"), 80),
        "timestamp": _text(raw.get("timestamp"), 64),
        "actor": _text(raw.get("actor"), 160),
        "version": _text(raw.get("version"), 20),
        "details": _text(raw.get("details"), 500),
    }


def _version(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    status = _text(raw.get("status"), 30).lower()
    if status not in {"finalized", "delivered", "superseded"}:
        status = "finalized"
    return {
        "artifact_id": _text(raw.get("artifact_id"), 80),
        "assessment_id": _text(raw.get("assessment_id"), 100),
        "document_type": "ocvs_sdd",
        "version": _text(raw.get("version"), 20),
        "status": status,
        "created_at": _text(raw.get("created_at"), 64),
        "created_by": _text(raw.get("created_by"), 160),
        "finalized_at": _text(raw.get("finalized_at"), 64),
        "finalized_by": _text(raw.get("finalized_by"), 160),
        "approved_at": _text(raw.get("approved_at"), 64),
        "approved_by": _text(raw.get("approved_by"), 160),
        "delivered_at": _text(raw.get("delivered_at"), 64),
        "delivery_date": _text(raw.get("delivery_date"), 20),
        "delivered_by": _text(raw.get("delivered_by"), 160),
        "recipient_name": _text(raw.get("recipient_name"), 160),
        "recipient_company": _text(raw.get("recipient_company"), 200),
        "recipient_email": _email(raw.get("recipient_email")),
        "delivery_comment": _text(raw.get("delivery_comment"), 2000),
        "revision_reason": _text(raw.get("revision_reason"), 2000),
        "replaces_version": _text(raw.get("replaces_version"), 20),
        "superseded_by": _text(raw.get("superseded_by"), 20),
        "docx_filename": Path(_text(raw.get("docx_filename"), 240)).name,
        "pdf_filename": Path(_text(raw.get("pdf_filename"), 240)).name,
        "docx_checksum": _text(raw.get("docx_checksum"), 128),
        "pdf_checksum": _text(raw.get("pdf_checksum"), 128),
        "docx_size": int(raw.get("docx_size") or 0),
        "pdf_size": int(raw.get("pdf_size") or 0),
        "source_sizing_timestamp": _text(raw.get("source_sizing_timestamp"), 64),
        "workload_summary": deepcopy(raw.get("workload_summary")) if isinstance(raw.get("workload_summary"), dict) else {},
        "topology": _text(raw.get("topology"), 40),
        "target_cluster_count": int(raw.get("target_cluster_count") or 0),
        "total_nodes": int(raw.get("total_nodes") or 0),
        "commitment_term": _text(raw.get("commitment_term"), 120),
        "review_snapshot": deepcopy(raw.get("review_snapshot")) if isinstance(raw.get("review_snapshot"), dict) else {},
    }


def normalize_delivery_governance(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    versions = [_version(item) for item in raw.get("versions", []) if isinstance(item, dict)] if isinstance(raw.get("versions"), list) else []
    # Keep the first immutable metadata record for a version and artifact id.
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in versions:
        key = (item["version"], item["artifact_id"])
        if item["version"] and key not in seen:
            seen.add(key)
            unique.append(item)
    return {
        "schema_version": "1.0",
        "versions": unique,
        "audit_events": [_event(item) for item in raw.get("audit_events", []) if isinstance(item, dict)] if isinstance(raw.get("audit_events"), list) else [],
        "current_working_revision": _text(raw.get("current_working_revision"), 30) or "0.1-draft",
        "latest_finalized_version": _text(raw.get("latest_finalized_version"), 20),
        "latest_delivered_version": _text(raw.get("latest_delivered_version"), 20),
        "based_on_version": _text(raw.get("based_on_version"), 20),
        "unpublished_changes": bool(raw.get("unpublished_changes", False)),
    }


def _audit(governance: dict[str, Any], event: str, actor: str, version: str, details: str = "") -> None:
    governance["audit_events"].append({
        "id": uuid4().hex, "event": event, "timestamp": _now(),
        "actor": _text(actor, 160), "version": _text(version, 20), "details": _text(details, 500),
    })


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_bytes(data: bytes, kind: str) -> None:
    if not data or len(data) > MAX_ARTIFACT_BYTES:
        raise ValueError(f"The {kind.upper()} artifact is empty or exceeds the supported size.")
    if kind == "docx" and not data.startswith(b"PK"):
        raise ValueError("The generated DOCX artifact is invalid.")
    if kind == "pdf" and not data.startswith(b"%PDF"):
        raise ValueError("The generated PDF artifact is invalid.")


def _artifact_directory(root: Path, artifact_id: str, *, create: bool = False) -> Path:
    if not ARTIFACT_ID_PATTERN.fullmatch(str(artifact_id or "")):
        raise ValueError("Invalid SDD artifact identifier.")
    if root.is_symlink():
        raise ValueError("The SDD artifact store cannot be a symbolic link.")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    directory = (root / artifact_id).resolve()
    if directory.parent != root:
        raise ValueError("Invalid SDD artifact location.")
    if create:
        directory.mkdir(mode=0o700, exist_ok=False)
    return directory


def _atomic_create(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _approval(workflow: dict[str, Any]) -> tuple[str, str]:
    approvals = [item for item in workflow.get("approval_history", []) if isinstance(item, dict) and item.get("event") == "approved"]
    latest = approvals[-1] if approvals else {}
    return _text(latest.get("date"), 64), _text(latest.get("actor"), 160)


def store_final_artifacts(
    root: Path,
    configuration: dict[str, Any],
    snapshot: dict[str, Any],
    docx_bytes: bytes,
    pdf_bytes: bytes,
    actor: str,
) -> dict[str, Any]:
    """Persist a finalized DOCX/PDF pair exactly once and return updated governance."""
    _validate_bytes(docx_bytes, "docx")
    _validate_bytes(pdf_bytes, "pdf")
    workflow = configuration.get("review_workflow") if isinstance(configuration.get("review_workflow"), dict) else {}
    version = _text(workflow.get("final_version") or workflow.get("current_revision"), 20)
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("A finalized document version is required before artifact storage.")
    governance = normalize_delivery_governance(configuration.get("delivery_governance"))
    if any(item["version"] == version for item in governance["versions"]):
        raise ValueError("This finalized SDD version already has immutable artifacts.")
    customer = configuration.get("customer_document") if isinstance(configuration.get("customer_document"), dict) else {}
    base = "_".join((
        safe_component(customer.get("customer_legal_name"), "Customer"),
        safe_component(customer.get("project_name"), "Project"),
        "OCVS_SDD", f"v{version}",
    ))
    docx_name, pdf_name = f"{base}.docx", f"{base}.pdf"
    artifact_id = uuid4().hex
    directory = _artifact_directory(root, artifact_id, create=True)
    try:
        _atomic_create(directory / docx_name, docx_bytes)
        _atomic_create(directory / pdf_name, pdf_bytes)
    except Exception:
        for child in directory.iterdir():
            child.unlink(missing_ok=True)
        directory.rmdir()
        raise
    approved_at, approved_by = _approval(workflow)
    scope = snapshot.get("scope") if isinstance(snapshot.get("scope"), dict) else {}
    sizing = snapshot.get("sizing") if isinstance(snapshot.get("sizing"), dict) else {}
    commercial = snapshot.get("commercial") if isinstance(snapshot.get("commercial"), dict) else {}
    record = _version({
        "artifact_id": artifact_id,
        "assessment_id": configuration.get("source_assessment_id"),
        "version": version, "status": "finalized", "created_at": _now(), "created_by": actor,
        "finalized_at": workflow.get("finalized_at") or _now(), "finalized_by": workflow.get("finalized_by") or actor,
        "approved_at": approved_at, "approved_by": approved_by,
        "docx_filename": docx_name, "pdf_filename": pdf_name,
        "docx_checksum": _checksum(docx_bytes), "pdf_checksum": _checksum(pdf_bytes),
        "docx_size": len(docx_bytes), "pdf_size": len(pdf_bytes),
        "source_sizing_timestamp": snapshot.get("source_step4_updated_at") or snapshot.get("saved_at"),
        "workload_summary": {
            "selected_vm_count": scope.get("selected_vm_count", 0),
            "selected_vcpu": scope.get("selected_vcpu", 0),
            "selected_ram_gb": scope.get("selected_ram_gb", 0),
            "selected_storage_tb": scope.get("selected_storage_tb", 0),
        },
        "topology": sizing.get("topology"), "target_cluster_count": sizing.get("target_cluster_count", 0),
        "total_nodes": sizing.get("total_nodes", 0),
        "commitment_term": commercial.get("commitment_term") or sizing.get("commitment_term"),
        "revision_reason": customer.get("version_comment"),
        "replaces_version": governance.get("based_on_version"),
        "review_snapshot": {"reviewers": deepcopy(workflow.get("reviewers", [])), "approvers": deepcopy(workflow.get("approvers", [])), "comments": deepcopy(workflow.get("comments", [])), "approval_history": deepcopy(workflow.get("approval_history", []))},
    })
    governance["versions"].append(record)
    governance.update({"latest_finalized_version": version, "current_working_revision": version, "unpublished_changes": False})
    _audit(governance, "artifact_created", actor, version, "Final DOCX and PDF stored with SHA-256 integrity metadata.")
    _audit(governance, "finalized", actor, version)
    return governance


def find_version(governance: dict[str, Any], *, artifact_id: str = "", version: str = "") -> dict[str, Any] | None:
    data = normalize_delivery_governance(governance)
    return next((item for item in data["versions"] if (artifact_id and item["artifact_id"] == artifact_id) or (version and item["version"] == version)), None)


def read_artifact(root: Path, record: dict[str, Any], kind: str) -> bytes:
    if kind not in {"docx", "pdf"}:
        raise ValueError("Unsupported SDD artifact type.")
    normalized = _version(record)
    directory = _artifact_directory(root, normalized["artifact_id"])
    filename = normalized[f"{kind}_filename"]
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file() or path.is_symlink():
        raise FileNotFoundError("The requested SDD artifact is not available on this host.")
    data = path.read_bytes()
    _validate_bytes(data, kind)
    if _checksum(data) != normalized[f"{kind}_checksum"]:
        raise ValueError("The requested SDD artifact failed integrity validation.")
    return data


def artifact_integrity(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    available = {"docx": False, "pdf": False}
    for kind in ("docx", "pdf"):
        try:
            read_artifact(root, record, kind)
            available[kind] = True
        except (OSError, ValueError) as exc:
            errors.append(f"{kind.upper()}: {exc}")
    return {
        "valid": not errors,
        "errors": errors,
        "docx_available": available["docx"],
        "pdf_available": available["pdf"],
    }


def delivery_manifest(configuration: dict[str, Any], snapshot: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    customer = configuration.get("customer_document") if isinstance(configuration.get("customer_document"), dict) else {}
    item = _version(record)
    return {
        "schema_version": "1.0", "customer": _text(customer.get("customer_legal_name"), 240),
        "project": _text(customer.get("project_name"), 240), "assessment_id": item["assessment_id"],
        "document_type": "ocvs_sdd", "version": item["version"], "status": item["status"],
        "finalization_date": item["finalized_at"], "finalized_by": item["finalized_by"],
        "approval_date": item["approved_at"], "approved_by": item["approved_by"],
        "delivery_date": item["delivered_at"], "delivered_by": item["delivered_by"],
        "docx": {"filename": item["docx_filename"], "sha256": item["docx_checksum"]},
        "pdf": {"filename": item["pdf_filename"], "sha256": item["pdf_checksum"]},
        "source_sizing_timestamp": item["source_sizing_timestamp"], "selected_workload": item["workload_summary"],
        "ocvs_topology": item["topology"], "target_cluster_count": item["target_cluster_count"],
        "total_ocvs_nodes": item["total_nodes"], "commitment_term": item["commitment_term"],
        "delivery_comment": item["delivery_comment"],
    }


def build_delivery_package(root: Path, configuration: dict[str, Any], snapshot: dict[str, Any], record: dict[str, Any]) -> tuple[bytes, str]:
    item = _version(record)
    docx = read_artifact(root, item, "docx")
    pdf = read_artifact(root, item, "pdf")
    manifest = delivery_manifest(configuration, snapshot, item)
    json_bytes = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
    markdown = "# OCVS SDD Delivery Manifest\n\n" + "\n".join(f"- **{key.replace('_', ' ').title()}**: {value}" for key, value in manifest.items() if not isinstance(value, dict)) + "\n"
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(item["docx_filename"], docx)
        archive.writestr(item["pdf_filename"], pdf)
        archive.writestr("delivery-manifest.json", json_bytes)
        archive.writestr("delivery-manifest.md", markdown.encode("utf-8"))
    customer = configuration.get("customer_document") if isinstance(configuration.get("customer_document"), dict) else {}
    filename = f"{safe_component(customer.get('customer_legal_name'), 'Customer')}_{safe_component(customer.get('project_name'), 'Project')}_OCVS_SDD_v{item['version']}_Delivery.zip"
    return target.getvalue(), filename


def mark_delivered(configuration: dict[str, Any], root: Path, artifact_id: str, actor: str, delivery_date: str, recipient: dict[str, Any], comment: str = "") -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration)
    governance = normalize_delivery_governance(config.get("delivery_governance"))
    record = find_version(governance, artifact_id=artifact_id)
    errors = []
    if not record or record["status"] != "finalized": errors.append("Only a finalized SDD can be marked as delivered.")
    if not _text(actor, 160): errors.append("Delivered-by identity is required.")
    clean_delivery_date = _text(delivery_date, 20)
    try:
        datetime.strptime(clean_delivery_date, "%Y-%m-%d")
    except ValueError:
        errors.append("A valid delivery date is required.")
    email = _text(recipient.get("email"), 254)
    if email and not _email(email): errors.append("Provide a valid recipient e-mail address or leave it blank.")
    if record and not artifact_integrity(root, record)["valid"]: errors.append("Artifact integrity validation failed; delivery is blocked.")
    if errors: return config, errors
    target = next(item for item in governance["versions"] if item["artifact_id"] == artifact_id)
    target.update({
        "status": "delivered", "delivered_at": f"{clean_delivery_date}T00:00:00+00:00",
        "delivery_date": clean_delivery_date, "delivered_by": _text(actor, 160),
        "recipient_name": _text(recipient.get("name"), 160), "recipient_company": _text(recipient.get("company"), 200),
        "recipient_email": _email(email), "delivery_comment": _text(comment, 2000),
    })
    governance["latest_delivered_version"] = target["version"]
    _audit(governance, "marked_delivered", actor, target["version"], "Customer delivery recorded after integrity validation.")
    config["delivery_governance"] = governance
    workflow = config.get("review_workflow") if isinstance(config.get("review_workflow"), dict) else {}
    if workflow.get("final_version") == target["version"]:
        workflow["status"] = "delivered"
        config["status"] = "delivered"
    config["review_workflow"] = workflow
    return config, []


def start_new_revision(configuration: dict[str, Any], actor: str, reason: str) -> tuple[dict[str, Any], list[str]]:
    config = deepcopy(configuration)
    governance = normalize_delivery_governance(config.get("delivery_governance"))
    base = governance["latest_delivered_version"] or governance["latest_finalized_version"]
    if not base: return config, ["Finalize an SDD before starting a governed revision."]
    if not _text(actor, 160): return config, ["The person starting the revision is required."]
    if not _text(reason, 2000): return config, ["A revision reason is required."]
    match = VERSION_PATTERN.fullmatch(base)
    if not match: return config, ["The previous finalized version is invalid."]
    major, minor = map(int, base.split(".")); next_version = f"{major}.{minor + 1}"
    workflow = config.get("review_workflow") if isinstance(config.get("review_workflow"), dict) else {}
    workflow.update({"status": "draft", "current_revision": next_version, "final_version": "", "finalized_at": "", "finalized_by": "", "content_hash": "", "stale_reason": ""})
    workflow["comments"] = []
    for key in ("reviewers", "approvers"):
        for person in workflow.get(key, []): person.update({"status": "pending", "date": "", "comment": ""})
    workflow.setdefault("approval_history", []).append({"id": uuid4().hex, "event": "revision_started", "status": "draft", "actor": _text(actor, 160), "date": _now(), "version": next_version, "comment": _text(reason, 2000), "source_snapshot_hash": ""})
    governance.update({"current_working_revision": f"{next_version}-draft", "based_on_version": base, "unpublished_changes": True})
    _audit(governance, "revision_started", actor, next_version, f"Based on v{base}: {_text(reason, 300)}")
    config.update({"review_workflow": workflow, "delivery_governance": governance, "status": "draft"})
    config.setdefault("customer_document", {})["version"] = next_version
    config["customer_document"]["version_comment"] = _text(reason, 1000)
    return config, []


def supersede_version(configuration: dict[str, Any], version: str, actor: str) -> tuple[dict[str, Any], str]:
    config = deepcopy(configuration); governance = normalize_delivery_governance(config.get("delivery_governance"))
    if not _text(actor, 160):
        return config, "The person superseding the version is required."
    latest = governance["latest_delivered_version"]
    target = find_version(governance, version=version)
    if not target or target["status"] != "delivered" or not latest or latest == version:
        return config, "Only an older delivered SDD can be marked as superseded."
    stored = next(item for item in governance["versions"] if item["version"] == version)
    stored.update({"status": "superseded", "superseded_by": latest})
    _audit(governance, "version_superseded", actor, version, f"Superseded by v{latest}.")
    config["delivery_governance"] = governance
    return config, ""


def governance_summary(configuration: dict[str, Any], root: Path) -> dict[str, Any]:
    governance = normalize_delivery_governance(configuration.get("delivery_governance"))
    versions = []
    for item in reversed(governance["versions"]):
        status = artifact_integrity(root, item)
        versions.append({**item, "integrity": "Valid" if status["valid"] else "Unavailable or invalid", **status})
    return {**governance, "versions": versions, "has_artifacts": bool(versions)}


def record_audit(configuration: dict[str, Any], event: str, actor: str, version: str, details: str = "") -> dict[str, Any]:
    """Append one non-sensitive governance event without changing artifacts."""
    config = deepcopy(configuration)
    governance = normalize_delivery_governance(config.get("delivery_governance"))
    _audit(governance, event, actor, version, details)
    config["delivery_governance"] = governance
    return config
