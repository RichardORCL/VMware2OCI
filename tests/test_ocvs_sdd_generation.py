import copy
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document
from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_ocvs_sdd import GenerationError, generate  # noqa: E402


TEMPLATE = ROOT / "document_templates" / "OCVS_SDD_template_automatable.docx"
SCHEMA = ROOT / "schemas" / "ocvs_sdd_generation.schema.json"
SINGLE = ROOT / "tests" / "fixtures" / "ocvs_sdd_single_cluster.json"
MULTI = ROOT / "tests" / "fixtures" / "ocvs_sdd_multi_cluster.json"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_data(path):
    tags, text = [], []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            if name.startswith("word/") and name.endswith(".xml"):
                try:
                    root = etree.fromstring(archive.read(name))
                except etree.XMLSyntaxError:
                    continue
                tags.extend(root.xpath(".//w:sdtPr/w:tag/@w:val", namespaces=NS))
                text.extend(root.xpath(".//w:t/text()", namespaces=NS))
    return names, tags, "\n".join(text)


class OCVSSDDGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp.name)
        self.before = digest(TEMPLATE)

    def tearDown(self):
        self.assertEqual(self.before, digest(TEMPLATE), "master template changed")
        self.temp.cleanup()

    def make(self, fixture=SINGLE, name="out.docx"):
        output = self.out_dir / name
        report = generate(TEMPLATE, fixture, output, SCHEMA)
        return output, report

    def fixture_variant(self, mutate):
        data = json.loads(SINGLE.read_text())
        mutate(data)
        path = self.out_dir / "variant.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_master_is_unchanged_and_output_is_valid_openxml(self):
        output, report = self.make()
        self.assertTrue(zipfile.is_zipfile(output))
        names, _, _ = package_data(output)
        self.assertIn("word/document.xml", names)
        self.assertNotEqual(self.before, report["generated_document_checksum"])
        Document(output)  # python-docx can open the result

    def test_schema_and_checksums_are_recorded(self):
        output, report = self.make()
        self.assertEqual(report["source_template_checksum"], self.before)
        self.assertEqual(report["generated_document_checksum"], digest(output))
        self.assertEqual(len(report["input_data_checksum"]), 64)
        self.assertEqual(json.loads(output.with_suffix(".validation.json").read_text())["generation_status"], "success")
        self.assertEqual(json.loads(SCHEMA.read_text())["title"], "OCVS SDD Draft Generation Input")

    def test_missing_mandatory_data_blocks_generation(self):
        fixture = self.fixture_variant(lambda d: d["document"].pop("customer_name"))
        with self.assertRaisesRegex(GenerationError, "document.customer_name"):
            self.make(fixture)

    def test_scalar_values_populate_and_draft_watermark_remains(self):
        output, report = self.make()
        _, tags, text = package_data(output)
        self.assertIn("Northstar Robotics (Fictional)", text)
        self.assertIn("DRAFT — NOT FOR CUSTOMER DELIVERY", text)
        self.assertIn("customer_name", report["populated_controls"])
        self.assertIn("customer_name", tags)  # editable content control remains

    def test_repeatable_rows_have_expected_counts_and_no_empty_seed(self):
        output, report = self.make(MULTI)
        _, tags, text = package_data(output)
        self.assertEqual(report["repeated_row_counts"]["source_cluster_rows"], 3)
        self.assertEqual(report["repeated_row_counts"]["target_ocvs_cluster_rows"], 3)
        self.assertEqual(tags.count("source_cluster_rows_item"), 3)
        self.assertEqual(tags.count("target_ocvs_cluster_rows_item"), 3)
        self.assertNotIn("[[SDT:", text)

    def test_single_and_multi_sections_are_mutually_exclusive(self):
        single, single_report = self.make(SINGLE, "single.docx")
        multi, multi_report = self.make(MULTI, "multi.docx")
        self.assertIn("section_single_cluster", single_report["enabled_conditional_sections"])
        self.assertIn("section_multi_cluster", single_report["excluded_conditional_sections"])
        self.assertIn("section_multi_cluster", multi_report["enabled_conditional_sections"])
        self.assertIn("section_single_cluster", multi_report["excluded_conditional_sections"])
        for output in (single, multi):
            self.assertFalse(any(tag.startswith("section_") for tag in package_data(output)[1]))

    def test_standard_includes_block_volume_and_excludes_vsan(self):
        _, report = self.make()
        self.assertIn("section_block_volume", report["enabled_conditional_sections"])
        self.assertIn("section_vsan", report["excluded_conditional_sections"])
        self.assertIn("section_standard_optimized", report["enabled_conditional_sections"])
        self.assertIn("section_denseio", report["excluded_conditional_sections"])

    def test_dense_includes_vsan_and_excludes_block_volume(self):
        def dense(d):
            d["sizing"].update({"selected_shape": "BM.DenseIO.E5.128", "selected_profile": "Dense storage", "storage_architecture": "vSAN"})
            d["target_clusters"][0].update({"selected_shape": "BM.DenseIO.E5.128", "selected_profile": "Dense storage", "storage_architecture": "vSAN"})
        _, report = self.make(self.fixture_variant(dense))
        self.assertIn("section_vsan", report["enabled_conditional_sections"])
        self.assertIn("section_block_volume", report["excluded_conditional_sections"])
        self.assertIn("section_denseio", report["enabled_conditional_sections"])

    def test_only_selected_provider_and_no_oracle_lift(self):
        _, report = self.make(MULTI)
        self.assertIn("section_partner_managed", report["enabled_conditional_sections"])
        self.assertIn("section_customer_managed", report["excluded_conditional_sections"])
        self.assertIn("section_oracle_managed", report["excluded_conditional_sections"])
        self.assertIn("section_oracle_lift", report["excluded_conditional_sections"])

    def test_oracle_lift_requires_explicit_oracle_provider(self):
        fixture = self.fixture_variant(lambda d: d["section_flags"].update({"include_oracle_lift": True}))
        with self.assertRaisesRegex(GenerationError, "Oracle Lift"):
            self.make(fixture)

    def test_invalid_multicluster_minimum_hosts_is_rejected(self):
        data = json.loads(MULTI.read_text())
        data["target_clusters"][0]["workload_nodes"] = 2
        data["target_clusters"][0]["total_nodes"] = 2
        path = self.out_dir / "bad-multi.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(GenerationError, "at least 3"):
            self.make(path)

    def test_no_forbidden_placeholders_or_visible_conditional_markers(self):
        for fixture, name in ((SINGLE, "single.docx"), (MULTI, "multi.docx")):
            output, _ = self.make(fixture, name)
            _, _, text = package_data(output)
            lowered = text.lower()
            for forbidden in ("a company making everything", "example@example.com", "insert region", "xxxxx", "<customer>", "[[section:"):
                self.assertNotIn(forbidden, lowered)

    def test_generated_document_remains_editable(self):
        output, _ = self.make(MULTI)
        _, tags, _ = package_data(output)
        self.assertGreater(len(tags), 100)
        self.assertIn("target_cluster_name", tags)
        self.assertIn("customer_name", tags)


if __name__ == "__main__":
    unittest.main()
