import tempfile
import unittest
import zipfile
from pathlib import Path

import app


ROOT = Path(__file__).resolve().parents[1]


def resolve_presentation(active_scenario: str, business_scenario: dict) -> str:
    path, _label = app.resolve_presentation_template(
        business_scenario,
        assessor_recommendation="",
        active_scenario=active_scenario,
    )
    return path.name


def _slide_xml(pptx_path: Path) -> str:
    with zipfile.ZipFile(pptx_path) as archive:
        return "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )


def _named_shape_texts(pptx_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with zipfile.ZipFile(pptx_path) as archive:
        for name in archive.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            xml = archive.read(name).decode("utf-8")
            for shape in app.re.findall(r"<p:sp\b.*?</p:sp>", xml, flags=app.re.DOTALL):
                shape_name = app.re.search(r'<p:cNvPr\b[^>]*\bname="([^"]*)"', shape)
                if not shape_name:
                    continue
                text = "\n".join(app.re.findall(r"<a:t[^>]*>(.*?)</a:t>", shape, flags=app.re.DOTALL))
                values[shape_name.group(1)] = text
    return values


def _slide_titles_in_display_order(pptx_path: Path) -> list[str]:
    import xml.etree.ElementTree as element_tree

    presentation_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    relationship_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(pptx_path) as archive:
        presentation = element_tree.fromstring(archive.read("ppt/presentation.xml"))
        relationships = element_tree.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"].lstrip("/") for item in relationships}
        titles = []
        for slide_id in presentation.findall(f".//{{{presentation_ns}}}sldId"):
            relationship_id = slide_id.attrib[f"{{{relationship_ns}}}id"]
            target = targets[relationship_id]
            part = target if target.startswith("ppt/") else f"ppt/{target}"
            text = archive.read(part).decode("utf-8")
            titles.append(
                "Current Environment" if "Current Environment" in text
                else "Assumptions & Methodology" if "Assumptions &amp; Methodology" in text
                else "OCVS Multi-Cluster Pricing Summary" if "OCVS Multi-Cluster Pricing Summary" in text
                else "OCVS Pricing Detail by Target Cluster" if "OCVS Pricing Detail by Target Cluster" in text
                else "OCVS Pricing Summary" if "OCVS Pricing Summary" in text
                else "OCI Native Pricing Summary" if "OCI Native Pricing Summary" in text
                else "Hybrid Pricing Summary" if "Hybrid Pricing Summary" in text
                else ""
            )
    return titles


def _analysis() -> dict:
    return {
        "workload_summary": {
            "vm_count": 10,
            "powered_on_count": 8,
            "powered_off_count": 2,
            "total_vcpus": 40,
            "total_memory_gb": 160,
            "total_storage_gb": 3072,
        },
        "overall": {
            "vm_count": 10,
            "total_cpus": 40,
            "total_memory_gb": 160,
            "total_provisioned_gb": 3072,
            "total_vpus": 100,
        },
        "supported_native_summary": {
            "vm_count": 6,
            "total_cpus": 24,
            "total_memory_gb": 96,
            "total_provisioned_gb": 2048,
            "total_vpus": 60,
        },
        "hybrid_ocvs_price": {
            "policy": {"vcpu_per_ocpu": 4.0},
            "totals": {"storage_gb": 1024},
            "selected": {
                "host_count": 3,
                "cluster_count": 1,
                "shape": "BM.DenseIO.E5.128",
            },
        },
    }


class PresentationExportTests(unittest.TestCase):
    def test_scenario_workspace_choice_is_persisted_without_save(self):
        client = app.app.test_client()
        response = client.post("/step4/presentation-scenario", data={"scenario": "hybrid"})
        self.assertEqual(response.status_code, 204)
        with client.session_transaction() as session_state:
            self.assertEqual(session_state["presentation_scenario"], "hybrid")

    def test_template_selection_follows_active_step3_scenario(self):
        standard = {"id": "compute", "name": "OCI Compute Migration"}
        self.assertEqual(resolve_presentation("native", standard), "OCI Compute Migration.pptx")
        self.assertEqual(resolve_presentation("ocvs", standard), "Oracle Cloud VMware Solution.pptx")
        self.assertEqual(resolve_presentation("hybrid", standard), "OCI Hybrid.pptx")
        self.assertEqual(
            resolve_presentation("native", {"id": "capacity", "name": "Capacity Expansion with OCVS"}),
            "Capacity Expansion with OCVS.pptx",
        )
        self.assertEqual(
            resolve_presentation("hybrid", {"id": "ocvs", "name": "Move to OCVS"}),
            "Oracle Cloud VMware Solution.pptx",
        )
        self.assertEqual(
            resolve_presentation("native", {"id": "dr", "name": "Disaster Recovery"}),
            "Disaster Recovery.pptx",
        )

    def test_dedicated_scenarios_ignore_a_stale_workspace_selection(self):
        for scenario_id, expected_template in {
            "ocvs": "Oracle Cloud VMware Solution.pptx",
            "capacity": "Capacity Expansion with OCVS.pptx",
            "dr": "Disaster Recovery.pptx",
        }.items():
            with self.subTest(scenario_id=scenario_id):
                self.assertEqual(
                    resolve_presentation("hybrid", {"id": scenario_id, "name": "Stale selection test"}),
                    expected_template,
                )

    def test_storage_type_rules(self):
        self.assertEqual(app._presentation_storage_type("BM.Standard.E5.128"), "OCI Block Volume (Block Storage)")
        self.assertEqual(app._presentation_storage_type("BM.Optimized.E5.128"), "OCI Block Volume (Block Storage)")
        self.assertEqual(app._presentation_storage_type("BM.DenseIO.E5.128"), "vSAN")
        self.assertEqual(app._presentation_storage_type("unknown"), "Not provided")

    def test_storage_formatting_uses_compact_tb_without_double_conversion(self):
        self.assertEqual(app._presentation_tb_number(1024), "1")
        self.assertEqual(app._presentation_tb_number("1024 GB"), "1")
        self.assertEqual(app._presentation_tb_number("300.5 TB"), "300.5")
        self.assertEqual(app._presentation_tb_number("200 TB"), "200")
        self.assertEqual(app.format_storage_gb_and_tb(34087), "34,087 GB (33.3 TB)")

    def test_ocvs_workspace_shows_capacity_requirement_in_gb_and_tb(self):
        template = (ROOT / "templates" / "_scenario_ocvs.html").read_text(encoding="utf-8")
        self.assertIn(
            "format_storage_gb_and_tb(ocvs_totals.storage_gb)",
            template,
        )

    def test_ocvs_templates_keep_current_environment_before_assumptions(self):
        for filename in (
            "Oracle Cloud VMware Solution.pptx",
            "Capacity Expansion with OCVS.pptx",
            "Disaster Recovery.pptx",
        ):
            with self.subTest(filename=filename):
                titles = _slide_titles_in_display_order(ROOT / "presentation_templates" / filename)
                self.assertEqual(titles[2], "Current Environment")
                self.assertEqual(titles[3], "Assumptions & Methodology")
                self.assertEqual(titles[5], "OCVS Pricing Summary")

    def test_ocvs_pricing_summary_calculates_all_commitment_terms(self):
        values = app._presentation_ocvs_pricing_replacements(
            {
                "pricing_available": True,
                "shape": "BM.Standard.E4.128",
                "host_count": 2,
                # This is the selected 3-year discounted monthly host rate.
                "host_monthly_cost": 550,
                "storage_monthly_cost": 300,
                "commitment_discount_pct": 45,
            },
            "EUR",
        )
        self.assertEqual(values["editable-ocvs-pricing-payg-infrastructure"], "€2,000")
        self.assertEqual(values["editable-ocvs-pricing-payg-storage"], "€300")
        self.assertEqual(values["editable-ocvs-pricing-payg-monthly-total"], "€2,300")
        self.assertEqual(values["editable-ocvs-pricing-payg-annual-total"], "€27,600")
        self.assertEqual(values["editable-ocvs-pricing-one-year-monthly-total"], "€1,600")
        self.assertEqual(values["editable-ocvs-pricing-three-year-monthly-total"], "€1,400")

    def test_ocvs_pricing_summary_fails_closed_when_pricing_is_unavailable(self):
        values = app._presentation_ocvs_pricing_replacements(
            {"pricing_available": False, "host_count": 3}, "USD"
        )
        self.assertEqual(set(values.values()), {"Not available"})

    def test_multi_cluster_pricing_aggregates_each_selected_cluster(self):
        clusters = {
            "topology": "multi",
            "clusters": [
                {
                    "name": "Management",
                    "source_clusters": ["A", "B"],
                    "selected": {
                        "pricing_available": True,
                        "shape": "BM.Standard.E4.128",
                        "host_count": 2,
                        "host_monthly_cost": 1000,
                        "storage_monthly_cost": 100,
                        "commitment_discount_pct": 0,
                        "commitment_term": "payg",
                    },
                },
                {
                    "name": "Applications",
                    "source_clusters": ["C"],
                    "selected": {
                        "pricing_available": True,
                        "shape": "BM.DenseIO.E5.128",
                        "host_count": 3,
                        "host_monthly_cost": 500,
                        "storage_monthly_cost": 0,
                        "commitment_discount_pct": 0,
                        "commitment_term": "payg",
                    },
                },
            ],
        }
        values = app._presentation_ocvs_multi_pricing_replacements(clusters, "EUR")
        self.assertEqual(values["editable-ocvs-pricing-payg-infrastructure"], "€3,500")
        self.assertEqual(values["editable-ocvs-pricing-payg-storage"], "€100")
        self.assertEqual(values["editable-ocvs-pricing-payg-monthly-total"], "€3,600")
        detail = app._presentation_ocvs_pricing_detail_replacements(clusters, "EUR")
        self.assertEqual(detail["editable-ocvs-pricing-detail-row-1-monthly"], "€2,100")
        self.assertEqual(detail["editable-ocvs-pricing-detail-row-2-monthly"], "€1,500")
        self.assertEqual(detail["editable-ocvs-pricing-detail-total-monthly"], "€3,600")

    def test_multi_cluster_pricing_fails_closed_if_one_cluster_is_unavailable(self):
        clusters = {
            "topology": "multi",
            "clusters": [
                {"name": "Priced", "selected": {"pricing_available": True, "shape": "BM.Standard.E4.128", "host_count": 2, "host_monthly_cost": 1000, "storage_monthly_cost": 100, "commitment_discount_pct": 0}},
                {"name": "Missing", "selected": {"pricing_available": False, "host_count": 2}},
            ],
        }
        summary = app._presentation_ocvs_multi_pricing_replacements(clusters, "EUR")
        self.assertEqual(summary["editable-ocvs-pricing-payg-monthly-total"], "Not available")
        detail = app._presentation_ocvs_pricing_detail_replacements(clusters, "EUR")
        self.assertEqual(detail["editable-ocvs-pricing-detail-row-2-monthly"], "Not available")
        self.assertEqual(detail["editable-ocvs-pricing-detail-total-monthly"], "Not available")

    def test_multi_cluster_ocvs_and_hybrid_exports_add_detail_without_empty_rows(self):
        selected = lambda shape, hosts, rate, storage: {
            "pricing_available": True,
            "shape": shape,
            "host_count": hosts,
            "cluster_count": 1,
            "host_monthly_cost": rate,
            "storage_monthly_cost": storage,
            "commitment_discount_pct": 0,
            "commitment_term": "payg",
        }
        multi = {
            "topology": "multi",
            "sddc_count": 1,
            "cluster_count": 2,
            "total_hosts": 5,
            "total_storage_gb": 4096,
            "clusters": [
                {"name": "Management", "source_clusters": ["A"], "vm_count": 4, "selected": selected("BM.Standard.E4.128", 3, 1000, 200), "totals": {"storage_gb": 2048}, "storage_architecture": "OCI Block Volume (Block Storage)"},
                {"name": "Applications", "source_clusters": ["B", "C"], "vm_count": 6, "selected": selected("BM.DenseIO.E5.128", 2, 800, 0), "totals": {"storage_gb": 2048}, "storage_architecture": "vSAN"},
            ],
        }
        ocvs_price = {"policy": {}, "totals": {"storage_gb": 4096}, "selected": selected("BM.Standard.E4.128", 5, 1000, 200)}
        base = _analysis()
        with tempfile.TemporaryDirectory() as tmp:
            ocvs_output = Path(tmp) / "ocvs-multi.pptx"
            hybrid_output = Path(tmp) / "hybrid-multi.pptx"
            ocvs_analysis = {**base, "sizing_scope_mode": "source_cluster", "ocvs_multi_cluster": multi}
            hybrid_analysis = {
                **base,
                "sizing_scope_mode": "source_cluster",
                "hybrid_ocvs_multi_cluster": multi,
                "supported_native_summary": {**base["supported_native_summary"], "total_monthly_cost": 500},
            }
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/Oracle Cloud VMware Solution.pptx",
                output_path=ocvs_output,
                customer_name="Acme",
                business_scenario={"id": "ocvs", "name": "Move to OCVS"},
                analysis=ocvs_analysis,
                ocvs_price=ocvs_price,
                generated_at="2026-09-10T12:00:00",
                pricing_currency="EUR",
            )
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/OCI Hybrid.pptx",
                output_path=hybrid_output,
                customer_name="Acme",
                business_scenario={"id": "hybrid", "name": "Hybrid"},
                analysis=hybrid_analysis,
                ocvs_price=ocvs_price,
                generated_at="2026-09-10T12:00:00",
                pricing_currency="EUR",
            )
            ocvs_titles = _slide_titles_in_display_order(ocvs_output)
            hybrid_titles = _slide_titles_in_display_order(hybrid_output)
            ocvs_text = _slide_xml(ocvs_output)
            hybrid_text = _slide_xml(hybrid_output)
            hybrid_values = _named_shape_texts(hybrid_output)
        self.assertEqual(ocvs_titles[5:7], ["OCVS Multi-Cluster Pricing Summary", "OCVS Pricing Detail by Target Cluster"])
        self.assertEqual(hybrid_titles[-2:], ["Hybrid Pricing Summary", "OCVS Pricing Detail by Target Cluster"])
        self.assertEqual(ocvs_text.count("OCVS Multi-Cluster Pricing Summary"), 1)
        self.assertEqual(ocvs_text.count("OCVS Pricing Detail by Target Cluster"), 1)
        self.assertEqual(hybrid_text.count("OCVS Pricing Detail by Target Cluster"), 1)
        self.assertNotIn("editable-ocvs-pricing-detail-row-3-cluster", ocvs_text)
        self.assertEqual(hybrid_values["editable-hybrid-pricing-payg-ocvs"], "€4,800")
        self.assertEqual(hybrid_values["editable-hybrid-pricing-payg-monthly-total"], "€5,300")

    def test_ocvs_exports_include_one_dynamic_pricing_summary_slide(self):
        ocvs_price = {
            "policy": {"vcpu_per_ocpu": 4.0},
            "totals": {"storage_gb": 3072},
            "selected": {
                "pricing_available": True,
                "shape": "BM.Standard.E4.128",
                "host_count": 2,
                "cluster_count": 1,
                "host_monthly_cost": 550,
                "storage_monthly_cost": 300,
                "commitment_discount_pct": 45,
            },
        }
        templates = {
            "ocvs": "Oracle Cloud VMware Solution.pptx",
            "capacity": "Capacity Expansion with OCVS.pptx",
            "dr": "Disaster Recovery.pptx",
        }
        with tempfile.TemporaryDirectory() as tmp:
            for scenario_id, filename in templates.items():
                with self.subTest(filename=filename):
                    output = Path(tmp) / filename
                    app.build_customer_presentation_pptx(
                        template_path=ROOT / "presentation_templates" / filename,
                        output_path=output,
                        customer_name="Acme",
                        business_scenario={"id": scenario_id, "name": scenario_id},
                        analysis=_analysis(),
                        ocvs_price=ocvs_price,
                        generated_at="2026-09-06T12:00:00",
                        pricing_currency="EUR",
                    )
                    with zipfile.ZipFile(output) as archive:
                        self.assertIsNone(archive.testzip())
                    titles = _slide_titles_in_display_order(output)
                    self.assertEqual(titles.count("OCVS Pricing Summary"), 1)
                    self.assertEqual(titles[5], "OCVS Pricing Summary")
                    values = _named_shape_texts(output)
                    self.assertEqual(values["editable-ocvs-pricing-payg-monthly-total"], "€2,300")
                    self.assertEqual(values["editable-ocvs-pricing-three-year-annual-total"], "€16,800")

    def test_native_and_hybrid_exports_include_dynamic_pricing_summaries(self):
        analysis = _analysis()
        analysis["overall"].update({
            "total_cpu_ram_monthly_cost": 100,
            "total_os_license_monthly_cost": 20,
            "total_storage_monthly_cost": 30,
            "total_monthly_cost": 150,
        })
        analysis["supported_native_summary"].update({
            "total_cpu_ram_monthly_cost": 90,
            "total_os_license_monthly_cost": 10,
            "total_storage_monthly_cost": 20,
            "total_monthly_cost": 120,
        })
        analysis["hybrid_ocvs_price"]["selected"].update({
            "pricing_available": True,
            "host_count": 2,
            "host_monthly_cost": 550,
            "storage_monthly_cost": 300,
            "commitment_discount_pct": 45,
        })
        with tempfile.TemporaryDirectory() as tmp:
            native_output = Path(tmp) / "native.pptx"
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/OCI Compute Migration.pptx",
                output_path=native_output,
                customer_name="Acme",
                business_scenario={"id": "compute", "name": "OCI Compute Migration"},
                analysis=analysis,
                ocvs_price={"selected": {}},
                generated_at="2026-09-06T12:00:00",
                pricing_currency="EUR",
            )
            hybrid_output = Path(tmp) / "hybrid.pptx"
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/OCI Hybrid.pptx",
                output_path=hybrid_output,
                customer_name="Acme",
                business_scenario={"id": "hybrid", "name": "OCI Hybrid"},
                analysis=analysis,
                ocvs_price={"selected": {}},
                generated_at="2026-09-06T12:00:00",
                pricing_currency="EUR",
            )

            for output in (native_output, hybrid_output):
                with zipfile.ZipFile(output) as archive:
                    self.assertIsNone(archive.testzip())

            native_titles = _slide_titles_in_display_order(native_output)
            self.assertEqual(native_titles.count("OCI Native Pricing Summary"), 1)
            self.assertEqual(native_titles[5], "OCI Native Pricing Summary")
            native_values = _named_shape_texts(native_output)
            self.assertEqual(native_values["editable-native-pricing-compute"], "€120")
            self.assertEqual(native_values["editable-native-pricing-storage"], "€30")
            self.assertEqual(native_values["editable-native-pricing-monthly-total"], "€150")
            self.assertEqual(native_values["editable-native-pricing-annual-total"], "€1,800")

            hybrid_titles = _slide_titles_in_display_order(hybrid_output)
            self.assertEqual(hybrid_titles.count("Hybrid Pricing Summary"), 1)
            self.assertEqual(hybrid_titles[5], "Hybrid Pricing Summary")
            hybrid_values = _named_shape_texts(hybrid_output)
            self.assertEqual(hybrid_values["editable-hybrid-pricing-native-monthly"], "€120")
            self.assertEqual(hybrid_values["editable-hybrid-pricing-payg-native"], "€120")
            self.assertEqual(hybrid_values["editable-hybrid-pricing-one-year-native"], "€120")
            self.assertEqual(hybrid_values["editable-hybrid-pricing-three-year-native"], "€120")
            self.assertEqual(hybrid_values["editable-hybrid-pricing-payg-ocvs"], "€2,300")
            self.assertEqual(hybrid_values["editable-hybrid-pricing-payg-monthly-total"], "€2,420")
            self.assertEqual(hybrid_values["editable-hybrid-pricing-three-year-annual-total"], "€17,040")

    def test_hybrid_pricing_keeps_native_cost_when_ocvs_term_is_unavailable(self):
        values = app._presentation_hybrid_pricing_replacements(
            native_summary={"total_monthly_cost": 125},
            selected_ocvs={"pricing_available": False},
            pricing_currency="USD",
        )
        self.assertEqual(values["editable-hybrid-pricing-native-monthly"], "$125")
        self.assertEqual(values["editable-hybrid-pricing-payg-native"], "$125")
        self.assertEqual(values["editable-hybrid-pricing-payg-ocvs"], "Not available")
        self.assertEqual(values["editable-hybrid-pricing-payg-monthly-total"], "Not available")

    def test_ocvs_generated_exports_keep_current_environment_before_assumptions(self):
        ocvs_price = {
            "policy": {
                "vcpu_per_ocpu": 4,
                "cpu_headroom_pct": 20,
                "memory_headroom_pct": 20,
                "storage_headroom_pct": 25,
                "dense_vsan_usable_pct": 50,
                "standard_storage_vpu": 10,
            },
            "totals": {"storage_gb": 3072},
            "selected": {"host_count": 3, "cluster_count": 1, "shape": "BM.Standard.E5.128"},
        }
        templates = {
            "ocvs": "Oracle Cloud VMware Solution.pptx",
            "capacity": "Capacity Expansion with OCVS.pptx",
            "dr": "Disaster Recovery.pptx",
        }
        with tempfile.TemporaryDirectory() as tmp:
            for scenario_id, filename in templates.items():
                with self.subTest(filename=filename):
                    output = Path(tmp) / filename
                    app.build_customer_presentation_pptx(
                        template_path=ROOT / "presentation_templates" / filename,
                        output_path=output,
                        customer_name="Acme",
                        business_scenario={"id": scenario_id, "name": scenario_id},
                        analysis=_analysis(),
                        ocvs_price=ocvs_price,
                        generated_at="2026-09-03T12:00:00",
                    )
                    titles = _slide_titles_in_display_order(output)
                    self.assertEqual(titles[2], "Current Environment")
                    self.assertEqual(titles[3], "Assumptions & Methodology")

    def test_ocvs_template_uses_workload_and_selected_ocvs_values(self):
        ocvs_price = {
            "policy": {"vcpu_per_ocpu": 4.0},
            "totals": {"storage_gb": 3072},
            "selected": {
                "host_count": 4,
                "cluster_count": 1,
                "shape": "BM.Standard.E5.128",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ocvs.pptx"
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/Oracle Cloud VMware Solution.pptx",
                output_path=output,
                customer_name="Acme",
                business_scenario={"id": "ocvs", "name": "Oracle Cloud VMware Solution"},
                analysis=_analysis(),
                ocvs_price=ocvs_price,
                generated_at="2026-08-17T12:00:00",
            )
            xml = _slide_xml(output)
        self.assertIn("Acme", xml)
        self.assertIn("4:1", xml)
        self.assertIn("OCI Block Volume (Block Storage)", xml)
        self.assertIn(">3<", xml)
        self.assertIn(">10<", xml)
        self.assertIn(">40<", xml)

    def test_ocvs_exports_replace_the_assumptions_slide_and_use_selected_scope(self):
        policy = {
            "vcpu_per_ocpu": 4.0,
            "cpu_headroom_pct": 20,
            "memory_headroom_pct": 20,
            "storage_headroom_pct": 25,
            "dense_vsan_usable_pct": 50,
            "standard_storage_vpu": 10,
        }
        templates = {
            "ocvs": "Oracle Cloud VMware Solution.pptx",
            "capacity": "Capacity Expansion with OCVS.pptx",
            "dr": "Disaster Recovery.pptx",
        }
        ocvs_price = {
            "policy": policy,
            # This is the policy-adjusted Workload Capacity Requirement, not
            # the 3 TB raw storage amount held in the selected VM scope.
            "totals": {"storage_gb": 5120},
            "selected": {
                "host_count": 4,
                "cluster_count": 1,
                "shape": "BM.Optimized3.36",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            for scenario_id, filename in templates.items():
                with self.subTest(scenario_id=scenario_id):
                    output = Path(tmp) / filename
                    app.build_customer_presentation_pptx(
                        template_path=ROOT / "presentation_templates" / filename,
                        output_path=output,
                        customer_name="Acme",
                        business_scenario={"id": scenario_id, "name": scenario_id},
                        analysis=_analysis(),
                        ocvs_price=ocvs_price,
                        generated_at="2026-09-03T12:00:00",
                    )
                    with zipfile.ZipFile(output) as archive:
                        self.assertIsNone(archive.testzip())
                    values = _named_shape_texts(output)
                    self.assertEqual(values["editable-current-storage"], "3")
                    self.assertEqual(values["editable-ocvs-storage"], "5")
                    self.assertEqual(values["vcpu-ocpu-value"], "4:1")
                    self.assertEqual(values["cpu-headroom-value"], "20%")
                    self.assertEqual(values["ram-headroom-value"], "20%")
                    self.assertEqual(values["storage-headroom-value"], "25%")
                    self.assertEqual(values["performance-value"], "10 VPU/GB")
                    self.assertIn("OCI Block Volume", values["architecture-value"])
                    self.assertNotIn("Average Utilization", _slide_xml(output))
                    self.assertNotIn("TB TB", _slide_xml(output))

    def test_denseio_ocvs_exports_use_the_vsan_assumptions_slide(self):
        ocvs_price = {
            "policy": {
                "vcpu_per_ocpu": 4.0,
                "cpu_headroom_pct": 20,
                "memory_headroom_pct": 20,
                "storage_headroom_pct": 25,
                "dense_vsan_usable_pct": 50,
                "standard_storage_vpu": 10,
            },
            "totals": {"storage_gb": 3072},
            "selected": {
                "host_count": 3,
                "cluster_count": 1,
                "shape": "BM.DenseIO.E5.128",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ocvs-denseio.pptx"
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/Oracle Cloud VMware Solution.pptx",
                output_path=output,
                customer_name="Acme",
                business_scenario={"id": "ocvs", "name": "Move to OCVS"},
                analysis=_analysis(),
                ocvs_price=ocvs_price,
                generated_at="2026-09-03T12:00:00",
            )
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
            values = _named_shape_texts(output)
        self.assertEqual(values["vsan-usable-value"], "50%")
        self.assertIn("vSAN", values["storage-architecture-value"])
        self.assertNotIn("performance-value", values)

    def test_hybrid_template_uses_hybrid_ocvs_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "hybrid.pptx"
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/OCI Hybrid.pptx",
                output_path=output,
                customer_name="Acme",
                business_scenario={"id": "hybrid", "name": "OCI Hybrid"},
                analysis=_analysis(),
                ocvs_price={"policy": {"vcpu_per_ocpu": 6.0}, "selected": {}},
                generated_at="2026-08-17T12:00:00",
            )
            xml = _slide_xml(output)
        self.assertIn("BM.DenseIO.E5.128", xml)
        self.assertIn(">vSAN<", xml)
        self.assertIn("4:1", xml)
        self.assertIn(">6<", xml)
        self.assertIn(">24<", xml)

    def test_final_slide_uses_native_subset_and_aggregates_extra_rows(self):
        native_rows = [
            {"oci_shape": "S3", "ocpu": 1, "memory_gb": 8, "provisioned_gb": 500, "vpu": 10},
            {"oci_shape": "S3", "ocpu": 1, "memory_gb": 8, "provisioned_gb": 500, "vpu": 10},
            {"oci_shape": "E4", "ocpu": 2, "memory_gb": 16, "provisioned_gb": 1200, "vpu": 20},
            {"oci_shape": "E5", "ocpu": 3, "memory_gb": 24, "provisioned_gb": 1000, "vpu": 30},
            {"oci_shape": "E6", "ocpu": 4, "memory_gb": 32, "provisioned_gb": 800, "vpu": 40},
            {"oci_shape": "A1", "ocpu": 5, "memory_gb": 40, "provisioned_gb": 700, "vpu": 50},
        ]
        _shapes, _vpus, totals = app._presentation_native_mix_rows(native_rows)
        self.assertEqual(totals["vms"], 6)
        self.assertEqual(totals["ocpus"], 16)
        self.assertEqual(totals["ram_gb"], 128)
        self.assertEqual(totals["storage_gb"], 4700)
        analysis = _analysis()
        analysis["supported_native_rows"] = native_rows
        with tempfile.TemporaryDirectory() as tmp:
            for filename, scenario_id in (
                ("OCI Compute Migration.pptx", "compute"),
                ("OCI Hybrid.pptx", "hybrid"),
            ):
                output = Path(tmp) / filename
                app.build_customer_presentation_pptx(
                    template_path=ROOT / "presentation_templates" / filename,
                    output_path=output,
                    customer_name="Acme",
                    business_scenario={"id": scenario_id, "name": scenario_id},
                    analysis=analysis,
                    ocvs_price={"policy": {"vcpu_per_ocpu": 4.0}, "selected": {}},
                    generated_at="2026-08-17T12:00:00",
                    native_vm_rows=native_rows,
                )
                xml = _slide_xml(output)
                self.assertIn("VM.Standard3.Flex", xml)
                self.assertIn("Other OCI Compute shapes", xml)
                self.assertIn("Other VPU values", xml)
                self.assertIn(">6<", xml)  # total Native VM count
                self.assertIn(">16<", xml)  # total configured OCPUs
                self.assertIn(">128<", xml)  # total Native RAM, displayed in GB

    def test_compute_summary_removes_unused_dynamic_rows(self):
        native_rows = [
            {"oci_shape": "S3", "ocpu": 2, "memory_gb": 16, "provisioned_gb": 1024, "vpu": 10},
            {"oci_shape": "E5", "ocpu": 4, "memory_gb": 32, "provisioned_gb": 2048, "vpu": 20},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "compute-summary.pptx"
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/OCI Compute Migration.pptx",
                output_path=output,
                customer_name="Acme",
                business_scenario={"id": "compute", "name": "OCI Compute Migration"},
                analysis=_analysis(),
                ocvs_price={"policy": {"vcpu_per_ocpu": 4.0}, "selected": {}},
                generated_at="2026-09-04T12:00:00",
                native_vm_rows=native_rows,
            )
            xml = _slide_xml(output)
        self.assertIn("VM.Standard3.Flex", xml)
        self.assertIn("VM.Standard.E5.Flex", xml)
        self.assertNotIn("editable-native-shape-row-3", xml)
        self.assertNotIn("editable-native-vpu-label-row-3", xml)

    def test_compute_assumptions_use_single_native_configuration(self):
        native_rows = [
            {"oci_shape": "S3", "ocpu": 1, "burst": "100%", "vpu": 10, "os_license": "BYOL", "memory_gb": 8, "provisioned_gb": 100},
            {"oci_shape": "S3", "ocpu": 1, "burst": "100%", "vpu": 10, "os_license": "BYOL", "memory_gb": 8, "provisioned_gb": 100},
        ]
        analysis = _analysis()
        analysis["workload_summary"]["total_vcpus"] = 4
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "compute-assumptions-single.pptx"
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/OCI Compute Migration.pptx",
                output_path=output,
                customer_name="Acme",
                business_scenario={"id": "compute", "name": "OCI Compute Migration"},
                analysis=analysis,
                ocvs_price={"policy": {"vcpu_per_ocpu": 4.0}, "selected": {}},
                generated_at="2026-09-04T12:00:00",
                native_vm_rows=native_rows,
            )
            values = _named_shape_texts(output)
        self.assertEqual(values["editable-native-assumptions-ratio"], "1 OCPU : 2 vCPUs\n(Derived from current OCI Native sizing)")
        self.assertEqual(values["editable-native-assumptions-shapes"], "VM.Standard3.Flex")
        self.assertEqual(values["editable-native-assumptions-ocpu"], "1 OCPU per VM")
        self.assertEqual(values["editable-native-assumptions-burst"], "100%")
        self.assertEqual(values["editable-native-assumptions-license"], "BYOL")
        self.assertEqual(values["editable-native-assumptions-vpu"], "10 VPU/GB")

    def test_compute_assumptions_summarize_multiple_native_configurations(self):
        native_rows = [
            {"oci_shape": "S3", "ocpu": 1, "burst": "100%", "vpu": 10, "os_license": "BYOL", "memory_gb": 8, "provisioned_gb": 100},
            {"oci_shape": "E5", "ocpu": 2, "burst": "50%", "vpu": 20, "os_license": "Lic Include", "memory_gb": 16, "provisioned_gb": 200},
        ]
        analysis = _analysis()
        analysis["workload_summary"]["total_vcpus"] = 6
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "compute-assumptions-multiple.pptx"
            app.build_customer_presentation_pptx(
                template_path=ROOT / "presentation_templates/OCI Compute Migration.pptx",
                output_path=output,
                customer_name="Acme",
                business_scenario={"id": "compute", "name": "OCI Compute Migration"},
                analysis=analysis,
                ocvs_price={"policy": {"vcpu_per_ocpu": 4.0}, "selected": {}},
                generated_at="2026-09-04T12:00:00",
                native_vm_rows=native_rows,
            )
            values = _named_shape_texts(output)
        for name, expected in {
            "editable-native-assumptions-shapes": "Multiple OCI Compute shapes configured per VM",
            "editable-native-assumptions-ocpu": "Configured per VM — multiple values",
            "editable-native-assumptions-burst": "Configured per VM — multiple values",
            "editable-native-assumptions-license": "Configured per VM — multiple values",
            "editable-native-assumptions-vpu": "Configured per VM — multiple VPU tiers",
        }.items():
            self.assertEqual(values[name], expected)

    def test_all_templates_export_as_valid_powerpoint_packages(self):
        templates = {
            "compute": "OCI Compute Migration.pptx",
            "ocvs": "Oracle Cloud VMware Solution.pptx",
            "capacity": "Capacity Expansion with OCVS.pptx",
            "dr": "Disaster Recovery.pptx",
            "hybrid": "OCI Hybrid.pptx",
        }
        ocvs_price = {
            "policy": {"vcpu_per_ocpu": 4.0},
            "totals": {"storage_gb": 3072},
            "selected": {"host_count": 4, "cluster_count": 1, "shape": "BM.Standard.E5.128"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            for scenario_id, filename in templates.items():
                output = Path(tmp) / filename
                app.build_customer_presentation_pptx(
                    template_path=ROOT / "presentation_templates" / filename,
                    output_path=output,
                    customer_name="Acme",
                    business_scenario={"id": scenario_id, "name": scenario_id},
                    analysis=_analysis(),
                    ocvs_price=ocvs_price,
                    generated_at="2026-08-17T12:00:00",
                )
                with zipfile.ZipFile(output) as archive:
                    self.assertIsNone(archive.testzip(), filename)


if __name__ == "__main__":
    unittest.main()
