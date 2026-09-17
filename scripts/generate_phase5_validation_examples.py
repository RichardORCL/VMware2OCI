#!/usr/bin/env python3
"""Generate representative Phase 5 SDD artifacts for visual validation."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_ocvs_sdd import generate
from services.ocvs_sdd_adapter import build_sdd_payload, normalize_sdd_configuration, readiness, snapshot_hash
from services.ocvs_sdd_review import approve, complete_review, finalize, normalize_review_workflow, request_changes, submit
from tests.test_ocvs_sdd_flask_integration import source_and_config


OUT = ROOT / "artifacts" / "phase5_validation"


def remove_fixture_markers(value):
    """Keep rendered QA artifacts realistic without leaking fixture labels."""
    if isinstance(value, dict):
        return {key: remove_fixture_markers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [remove_fixture_markers(item) for item in value]
    if isinstance(value, str):
        return (
            value.replace("Fictional", "Northstar")
            .replace("fictional", "northstar")
            .replace("@northstar.invalid", "@northstar-industries.com")
        )
    return value


def prepared(fixture: str):
    source, config = source_and_config(fixture)
    source = remove_fixture_markers(source)
    config = remove_fixture_markers(config)
    source["document"]["customer_name"] = "Northstar Industries"
    config["customer_document"].update({
        "customer_legal_name": "Northstar Industries SAS",
        "project_name": "OCVS Migration Programme",
        "document_author": "Alex Architect",
        "document_author_email": "alex@northstar-industries.com",
        "version_comment": "Technical design review",
    })
    config["source_snapshot_hash"] = snapshot_hash(source)
    config["review_workflow"] = normalize_review_workflow({
        "reviewers": [{"name": "Rita Reviewer", "email": "rita@northstar-industries.com", "role": "OCVS Technical Reviewer", "company": "Northstar Industries", "required": True}],
        "approvers": [{"name": "Adam Approver", "email": "adam@northstar-industries.com", "role": "Infrastructure Director", "company": "Northstar Industries"}],
    })
    return source, normalize_sdd_configuration(config)


def write_doc(name: str, source, config, *, final=False):
    payload = build_sdd_payload(source, config, final=final)
    input_path = OUT / f"{name}.json"
    output_path = OUT / f"{name}.docx"
    input_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    generate(ROOT / "document_templates" / "OCVS_SDD_template_automatable.docx", input_path, output_path, ROOT / "schemas" / "ocvs_sdd_generation.schema.json")
    input_path.unlink()
    return output_path


def reviewed(source, config):
    status = readiness(source, config, scenario_id="ocvs")
    config, errors = submit(config, source, status, "Alex Architect")
    assert not errors, errors
    reviewer = config["review_workflow"]["reviewers"][0]
    config, error = complete_review(config, reviewer["id"], reviewer["name"], "Technical review complete.")
    assert not error, error
    approver = config["review_workflow"]["approvers"][0]
    config, errors = approve(config, source, status, approver["id"], approver["name"], "Approved for customer delivery.")
    assert not errors, errors
    return config


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    single, draft = prepared("ocvs_sdd_single_cluster.json")
    status = readiness(single, draft, scenario_id="ocvs")
    awaiting, errors = submit(draft, single, status, "Alex Architect")
    assert not errors, errors
    write_doc("01_draft_awaiting_review", single, awaiting)
    changes, error = request_changes(awaiting, "Rita Reviewer", "Clarify the network validation approach.")
    assert not error, error
    write_doc("02_draft_changes_requested", single, changes)
    approved_single = reviewed(single, deepcopy(draft))
    write_doc("03_approved_single_cluster", single, approved_single)

    multi, multi_config = prepared("ocvs_sdd_multi_cluster.json")
    approved_multi = reviewed(multi, multi_config)
    write_doc("04_approved_multi_cluster", multi, approved_multi)

    final_config, errors = finalize(approved_single, single, readiness(single, approved_single, scenario_id="ocvs"), "Alex Architect")
    assert not errors, errors
    final_docx = write_doc("05_final_customer_ready", single, final_config, final=True)
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if not office:
        raise RuntimeError("LibreOffice is required for final PDF validation.")
    result = subprocess.run([office, "--headless", "--convert-to", "pdf", "--outdir", str(OUT), str(final_docx)], capture_output=True, text=True, timeout=120)
    if result.returncode or not final_docx.with_suffix(".pdf").exists():
        raise RuntimeError(result.stderr or result.stdout or "PDF conversion failed")
    print(OUT)


if __name__ == "__main__":
    main()
