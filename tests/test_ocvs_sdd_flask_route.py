from __future__ import annotations

import hashlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module

from tests.test_ocvs_sdd_flask_integration import source_and_config


ROOT = Path(__file__).resolve().parents[1]
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def fake_generator_module(*, fail: bool = False) -> types.ModuleType:
    module = types.ModuleType("scripts.generate_ocvs_sdd")

    class GenerationError(RuntimeError):
        pass

    def validate_input(_payload):
        return []

    def generate(template_path, _input_path, output_path, _schema_path):
        if fail:
            raise GenerationError("Synthetic route failure")
        template_bytes = Path(template_path).read_bytes()
        Path(output_path).write_bytes(template_bytes)
        digest = hashlib.sha256(template_bytes).hexdigest()
        return {
            "source_template_checksum": digest,
            "input_data_checksum": "input-checksum",
            "generated_document_checksum": digest,
            "warnings_requiring_specialist_review": [],
        }

    module.GenerationError = GenerationError
    module.validate_input = validate_input
    module.generate = generate
    return module


class OCVSSDDFlaskRouteTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True, SECRET_KEY="phase3-test-secret")
        self.client = app_module.app.test_client()

    def valid_app_state(self):
        source, config = source_and_config()
        return {
            "sdd_source_snapshot": source,
            "sdd_configuration": config,
            "step4_last_updated_at": config["source_step4_updated_at"],
            "selected_vm_names": [],
        }

    def test_route_is_blocked_for_non_ocvs_scenario(self):
        with patch.object(app_module, "selected_business_scenario", return_value={"id": "compute"}):
            response = self.client.post("/step4/sdd", data={"action": "generate_sdd"})
        self.assertEqual(response.status_code, 303)

    def test_valid_ocvs_route_downloads_docx_without_modifying_master(self):
        state = self.valid_app_state()
        template_before = hashlib.sha256(app_module.OCVS_SDD_TEMPLATE_PATH.read_bytes()).hexdigest()
        fake_module = fake_generator_module()
        with (
            patch.object(app_module, "selected_business_scenario", return_value={"id": "ocvs"}),
            patch.object(app_module, "load_app_state", return_value=state),
            patch.dict(sys.modules, {"scripts.generate_ocvs_sdd": fake_module}),
        ):
            response = self.client.post("/step4/sdd", data={"action": "generate_sdd"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, DOCX_MIME)
        self.assertIn("ocvs_sdd_draft", response.headers.get("Content-Disposition", "").lower())
        self.assertTrue(response.data.startswith(b"PK"))
        self.assertEqual(
            hashlib.sha256(app_module.OCVS_SDD_TEMPLATE_PATH.read_bytes()).hexdigest(),
            template_before,
        )

    def test_generation_failure_returns_redirect_and_no_partial_file(self):
        state = self.valid_app_state()
        fake_module = fake_generator_module(fail=True)
        with (
            patch.object(app_module, "selected_business_scenario", return_value={"id": "ocvs"}),
            patch.object(app_module, "load_app_state", return_value=state),
            patch.dict(sys.modules, {"scripts.generate_ocvs_sdd": fake_module}),
        ):
            response = self.client.post("/step4/sdd", data={"action": "generate_sdd"})
        self.assertEqual(response.status_code, 303)
        self.assertNotEqual(response.mimetype, DOCX_MIME)


if __name__ == "__main__":
    unittest.main()
