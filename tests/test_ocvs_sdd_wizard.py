from __future__ import annotations

import copy
import html
import unittest
from unittest.mock import patch

import app as app_module
from services.ocvs_sdd_adapter import (
    WIZARD_SECTIONS,
    normalize_sdd_configuration,
    readiness,
    snapshot_hash,
    validate_section,
)
from tests.test_ocvs_sdd_flask_integration import source_and_config


class OCVSSDDWizardModelTests(unittest.TestCase):
    def test_phase3_configuration_is_normalized_without_losing_narrative(self):
        config = normalize_sdd_configuration(
            {
                "schema_version": "1.0",
                "customer_document": {"project_name": "Northstar"},
                "business": {"customer_business_context": "Line one\nLine two"},
                "operations": {"implementation_provider": "Oracle"},
            }
        )
        self.assertEqual(config["schema_version"], "2.0")
        self.assertEqual(config["business"]["customer_business_context"], "Line one\nLine two")
        self.assertEqual(config["operations"]["implementation_provider"], "oracle")
        self.assertEqual(config["wizard"]["current_step"], "customer-project")

    def test_validation_reports_helpful_email_and_cidr_errors(self):
        source, config = source_and_config()
        config["customer_document"]["document_author_email"] = "not-an-email"
        config["network"]["vcn_cidr"] = "10.0.0.0/99"
        self.assertIn(
            "Enter a valid document author email address.",
            validate_section("customer-project", config)["errors"],
        )
        self.assertTrue(
            any("invalid CIDR" in item for item in validate_section("network-design", config)["errors"])
        )
        config["source_snapshot_hash"] = snapshot_hash(source)

    def test_disabled_optional_sections_do_not_block_readiness(self):
        source, config = source_and_config()
        config["section_flags"].update(include_security=False, include_raci=False, include_risks=False, include_transition=False)
        config["security"] = {"include_section": False}
        config["source_snapshot_hash"] = snapshot_hash(source)
        result = readiness(source, config, scenario_id="ocvs")
        self.assertTrue(result["ready"])
        self.assertFalse(result["blocking_errors_by_step"].get("security-compliance"))

    def test_stale_sizing_blocks_generation_and_pricing_is_only_a_warning(self):
        source, config = source_and_config()
        changed = copy.deepcopy(source)
        changed["sizing"]["total_nodes"] += 1
        changed["commercial"].update(pricing_available=False, monthly_cost=None, annual_cost=None)
        result = readiness(changed, config, scenario_id="ocvs")
        self.assertFalse(result["ready"])
        self.assertTrue(result["configuration_is_stale"])
        self.assertTrue(any("Pricing is unavailable" in item for item in result["warnings"]))


class OCVSSDDWizardRouteTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True, SECRET_KEY="phase4-wizard-test")
        self.client = app_module.app.test_client()
        self.source, self.config = source_and_config()
        self.state = {
            "sdd_source_snapshot": self.source,
            "sdd_configuration": self.config,
            "step4_last_updated_at": self.config["source_step4_updated_at"],
            "selected_vm_names": [],
        }
        self.scenario = app_module.BUSINESS_SCENARIO_BY_ID["ocvs"]

    def _patches(self):
        return (
            patch.object(app_module, "selected_business_scenario", return_value=self.scenario),
            patch.object(app_module, "load_app_state", return_value=self.state),
            patch.object(app_module, "_current_ocvs_sdd_snapshot", return_value=(self.source, "step4")),
        )

    def test_all_seven_steps_render_with_navigation(self):
        for index, section in enumerate(WIZARD_SECTIONS):
            scenario_patch, state_patch, snapshot_patch = self._patches()
            with scenario_patch, state_patch, snapshot_patch:
                response = self.client.get(f"/step4/sdd/configure/{section}")
            self.assertEqual(response.status_code, 200, section)
            self.assertIn(b"SDD Configuration", response.data)
            self.assertIn(html.escape(app_module.WIZARD_LABELS[section]).encode(), response.data)
            if index:
                self.assertIn(b"Previous", response.data)

    def test_wizard_is_not_available_for_other_scenarios(self):
        with patch.object(
            app_module,
            "selected_business_scenario",
            return_value=app_module.BUSINESS_SCENARIO_BY_ID["compute"],
        ):
            response = self.client.get("/step4/sdd/configure/customer-project")
        self.assertEqual(response.status_code, 303)

    def test_dynamic_network_rows_persist_and_continue(self):
        saved: list[dict] = []
        form = {
            "vcn_cidr": "10.0.0.0/16",
            "segments_name[]": "Application",
            "segments_purpose[]": "Application workloads",
            "segments_cidr[]": "10.0.10.0/24",
            "segments_vlan[]": "110",
            "segments_gateway[]": "10.0.10.1",
            "segments_routing_notes[]": "Via DRG",
            "segments_security_notes[]": "Customer policy",
            "wizard_action": "continue",
        }
        scenario_patch, state_patch, snapshot_patch = self._patches()
        with (
            scenario_patch,
            state_patch,
            snapshot_patch,
            patch.object(app_module, "save_app_state", side_effect=lambda value: saved.append(copy.deepcopy(value))),
        ):
            response = self.client.post("/step4/sdd/configure/network-design", data=form)
        self.assertEqual(response.status_code, 303)
        self.assertIn("security-compliance", response.headers["Location"])
        segment = saved[-1]["sdd_configuration"]["network"]["segments"][0]
        self.assertEqual(segment["name"], "Application")
        self.assertEqual(segment["cidr"], "10.0.10.0/24")

    def test_milestone_and_raci_rows_preserve_phase4_fields(self):
        saved: list[dict] = []
        form = {
            "include_raci": "1",
            "include_transition": "1",
            "milestones_milestone[]": "Pilot wave",
            "milestones_owner[]": "Customer",
            "milestones_date[]": "2026-10-01",
            "milestones_dependency[]": "Network ready",
            "milestones_status[]": "Planned",
            "milestones_notes[]": "Validate rollback",
            "raci_activity[]": "Approve wave",
            "raci_customer[]": "A",
            "raci_partner[]": "R",
            "raci_oracle[]": "C",
            "raci_notes[]": "Before cutover",
            "wizard_action": "save",
        }
        scenario_patch, state_patch, snapshot_patch = self._patches()
        with (
            scenario_patch,
            state_patch,
            snapshot_patch,
            patch.object(app_module, "save_app_state", side_effect=lambda value: saved.append(copy.deepcopy(value))),
        ):
            response = self.client.post("/step4/sdd/configure/migration-transition", data=form)
        self.assertEqual(response.status_code, 303)
        delivery = saved[-1]["sdd_configuration"]["delivery"]
        self.assertEqual(delivery["transition_milestones"][0]["dependency"], "Network ready")
        self.assertEqual(delivery["raci"][0]["oracle"], "C")


if __name__ == "__main__":
    unittest.main()
