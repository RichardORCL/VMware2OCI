from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from services.ocvs_sdd_adapter import (
    build_sdd_payload,
    normalize_sdd_configuration,
    readiness,
    snapshot_hash,
)


ROOT = Path(__file__).resolve().parents[1]


def source_and_config(name: str = "ocvs_sdd_single_cluster.json"):
    fixture = json.loads((ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8"))
    source = {
        "assessment_id": "assessment-1",
        "source_step4_updated_at": "2026-09-16T10:00:00",
        "document": {
            "customer_name": fixture["document"]["customer_name"],
            "assessment_name": fixture["document"]["assessment_name"],
            "assessment_date": fixture["document"]["assessment_date"],
            "rvtools_file_name": "/private/customer/" + fixture["document"]["rvtools_file_name"],
        },
        "scope": deepcopy(fixture["scope"]),
        "sizing": deepcopy(fixture["sizing"]),
        "target_clusters": deepcopy(fixture["target_clusters"]),
        "commercial": deepcopy(fixture["commercial"]),
        "specialist_review_warnings": ["Draft requires specialist review."],
    }
    config = normalize_sdd_configuration(
        {
            "source_assessment_id": "assessment-1",
            "source_snapshot_hash": snapshot_hash(source),
            "source_step4_updated_at": "2026-09-16T10:00:00",
            "customer_document": {
                "customer_legal_name": fixture["document"]["customer_legal_name"],
                "project_name": fixture["document"]["project_name"],
                "document_author": fixture["document"]["document_author"],
                "document_author_email": fixture["document"]["document_author_email"],
                "version": fixture["document"].get("document_version", "0.1"),
                "version_comment": fixture["document"].get("version_comment", ""),
            },
            "business": fixture["business"],
            "operations": {"implementation_provider": "customer"},
        }
    )
    return source, config


class OCVSSDDAdapterIntegrationTests(unittest.TestCase):
    def test_single_cluster_payload_uses_safe_filename_and_contract(self):
        from scripts.generate_ocvs_sdd import validate_input

        source, config = source_and_config()
        payload = build_sdd_payload(source, config)
        self.assertEqual(payload["document"]["rvtools_file_name"], "northstar_fictional_rvtools.xlsx")
        self.assertEqual(len(payload["target_clusters"]), 1)
        self.assertEqual(validate_input(payload), [])

    def test_multi_cluster_payload_never_falls_back_to_single(self):
        from scripts.generate_ocvs_sdd import validate_input

        source, config = source_and_config("ocvs_sdd_multi_cluster.json")
        config["source_snapshot_hash"] = snapshot_hash(source)
        payload = build_sdd_payload(source, config)
        self.assertEqual(payload["sizing"]["topology"], "multi")
        self.assertEqual(len(payload["target_clusters"]), 3)
        self.assertEqual(payload["target_clusters"][1]["selected_shape"], "BM.Optimized3.36")
        self.assertEqual(validate_input(payload), [])

    def test_unavailable_pricing_has_no_false_amounts(self):
        source, config = source_and_config()
        source["commercial"].update(pricing_available=False, monthly_cost=123, annual_cost=456)
        config["source_snapshot_hash"] = snapshot_hash(source)
        payload = build_sdd_payload(source, config)
        self.assertFalse(payload["commercial"]["pricing_available"])
        self.assertIsNone(payload["commercial"]["monthly_cost"])
        self.assertIsNone(payload["commercial"]["annual_cost"])

    def test_readiness_blocks_missing_and_stale_configuration(self):
        source, config = source_and_config()
        self.assertTrue(readiness(source, config, scenario_id="ocvs")["ready"])
        stale = deepcopy(config)
        stale["source_snapshot_hash"] = "old"
        result = readiness(source, stale, scenario_id="ocvs")
        self.assertFalse(result["ready"])
        self.assertTrue(result["configuration_is_stale"])
        missing = readiness(source, {}, scenario_id="ocvs")
        self.assertFalse(missing["ready"])
        self.assertIn("Customer Legal Name", missing["missing_required_inputs"])

    def test_invalid_multi_cluster_assignment_is_blocking(self):
        source, config = source_and_config("ocvs_sdd_multi_cluster.json")
        source["target_clusters"][1]["assigned_source_clusters"] = source["target_clusters"][0]["assigned_source_clusters"]
        config["source_snapshot_hash"] = snapshot_hash(source)
        result = readiness(source, config, scenario_id="ocvs")
        self.assertFalse(result["ready"])
        self.assertTrue(any("unassigned or duplicated" in item for item in result["blocking_errors"]))

    def test_selected_scope_must_reconcile_with_source_cluster_totals(self):
        source, config = source_and_config()
        source["scope"]["source_clusters"][0]["vm_count"] -= 1
        config["source_snapshot_hash"] = snapshot_hash(source)
        result = readiness(source, config, scenario_id="ocvs")
        self.assertFalse(result["ready"])
        self.assertTrue(any("does not reconcile" in item for item in result["blocking_errors"]))

    def test_minimum_host_rules_are_blocking(self):
        source, config = source_and_config("ocvs_sdd_multi_cluster.json")
        source["target_clusters"][0]["total_nodes"] = 2
        config["source_snapshot_hash"] = snapshot_hash(source)
        result = readiness(source, config, scenario_id="ocvs")
        self.assertFalse(result["ready"])
        self.assertTrue(any("requires at least 3 hosts" in item for item in result["blocking_errors"]))

    def test_missing_pricing_is_a_warning_not_a_blocker(self):
        source, config = source_and_config()
        source["commercial"]["pricing_available"] = False
        source["commercial"]["monthly_cost"] = None
        source["commercial"]["annual_cost"] = None
        config["source_snapshot_hash"] = snapshot_hash(source)
        result = readiness(source, config, scenario_id="ocvs")
        self.assertTrue(result["ready"])
        self.assertTrue(any("Pricing is unavailable" in item for item in result["warnings"]))

    def test_non_ocvs_scenario_is_blocked(self):
        source, config = source_and_config()
        result = readiness(source, config, scenario_id="capacity")
        self.assertFalse(result["ready"])
        self.assertTrue(any("only for Move to OCVS" in item for item in result["blocking_errors"]))


class OCVSSDDUIIntegrationTests(unittest.TestCase):
    def test_export_template_scopes_panel_to_ocvs(self):
        template = (ROOT / "templates" / "_export_center.html").read_text(encoding="utf-8")
        self.assertIn("export_scenario_id == 'ocvs'", template)
        self.assertIn("Solution Definition Document", template)
        self.assertIn("Generate Draft SDD", template)


if __name__ == "__main__":
    unittest.main()
