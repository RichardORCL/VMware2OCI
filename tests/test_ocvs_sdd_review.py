from __future__ import annotations

import unittest
from copy import deepcopy

from services.ocvs_sdd_adapter import build_sdd_payload, normalize_sdd_configuration, readiness, snapshot_hash
from services.ocvs_sdd_review import (
    add_comment, approve, complete_review, final_validation, finalize,
    invalidate_if_stale, normalize_review_workflow, request_changes,
    resolve_comment, submit, summary,
)
from tests.test_ocvs_sdd_flask_integration import source_and_config


def prepared():
    source, config = source_and_config()
    config["customer_document"].update({
        "customer_legal_name": "Northstar Industries",
        "project_name": "OCVS Migration",
        "document_author": "Alex Architect",
        "document_author_email": "alex@northstar.example.org",
    })
    config["source_snapshot_hash"] = snapshot_hash(source)
    config["review_workflow"] = normalize_review_workflow({
        "reviewers": [{"name": "Rita Reviewer", "email": "rita@northstar.example.org", "required": True}],
        "approvers": [{"name": "Adam Approver", "email": "adam@northstar.example.org"}],
    })
    config = normalize_sdd_configuration(config)
    return source, config, readiness(source, config, scenario_id="ocvs")


class OCVSSDDReviewTests(unittest.TestCase):
    def test_phase4_state_upgrades_with_safe_defaults(self):
        _source, config = source_and_config()
        normalized = normalize_sdd_configuration(config)
        self.assertEqual(normalized["review_workflow"]["status"], "draft")
        self.assertEqual(normalized["review_workflow"]["current_revision"], "0.1")

    def test_submission_requires_readiness(self):
        source, config, status = prepared()
        status["ready"] = False
        submitted, errors = submit(config, source, status, "Alex")
        self.assertTrue(errors)
        self.assertEqual(submitted["review_workflow"]["status"], "draft")

    def test_submission_requires_reviewer(self):
        source, config, status = prepared()
        config["review_workflow"]["reviewers"] = []
        _submitted, errors = submit(config, source, status, "Alex")
        self.assertIn("Assign at least one technical reviewer before submission.", errors)

    def test_valid_submission_freezes_source(self):
        source, config, status = prepared()
        submitted, errors = submit(config, source, status, "Alex")
        self.assertFalse(errors)
        self.assertEqual(submitted["review_workflow"]["status"], "in_review")
        self.assertTrue(submitted["review_workflow"]["content_hash"])
        self.assertEqual(submitted["review_workflow"]["source_snapshot_hash"], snapshot_hash(source))

    def test_comments_are_persisted(self):
        source, config, status = prepared()
        config, _ = submit(config, source, status, "Alex")
        config, error = add_comment(config, section="Network", author="Rita", comment="Confirm DRG.", severity="warning")
        self.assertFalse(error)
        self.assertEqual(config["review_workflow"]["comments"][0]["section"], "Network")

    def test_blocking_comment_prevents_approval(self):
        source, config, status = prepared()
        config, _ = submit(config, source, status, "Alex")
        config, _ = add_comment(config, section="Network", author="Rita", comment="Missing route.", severity="blocking")
        reviewer = config["review_workflow"]["reviewers"][0]
        config, _ = complete_review(config, reviewer["id"], "Rita")
        approver = config["review_workflow"]["approvers"][0]
        _config, errors = approve(config, source, status, approver["id"], "Adam")
        self.assertTrue(any("blocking" in item.lower() for item in errors))

    def test_resolved_blocker_allows_approval(self):
        source, config, status = prepared()
        config, _ = submit(config, source, status, "Alex")
        config, _ = add_comment(config, section="Network", author="Rita", comment="Missing route.", severity="blocking")
        comment = config["review_workflow"]["comments"][0]
        config, error = resolve_comment(config, comment["id"], "Alex", "Route added.")
        self.assertFalse(error)
        reviewer = config["review_workflow"]["reviewers"][0]
        config, _ = complete_review(config, reviewer["id"], "Rita")
        approver = config["review_workflow"]["approvers"][0]
        config, errors = approve(config, source, status, approver["id"], "Adam")
        self.assertFalse(errors)
        self.assertEqual(config["review_workflow"]["status"], "approved")

    def test_request_changes_preserves_comments(self):
        source, config, status = prepared()
        config, _ = submit(config, source, status, "Alex")
        config, _ = add_comment(config, section="General", author="Rita", comment="Update wording.", severity="informational")
        config, error = request_changes(config, "Rita", "Please revise.")
        self.assertFalse(error)
        self.assertEqual(config["review_workflow"]["status"], "changes_requested")
        self.assertEqual(len(config["review_workflow"]["comments"]), 1)

    def test_source_change_invalidates_approval(self):
        source, config = self._approved()
        changed = deepcopy(source)
        changed["scope"]["selected_vm_count"] += 1
        config, invalidated = invalidate_if_stale(config, changed)
        self.assertTrue(invalidated)
        self.assertEqual(config["review_workflow"]["status"], "changes_requested")

    def test_approval_history_is_append_only(self):
        source, config = self._approved()
        before = deepcopy(config["review_workflow"]["approval_history"])
        config, _ = invalidate_if_stale(config, {**source, "source_step4_updated_at": "later"})
        self.assertEqual(config["review_workflow"]["approval_history"][:len(before)], before)

    def test_draft_revision_increments_on_resubmit(self):
        source, config, status = prepared()
        config, _ = submit(config, source, status, "Alex")
        config, _ = request_changes(config, "Rita")
        config, errors = submit(config, source, status, "Alex")
        self.assertFalse(errors)
        self.assertEqual(config["review_workflow"]["current_revision"], "0.2")

    def test_first_approval_becomes_version_one(self):
        _source, config = self._approved()
        self.assertEqual(config["review_workflow"]["current_revision"], "1.0")

    def test_finalization_blocked_before_approval(self):
        source, config, status = prepared()
        _config, errors = finalize(config, source, status, "Alex")
        self.assertTrue(errors)

    def test_finalization_sets_customer_version(self):
        source, config = self._approved()
        status = readiness(source, config, scenario_id="ocvs")
        config, errors = finalize(config, source, status, "Alex")
        self.assertFalse(errors)
        self.assertEqual(config["review_workflow"]["status"], "finalized")
        self.assertEqual(config["review_workflow"]["final_version"], "1.0")

    def test_draft_and_final_payload_watermark_flags(self):
        source, config, _status = prepared()
        self.assertTrue(build_sdd_payload(source, config)["document"]["draft_status"])
        self.assertFalse(build_sdd_payload(source, config, final=True, document_version="1.0")["document"]["draft_status"])

    def test_final_validation_rejects_sample_customer(self):
        source, config = self._approved()
        config["customer_document"]["customer_legal_name"] = "Fictional Sample Customer"
        status = readiness(source, config, scenario_id="ocvs")
        self.assertTrue(any("sample" in item.lower() for item in final_validation(config, source, status)))

    def test_summary_exposes_progress_and_actions(self):
        source, config, status = prepared()
        state = summary(config, source, status)
        self.assertTrue(state["can_submit"])
        self.assertEqual(state["reviewer_required"], 1)

    def test_review_fields_are_json_portable(self):
        import json
        source, config, status = prepared()
        config, _ = submit(config, source, status, "Alex")
        encoded = json.dumps(normalize_sdd_configuration(config))
        self.assertIn("submitted_for_review", encoded)
        self.assertNotIn("/tmp/", encoded)

    def test_non_ocvs_remains_blocked_by_phase4_readiness(self):
        source, config, _status = prepared()
        result = readiness(source, config, scenario_id="hybrid")
        self.assertFalse(result["ready"])

    def test_no_generated_artifact_reference_is_persisted(self):
        _source, config, _status = prepared()
        keys = set(config["review_workflow"])
        self.assertFalse({"path", "file", "artifact", "pdf_path", "docx_path"} & keys)

    def _approved(self):
        source, config, status = prepared()
        config, _ = submit(config, source, status, "Alex")
        reviewer = config["review_workflow"]["reviewers"][0]
        config, _ = complete_review(config, reviewer["id"], "Rita")
        approver = config["review_workflow"]["approvers"][0]
        config, errors = approve(config, source, status, approver["id"], "Adam")
        self.assertFalse(errors)
        return source, config


if __name__ == "__main__":
    unittest.main()
