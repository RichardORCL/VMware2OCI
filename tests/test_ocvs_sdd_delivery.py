from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path

from services.ocvs_sdd_adapter import normalize_sdd_configuration
from services.ocvs_sdd_delivery import (
    artifact_integrity,
    build_delivery_package,
    delivery_manifest,
    find_version,
    governance_summary,
    mark_delivered,
    normalize_delivery_governance,
    read_artifact,
    record_audit,
    safe_component,
    start_new_revision,
    store_final_artifacts,
    supersede_version,
)
from tests.test_ocvs_sdd_flask_integration import source_and_config


DOCX = b"PK\x03\x04immutable-docx"
PDF = b"%PDF-1.7\nimmutable-pdf"


def finalized_configuration(version: str = "1.0") -> tuple[dict, dict]:
    source, config = source_and_config()
    config = normalize_sdd_configuration(config)
    config["source_assessment_id"] = "assessment-123"
    config["customer_document"].update({
        "customer_legal_name": "Northstar / Industries",
        "project_name": "Move to OCVS",
        "document_author": "Alex Architect",
        "version": version,
        "version_comment": "Approved customer baseline",
    })
    config["review_workflow"].update({
        "status": "finalized",
        "current_revision": version,
        "final_version": version,
        "finalized_at": "2026-09-17T09:00:00+00:00",
        "finalized_by": "Alex Architect",
        "reviewers": [{"id": "reviewer-1", "name": "Rita Reviewer", "status": "completed"}],
        "approvers": [{"id": "approver-1", "name": "Adam Approver", "status": "approved"}],
        "comments": [],
        "approval_history": [{
            "id": "approval-1", "event": "approved", "status": "approved",
            "actor": "Adam Approver", "date": "2026-09-17T08:30:00+00:00",
            "version": version, "comment": "Approved", "source_snapshot_hash": "hash",
        }],
    })
    return config, source


class OCVSSDDDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "private-sdd-artifacts"
        self.config, self.snapshot = finalized_configuration()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def stored(self) -> dict:
        config = deepcopy(self.config)
        config["delivery_governance"] = store_final_artifacts(
            self.root, config, self.snapshot, DOCX, PDF, "Alex Architect",
        )
        return config

    def delivered(self) -> dict:
        config = self.stored()
        artifact_id = config["delivery_governance"]["versions"][0]["artifact_id"]
        config, errors = mark_delivered(
            config, self.root, artifact_id, "Alex Architect", "2026-09-17",
            {"name": "Casey Customer", "company": "Northstar", "email": "casey@example.org"},
            "Delivered through the approved channel.",
        )
        self.assertFalse(errors)
        return config

    def test_01_old_assessment_upgrades_with_safe_defaults(self):
        normalized = normalize_sdd_configuration({})
        governance = normalized["delivery_governance"]
        self.assertEqual(governance["schema_version"], "1.0")
        self.assertEqual(governance["versions"], [])
        self.assertEqual(governance["current_working_revision"], "0.1-draft")

    def test_02_safe_component_removes_paths_and_reserved_punctuation(self):
        self.assertEqual(safe_component("../Northstar / Project"), "Northstar_Project")

    def test_03_finalization_stores_both_immutable_artifacts(self):
        config = self.stored()
        record = config["delivery_governance"]["versions"][0]
        directory = self.root / record["artifact_id"]
        self.assertEqual((directory / record["docx_filename"]).read_bytes(), DOCX)
        self.assertEqual((directory / record["pdf_filename"]).read_bytes(), PDF)

    def test_04_finalization_records_sha256_and_sizes(self):
        record = self.stored()["delivery_governance"]["versions"][0]
        self.assertEqual(record["docx_checksum"], hashlib.sha256(DOCX).hexdigest())
        self.assertEqual(record["pdf_checksum"], hashlib.sha256(PDF).hexdigest())
        self.assertEqual(record["docx_size"], len(DOCX))
        self.assertEqual(record["pdf_size"], len(PDF))

    def test_05_finalization_preserves_governance_metadata(self):
        record = self.stored()["delivery_governance"]["versions"][0]
        self.assertEqual(record["version"], "1.0")
        self.assertEqual(record["approved_by"], "Adam Approver")
        self.assertEqual(record["finalized_by"], "Alex Architect")
        self.assertEqual(record["assessment_id"], "assessment-123")
        self.assertEqual(record["revision_reason"], "Approved customer baseline")

    def test_06_duplicate_final_version_cannot_overwrite_artifacts(self):
        config = self.stored()
        with self.assertRaisesRegex(ValueError, "already has immutable artifacts"):
            store_final_artifacts(self.root, config, self.snapshot, DOCX, PDF, "Alex")

    def test_07_invalid_docx_is_rejected_before_storage(self):
        with self.assertRaisesRegex(ValueError, "DOCX"):
            store_final_artifacts(self.root, self.config, self.snapshot, b"not-docx", PDF, "Alex")
        self.assertFalse(self.root.exists())

    def test_08_invalid_pdf_is_rejected_before_storage(self):
        with self.assertRaisesRegex(ValueError, "PDF"):
            store_final_artifacts(self.root, self.config, self.snapshot, DOCX, b"not-pdf", "Alex")
        self.assertFalse(self.root.exists())

    def test_09_read_artifact_verifies_integrity(self):
        config = self.stored(); record = config["delivery_governance"]["versions"][0]
        self.assertEqual(read_artifact(self.root, record, "docx"), DOCX)
        self.assertEqual(read_artifact(self.root, record, "pdf"), PDF)

    def test_10_tampered_artifact_is_blocked(self):
        config = self.stored(); record = config["delivery_governance"]["versions"][0]
        (self.root / record["artifact_id"] / record["pdf_filename"]).write_bytes(b"%PDF-tampered")
        with self.assertRaisesRegex(ValueError, "integrity"):
            read_artifact(self.root, record, "pdf")

    def test_11_path_traversal_artifact_id_is_rejected(self):
        record = {"artifact_id": "../outside", "docx_filename": "file.docx"}
        with self.assertRaisesRegex(ValueError, "identifier"):
            read_artifact(self.root, record, "docx")

    def test_12_unsupported_download_type_is_rejected(self):
        record = self.stored()["delivery_governance"]["versions"][0]
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            read_artifact(self.root, record, "exe")

    def test_13_integrity_reports_each_file_availability(self):
        config = self.stored(); record = config["delivery_governance"]["versions"][0]
        (self.root / record["artifact_id"] / record["pdf_filename"]).unlink()
        result = artifact_integrity(self.root, record)
        self.assertFalse(result["valid"])
        self.assertTrue(result["docx_available"])
        self.assertFalse(result["pdf_available"])

    def test_14_delivery_package_has_exact_required_contents(self):
        config = self.stored(); record = config["delivery_governance"]["versions"][0]
        package, filename = build_delivery_package(self.root, config, self.snapshot, record)
        self.assertTrue(filename.endswith("_Delivery.zip"))
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            names = set(archive.namelist())
        self.assertEqual(names, {record["docx_filename"], record["pdf_filename"], "delivery-manifest.json", "delivery-manifest.md"})

    def test_15_delivery_manifest_has_traceability_fields(self):
        config = self.stored(); record = config["delivery_governance"]["versions"][0]
        manifest = delivery_manifest(config, self.snapshot, record)
        self.assertEqual(manifest["customer"], "Northstar / Industries")
        self.assertEqual(manifest["project"], "Move to OCVS")
        self.assertEqual(manifest["version"], "1.0")
        self.assertIn("sha256", manifest["docx"])
        self.assertIn("selected_workload", manifest)

    def test_16_manifest_and_state_never_persist_absolute_artifact_paths(self):
        config = self.stored(); record = config["delivery_governance"]["versions"][0]
        encoded = json.dumps({"config": config, "manifest": delivery_manifest(config, self.snapshot, record)})
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("/tmp/", encoded)

    def test_17_mark_delivered_records_confirmation_metadata(self):
        config = self.delivered(); record = config["delivery_governance"]["versions"][0]
        self.assertEqual(record["status"], "delivered")
        self.assertEqual(record["delivery_date"], "2026-09-17")
        self.assertEqual(record["recipient_company"], "Northstar")
        self.assertEqual(config["review_workflow"]["status"], "delivered")
        self.assertEqual(config["status"], "delivered")

    def test_18_mark_delivered_requires_final_artifact(self):
        config, errors = mark_delivered(self.config, self.root, "missing", "Alex", "2026-09-17", {})
        self.assertTrue(errors)
        self.assertEqual(config["review_workflow"]["status"], "finalized")

    def test_19_mark_delivered_requires_actor_and_real_calendar_date(self):
        config = self.stored(); artifact_id = config["delivery_governance"]["versions"][0]["artifact_id"]
        _config, errors = mark_delivered(config, self.root, artifact_id, "", "2026-02-31", {})
        self.assertTrue(any("identity" in item for item in errors))
        self.assertTrue(any("date" in item for item in errors))

    def test_20_mark_delivered_rejects_invalid_recipient_email(self):
        config = self.stored(); artifact_id = config["delivery_governance"]["versions"][0]["artifact_id"]
        _config, errors = mark_delivered(config, self.root, artifact_id, "Alex", "2026-09-17", {"email": "invalid"})
        self.assertTrue(any("e-mail" in item for item in errors))

    def test_21_delivery_is_blocked_when_artifact_is_tampered(self):
        config = self.stored(); record = config["delivery_governance"]["versions"][0]
        (self.root / record["artifact_id"] / record["docx_filename"]).write_bytes(b"PKtampered")
        _config, errors = mark_delivered(config, self.root, record["artifact_id"], "Alex", "2026-09-17", {})
        self.assertTrue(any("integrity" in item for item in errors))

    def test_22_new_revision_requires_a_finalized_baseline(self):
        config, errors = start_new_revision(self.config, "Alex", "Customer update")
        self.assertTrue(errors)
        self.assertEqual(config["review_workflow"]["status"], "finalized")

    def test_23_new_revision_requires_actor_and_reason(self):
        config = self.delivered()
        _config, actor_errors = start_new_revision(config, "", "Customer update")
        _config, reason_errors = start_new_revision(config, "Alex", "")
        self.assertTrue(actor_errors)
        self.assertTrue(reason_errors)

    def test_24_new_revision_increments_version_and_resets_review(self):
        config = self.delivered()
        revised, errors = start_new_revision(config, "Alex", "Network design changed")
        self.assertFalse(errors)
        self.assertEqual(revised["review_workflow"]["current_revision"], "1.1")
        self.assertEqual(revised["review_workflow"]["status"], "draft")
        self.assertEqual(revised["review_workflow"]["reviewers"][0]["status"], "pending")
        self.assertEqual(revised["review_workflow"]["approvers"][0]["status"], "pending")
        self.assertEqual(revised["delivery_governance"]["based_on_version"], "1.0")
        self.assertTrue(revised["delivery_governance"]["unpublished_changes"])

    def test_25_new_revision_keeps_previous_artifact_record_unchanged(self):
        config = self.delivered(); before = deepcopy(config["delivery_governance"]["versions"])
        revised, errors = start_new_revision(config, "Alex", "Network design changed")
        self.assertFalse(errors)
        self.assertEqual(revised["delivery_governance"]["versions"], before)

    def test_26_second_finalization_links_to_replaced_version(self):
        config = self.delivered()
        revised, _ = start_new_revision(config, "Alex", "Network design changed")
        revised["review_workflow"].update({
            "status": "finalized", "final_version": "1.1", "current_revision": "1.1",
            "finalized_at": "2026-09-18T09:00:00+00:00", "finalized_by": "Alex",
        })
        revised["customer_document"].update({"version": "1.1", "version_comment": "Network design changed"})
        revised["delivery_governance"] = store_final_artifacts(self.root, revised, self.snapshot, b"PKsecond", b"%PDF-second", "Alex")
        record = find_version(revised["delivery_governance"], version="1.1")
        self.assertEqual(record["replaces_version"], "1.0")
        self.assertEqual(record["revision_reason"], "Network design changed")

    def test_27_older_delivered_version_can_be_superseded(self):
        config = self.delivered()
        revised, _ = start_new_revision(config, "Alex", "Network design changed")
        revised["review_workflow"].update({"status": "finalized", "final_version": "1.1", "current_revision": "1.1"})
        revised["customer_document"]["version"] = "1.1"
        revised["delivery_governance"] = store_final_artifacts(self.root, revised, self.snapshot, b"PKsecond", b"%PDF-second", "Alex")
        second = find_version(revised["delivery_governance"], version="1.1")
        revised, errors = mark_delivered(revised, self.root, second["artifact_id"], "Alex", "2026-09-18", {})
        self.assertFalse(errors)
        revised, error = supersede_version(revised, "1.0", "Alex")
        self.assertFalse(error)
        old = find_version(revised["delivery_governance"], version="1.0")
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_by"], "1.1")

    def test_28_latest_delivered_version_cannot_be_superseded(self):
        config = self.delivered()
        _config, error = supersede_version(config, "1.0", "Alex")
        self.assertTrue(error)

    def test_29_governance_summary_reports_missing_host_artifacts(self):
        config = self.stored(); record = config["delivery_governance"]["versions"][0]
        (self.root / record["artifact_id"] / record["pdf_filename"]).unlink()
        result = governance_summary(config, self.root)
        self.assertEqual(result["versions"][0]["integrity"], "Unavailable or invalid")

    def test_30_audit_history_is_append_only(self):
        config = self.stored(); before = deepcopy(config["delivery_governance"]["audit_events"])
        config = record_audit(config, "artifact_download", "Alex", "1.0", "DOCX")
        self.assertEqual(config["delivery_governance"]["audit_events"][:len(before)], before)
        self.assertEqual(config["delivery_governance"]["audit_events"][-1]["event"], "artifact_download")


if __name__ == "__main__":
    unittest.main()
