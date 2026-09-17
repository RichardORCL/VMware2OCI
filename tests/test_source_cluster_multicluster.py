import unittest
from unittest.mock import patch
import tempfile
import zipfile
from pathlib import Path

from werkzeug.datastructures import MultiDict

import app


ROOT = Path(__file__).resolve().parents[1]


def slide_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )


class SourceClusterSizingTests(unittest.TestCase):
    def test_source_cluster_resolution_prefers_cluster_then_resource_pool(self):
        self.assertEqual(app.resolve_source_cluster({"Cluster": "Production"}), "Production")
        self.assertEqual(
            app.resolve_source_cluster({"Resource Pool": "Datacenter/Cluster-DR/Resources/App"}),
            "Cluster-DR",
        )
        self.assertEqual(app.resolve_source_cluster({"VM": "orphan"}), "Unassigned source cluster")

    def test_cluster_summary_preserves_selection_and_capacity(self):
        rows = [
            {"vm_name": "a", "source_cluster": "Cluster A", "cpus": 2, "memory_gb": 8, "provisioned_gb": 100},
            {"vm_name": "b", "source_cluster": "Cluster A", "cpus": 4, "memory_gb": 16, "provisioned_gb": 200},
            {"vm_name": "c", "source_cluster": "Cluster B", "cpus": 1, "memory_gb": 4, "provisioned_gb": 50},
        ]
        summaries = app.build_source_cluster_summaries(rows, ["a", "b"])
        self.assertEqual([item["name"] for item in summaries], ["Cluster A", "Cluster B"])
        self.assertEqual(summaries[0]["selected_vm_count"], 2)
        self.assertEqual(summaries[0]["vcpus"], 6)
        self.assertEqual(summaries[0]["memory_gb"], 24)
        self.assertEqual(summaries[0]["storage_gb"], 300)
        self.assertTrue(summaries[0]["fully_selected"])
        self.assertFalse(summaries[1]["fully_selected"])

    def test_multi_cluster_form_rejects_duplicate_and_missing_assignments(self):
        form = MultiDict(
            [
                ("ocvs_topology", "multi"),
                ("ocvs_target_enabled_0", "1"),
                ("ocvs_target_name_0", "Management"),
                ("ocvs_target_sources_0", "Cluster A"),
                ("ocvs_target_enabled_1", "1"),
                ("ocvs_target_name_1", "Applications"),
                ("ocvs_target_sources_1", "Cluster A"),
            ]
        )
        topology, clusters, errors = app.parse_ocvs_target_cluster_form(
            form, "ocvs", ["Cluster A", "Cluster B"]
        )
        self.assertEqual(topology, "multi")
        self.assertEqual(len(clusters), 2)
        self.assertTrue(any("only one" in error for error in errors))
        self.assertTrue(any("every selected" in error for error in errors))

    def test_multi_cluster_form_rejects_a_seventh_cluster(self):
        items = [("ocvs_topology", "multi")]
        available = []
        for index in range(7):
            source = f"Cluster {index + 1}"
            available.append(source)
            items.extend(
                [
                    (f"ocvs_target_enabled_{index}", "1"),
                    (f"ocvs_target_name_{index}", f"Target {index + 1}"),
                    (f"ocvs_target_sources_{index}", source),
                ]
            )
        _topology, clusters, errors = app.parse_ocvs_target_cluster_form(
            MultiDict(items), "ocvs", available
        )
        self.assertEqual(len(clusters), 6)
        self.assertTrue(any("at most six" in error for error in errors))

    def test_multi_cluster_summary_uses_cluster_scopes_and_minimum_hosts(self):
        rows = [
            {"vm_name": "a", "source_cluster": "Cluster A", "cpus": 2, "memory_gb": 8, "provisioned_gb": 100},
            {"vm_name": "b", "source_cluster": "Cluster B", "cpus": 4, "memory_gb": 16, "provisioned_gb": 200},
        ]
        targets = [
            {"name": "Management", "source_clusters": ["Cluster A"], "profile": "BM.Standard.E4.128"},
            {"name": "Applications", "source_clusters": ["Cluster B"], "profile": "BM.Standard.E4.128"},
        ]
        calls = []

        def fake_price_summary(**kwargs):
            calls.append(kwargs)
            minimum = int(kwargs.get("minimum_hosts") or 0)
            scoped = kwargs["vm_rows"]
            return {
                "totals": {"storage_gb": sum(row["provisioned_gb"] for row in scoped)},
                "selected": {
                    "shape": kwargs["selected_profile"],
                    "host_type": "Standard",
                    "host_count": minimum,
                    "selection_monthly_cost": minimum * 100.0,
                },
            }

        with patch.object(app, "build_ocvs_price_summary", side_effect=fake_price_summary):
            summary = app.build_ocvs_multi_cluster_summary(
                rows,
                targets,
                price_lookup={},
                block_storage_unit_price=0.0,
                block_perf_unit_price=0.0,
                iaas_discount_pct=0.0,
                policy={},
                default_profile="best_fit",
                dr_node_count=0,
                vmware_license_price_per_core_yearly=0.0,
                ocvs_commitment_term="payg",
            )

        self.assertTrue(summary["is_valid"])
        self.assertEqual(summary["cluster_count"], 2)
        self.assertEqual([item["vm_names"] for item in summary["clusters"]], [["a"], ["b"]])
        self.assertEqual([call["minimum_hosts"] for call in calls], [3, 2])
        self.assertEqual(summary["total_hosts"], 5)
        self.assertEqual(summary["total_storage_gb"], 300)

    def test_multi_cluster_standard2_bundled_rate_populates_pricing_slides(self):
        rows = [
            {"vm_name": "a", "source_cluster": "Cluster A", "cpus": 20, "memory_gb": 128, "provisioned_gb": 1000},
            {"vm_name": "b", "source_cluster": "Cluster B", "cpus": 24, "memory_gb": 160, "provisioned_gb": 2000},
        ]
        targets = [
            {"name": "Management", "source_clusters": ["Cluster A"], "profile": "BM.Standard2.52"},
            {"name": "Applications", "source_clusters": ["Cluster B"], "profile": "BM.Standard2.52"},
        ]
        summary = app.build_ocvs_multi_cluster_summary(
            rows,
            targets,
            price_lookup={"Compute - Virtual Machine Standard - X7": 0.059334},
            block_storage_unit_price=0.023715,
            block_perf_unit_price=0.001581,
            iaas_discount_pct=0.0,
            policy={},
            default_profile="BM.Standard2.52",
            dr_node_count=0,
            vmware_license_price_per_core_yearly=0.0,
            ocvs_commitment_term="payg",
        )

        self.assertTrue(all(cluster["selected"]["pricing_available"] for cluster in summary["clusters"]))
        replacements = app._presentation_ocvs_multi_pricing_replacements(summary, "EUR")
        self.assertNotEqual(
            replacements["editable-ocvs-pricing-payg-monthly-total"],
            "Not available",
        )

    def test_ocvs_results_view_uses_multi_cluster_aggregate(self):
        context = {
            "scenario_comparison": {
                "rows": [
                    {
                        "id": "ocvs",
                        "monthly_cost": 999.0,
                        "yearly_cost": 11988.0,
                        "cost_per_vm": 499.5,
                        "native_vm_count": 0,
                        "ocvs_vm_count": 2,
                    }
                ]
            },
            "scenario_chart_rows": [],
            "cost_breakdown_rows": [],
            "overall": {"vm_count": 2},
            "ocvs_price": {"selected": {"host_count": 3}},
            "hybrid_ocvs_price": {"selected": {}},
            "vmware_license_summary": {
                "ocvs": {"physical_cores": 0, "monthly_cost": 0},
                "hybrid": {"physical_cores": 0, "monthly_cost": 0},
            },
            "supported_native_summary": {"total_monthly_cost": 0},
            "iaas_discount_pct": 0,
            "ocvs_multi_cluster": {
                "is_valid": True,
                "topology": "multi",
                "sddc_count": 1,
                "cluster_count": 2,
                "total_hosts": 5,
                "total_monthly_cost": 500.0,
                "total_annual_cost": 6000.0,
                "clusters": [
                    {"name": "Management", "source_clusters": ["Cluster A"]},
                    {"name": "Applications", "source_clusters": ["Cluster B"]},
                ],
            },
        }

        result = app.build_scenario_view("ocvs", context)

        self.assertEqual(result["title"], "Multi-cluster OCVS migration results")
        self.assertIs(result["multi_cluster"], context["ocvs_multi_cluster"])
        self.assertEqual(result["scenario"]["monthly_cost"], 500.0)
        self.assertEqual(result["scenario"]["yearly_cost"], 6000.0)
        self.assertEqual(result["scenario"]["cost_per_vm"], 250.0)
        self.assertEqual(result["cards"][2]["value"], 5)
        self.assertEqual(result["cards"][3]["value"], 2)

        readiness = {
            "overall_state": "customer_ready",
            "scenarios": {
                "ocvs": {
                    "state": "ready",
                    "pricing_state": "complete",
                    "technical_eligibility": "eligible",
                    "rankable": True,
                }
            },
        }
        with app.app.test_request_context("/step4?tab=price"):
            page = app.build_results_page_context(readiness, [result], {})
        ocvs_result = next(item for item in page["scenarios"] if item["id"] == "ocvs")
        self.assertIs(ocvs_result["multi_cluster"], context["ocvs_multi_cluster"])

    def test_presentation_uses_legacy_single_cluster_and_dynamic_multi_cluster_slides(self):
        workload = {
            "vm_count": 2,
            "powered_on_count": 2,
            "powered_off_count": 0,
            "total_vcpus": 6,
            "total_memory_gb": 24,
            "total_storage_gb": 300,
        }
        ocvs = {
            "policy": {},
            "totals": {"storage_gb": 400},
            "selected": {"shape": "BM.Standard.E4.128", "host_count": 3, "cluster_count": 1},
        }
        consolidated = {
            "workload_summary": workload,
            "overall": {},
            "supported_native_summary": {},
            "sizing_scope_mode": "consolidated",
        }
        multi = {
            **consolidated,
            "sizing_scope_mode": "source_cluster",
            "source_cluster_summaries": [
                {"name": "Cluster A", "selected_vm_count": 1, "vcpus": 2, "memory_gb": 8, "storage_gb": 100},
                {"name": "Cluster B", "selected_vm_count": 1, "vcpus": 4, "memory_gb": 16, "storage_gb": 200},
            ],
            "ocvs_multi_cluster": {
                "topology": "multi",
                "sddc_count": 1,
                "cluster_count": 2,
                "total_hosts": 5,
                "total_storage_gb": 400,
                "clusters": [
                    {"name": "Management", "vm_count": 1, "selected": {"shape": "BM.Standard.E4.128", "host_count": 3}, "totals": {"storage_gb": 150}, "storage_architecture": "OCI Block Volume (Block Storage)"},
                    {"name": "Applications", "vm_count": 1, "selected": {"shape": "BM.Standard.E4.128", "host_count": 2}, "totals": {"storage_gb": 250}, "storage_architecture": "OCI Block Volume (Block Storage)"},
                ],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            single_path = Path(tmp) / "single.pptx"
            multi_path = Path(tmp) / "multi.pptx"
            for analysis, output in ((consolidated, single_path), (multi, multi_path)):
                app.build_customer_presentation_pptx(
                    template_path=ROOT / "presentation_templates/Oracle Cloud VMware Solution.pptx",
                    output_path=output,
                    customer_name="Acme",
                    business_scenario={"id": "ocvs", "name": "Move to OCVS"},
                    analysis=analysis,
                    ocvs_price=ocvs,
                    generated_at="2026-09-09T12:00:00",
                )
            single_text = slide_xml(single_path)
            multi_text = slide_xml(multi_path)
        self.assertNotIn("Target OCVS Cluster Distribution", single_text)
        self.assertIn("Target OCVS Cluster Distribution", multi_text)
        self.assertIn("Cluster A", multi_text)
        self.assertIn("Applications", multi_text)

    def test_migration_plan_contract_contains_neutral_planning_fields(self):
        rows = [
            {
                "vm_name": "app-01",
                "source_cluster": "Cluster A",
                "source_vcenter": "vcsa-01",
                "source_datacenter": "DC1",
                "oci_shape": "S3",
                "native_status": "Supported",
                "power_state": "poweredOn",
            }
        ]
        records = app.build_migration_plan_records(
            rows,
            {"rows": [{"vm_name": "app-01", "hybrid_effective_target": "native"}]},
        )
        record = records[0]
        self.assertEqual(record["target_platform"], "OCI Native")
        self.assertEqual(record["target_shape"], "VM.Standard3.Flex")
        self.assertEqual(record["migration_priority"], "High")
        self.assertEqual(record["readiness_status"], "Supported")
        self.assertIn("validation_status", record)
        self.assertIn("notes", record)


if __name__ == "__main__":
    unittest.main()
