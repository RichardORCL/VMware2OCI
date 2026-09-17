from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import app as app_module
from services.ocvs_sdd_adapter import normalize_sdd_configuration
from services.ocvs_sdd_delivery import store_final_artifacts
from tests.test_ocvs_sdd_delivery import DOCX, PDF, finalized_configuration


class OCVSSDDDeliveryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module.app.config.update(TESTING=True, SECRET_KEY="phase6-route-secret")
        self.client = app_module.app.test_client()
        self.temporary = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temporary.name) / "app_state"
        self.config, self.snapshot = finalized_configuration()
        self.config["delivery_governance"] = store_final_artifacts(
            self.state_dir / "sdd_artifacts", self.config, self.snapshot, DOCX, PDF, "Alex Architect",
        )
        self.config = normalize_sdd_configuration(self.config)
        self.state = {"sdd_configuration": self.config, "sdd_source_snapshot": self.snapshot}

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def route_patches(self):
        return (
            patch.object(app_module, "APP_STATE_DIR", self.state_dir),
            patch.object(app_module, "selected_business_scenario", return_value={"id": "ocvs", "name": "Move to OCVS"}),
            patch.object(app_module, "load_app_state", return_value=self.state),
            patch.object(app_module, "_current_ocvs_sdd_snapshot", return_value=(self.snapshot, "step4")),
        )

    def test_delivery_workspace_renders_version_history(self):
        first, second, third, fourth = self.route_patches()
        with first, second, third, fourth:
            response = self.client.get("/step4/sdd/delivery")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SDD Customer Delivery", response.data)
        self.assertIn(b"v1.0", response.data)
        self.assertIn(b"ZIP package", response.data)

    def test_historical_docx_download_uses_immutable_artifact(self):
        artifact_id = self.config["delivery_governance"]["versions"][0]["artifact_id"]
        first, second, third, fourth = self.route_patches()
        with first, second, third, fourth, patch.object(app_module, "save_app_state"):
            response = self.client.get(f"/step4/sdd/artifact/{artifact_id}/docx")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, DOCX)

    def test_delivery_package_route_returns_four_files(self):
        artifact_id = self.config["delivery_governance"]["versions"][0]["artifact_id"]
        first, second, third, fourth = self.route_patches()
        with first, second, third, fourth, patch.object(app_module, "save_app_state"):
            response = self.client.get(f"/step4/sdd/package/{artifact_id}")
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(len(archive.namelist()), 4)

    def test_mark_delivered_persists_governed_status(self):
        artifact_id = self.config["delivery_governance"]["versions"][0]["artifact_id"]
        saved = []
        first, second, third, fourth = self.route_patches()
        with first, second, third, fourth, patch.object(app_module, "save_app_state", side_effect=lambda value: saved.append(value)):
            response = self.client.post("/step4/sdd/delivery", data={
                "action": "mark_delivered", "artifact_id": artifact_id,
                "actor": "Alex Architect", "delivery_date": "2026-09-17",
                "recipient_name": "Casey Customer", "recipient_company": "Northstar",
                "recipient_email": "casey@example.org", "delivery_comment": "Sent securely",
            })
        self.assertEqual(response.status_code, 303)
        self.assertTrue(saved)
        self.assertEqual(saved[-1]["sdd_configuration"]["review_workflow"]["status"], "delivered")
        self.assertEqual(len(saved[-1]["sdd_configuration"]["acceptance_handover"]["records"]), 1)
        self.assertEqual(saved[-1]["sdd_configuration"]["acceptance_handover"]["records"][0]["status"], "acceptance_pending")

    def test_start_revision_redirects_to_wizard_and_keeps_old_artifact(self):
        artifact_id = self.config["delivery_governance"]["versions"][0]["artifact_id"]
        delivered, errors = app_module.mark_ocvs_sdd_delivered(
            self.config, self.state_dir / "sdd_artifacts", artifact_id, "Alex", "2026-09-17", {}, "",
        )
        self.assertFalse(errors)
        self.state["sdd_configuration"] = normalize_sdd_configuration(delivered)
        saved = []
        first, second, third, fourth = self.route_patches()
        with first, second, third, fourth, patch.object(app_module, "save_app_state", side_effect=lambda value: saved.append(value)):
            response = self.client.post("/step4/sdd/delivery", data={
                "action": "start_revision", "actor": "Alex", "revision_reason": "Customer network update",
            })
        self.assertEqual(response.status_code, 303)
        self.assertIn("/step4/sdd/configure", response.headers["Location"])
        revised = saved[-1]["sdd_configuration"]
        self.assertEqual(revised["review_workflow"]["current_revision"], "1.1")
        self.assertEqual(revised["delivery_governance"]["versions"][0]["artifact_id"], artifact_id)


if __name__ == "__main__":
    unittest.main()
