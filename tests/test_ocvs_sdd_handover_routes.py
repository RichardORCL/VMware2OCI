from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
from services.ocvs_sdd_adapter import normalize_sdd_configuration
from services.ocvs_sdd_delivery import mark_delivered, store_final_artifacts
from services.ocvs_sdd_handover import start_acceptance
from tests.test_ocvs_sdd_delivery import DOCX, PDF, finalized_configuration


class OCVSSDDHandoverRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module.app.config.update(TESTING=True, SECRET_KEY="phase7-route-secret")
        self.client = app_module.app.test_client()
        self.temporary = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temporary.name) / "app_state"
        config, self.snapshot = finalized_configuration()
        config["delivery_governance"] = store_final_artifacts(
            self.state_dir / "sdd_artifacts", config, self.snapshot, DOCX, PDF, "Alex",
        )
        artifact_id = config["delivery_governance"]["versions"][0]["artifact_id"]
        config, errors = mark_delivered(config, self.state_dir / "sdd_artifacts", artifact_id, "Alex", "2026-09-17", {
            "name":"Casey", "company":"Northstar", "email":"casey@example.org",
        })
        self.assertEqual(errors, [])
        config, errors = start_acceptance(config, self.state_dir / "sdd_artifacts", artifact_id, "Alex")
        self.assertEqual(errors, [])
        self.state = {"sdd_configuration": normalize_sdd_configuration(config), "sdd_source_snapshot": self.snapshot}

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_workspace_renders_traceability_and_controls(self):
        with patch.object(app_module, "APP_STATE_DIR", self.state_dir), \
             patch.object(app_module, "selected_business_scenario", return_value={"id":"ocvs","name":"Move to OCVS"}), \
             patch.object(app_module, "load_app_state", return_value=self.state), \
             patch.object(app_module, "save_app_state"):
            response = self.client.get("/step4/sdd/acceptance")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Customer Acceptance &amp; Handover", response.data)
        self.assertIn(b"Casey", response.data)
        self.assertIn(b"Implementation readiness", response.data)

    def test_non_ocvs_scenario_is_redirected(self):
        with patch.object(app_module, "selected_business_scenario", return_value={"id":"native","name":"OCI Native"}):
            response = self.client.get("/step4/sdd/acceptance")
        self.assertEqual(response.status_code, 303)


if __name__ == "__main__":
    unittest.main()
