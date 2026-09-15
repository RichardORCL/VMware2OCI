"""Synthetic Matilda inventories exercise the same VM contract as RVTools."""

import json
import tempfile
import unittest
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import app as app_module
import assessment_portability as portability


MATILDA_HEADERS = [
    "Hostname", "IP", "ESX Host Name", "Cluster", "Logical Processors",
    "Memory(GB)", "Total Storage(GB)", "Used Storage(GB)",
    "Operating System", "OS Version", "Power Status",
]


def vm_record(**changes):
    record = dict(zip(MATILDA_HEADERS, [
        "app-01", "192.0.2.1", "esx-01", "Cluster A", 4,
        8, 100, 900, "Red Hat Enterprise Linux", "8", "Powered On",
    ]))
    record.update(changes)
    return record


def sheet(name, records, headers=None):
    headers = list(headers or MATILDA_HEADERS)
    return {
        "name": name,
        "rows": [headers] + [[record.get(header, "") for header in headers] for record in records],
    }


class MatildaInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        # The mapping loader may create its defaults; keep that side effect local.
        mapping_patch = patch.object(app_module, "OS_MAPPING_CONFIG_PATH", self.root / "os_mapping.json")
        mapping_patch.start()
        self.addCleanup(mapping_patch.stop)

    def workbook(self, sheets, name="Inventory Report.xlsx"):
        path = self.root / name
        path.write_bytes(app_module._build_xlsx_workbook_bytes(sheets, currency_fmt_code="0.00"))
        return str(path)

    def load(self, records, headers=None):
        return app_module.load_vms_from_vinfo(self.workbook([sheet("Vm", records, headers)]))

    @contextmanager
    def upload_client(self):
        downloads = self.root / "downloads"
        app_state = downloads / "app_state"
        catalog = self.root / "rvtools"
        app_state.mkdir(parents=True)
        catalog.mkdir()
        with (
            patch.object(app_module, "DOWNLOADS_DIR", downloads),
            patch.object(app_module, "APP_STATE_DIR", app_state),
            patch.object(app_module, "RVTOOLS_DIR", catalog),
            patch.dict(app_module.app.config, TESTING=True),
            app_module.app.test_client() as client,
        ):
            with client.session_transaction() as session:
                session["_app_instance_id"] = app_module.APP_INSTANCE_ID
                session["state_id"] = "matilda_upload_test"
            yield client, catalog, app_state

    def upload(self, client, path):
        return client.post(
            "/",
            data={
                "action": "upload_rvtools_file",
                "inventory_mode": "upload",
                "rvtools_upload": (BytesIO(Path(path).read_bytes()), Path(path).name),
            },
            content_type="multipart/form-data",
        )

    def test_allocated_resources_use_total_storage_even_when_used_exceeds_total(self):
        rows, source = self.load([
            vm_record(),
            vm_record(Hostname="db-01", **{
                "Logical Processors": 8, "Memory(GB)": 16.5,
                "Total Storage(GB)": 200.25, "Used Storage(GB)": 300,
            }),
        ])

        self.assertEqual(["app-01", "db-01"], [row["name"] for row in rows])
        self.assertEqual([4, 8], [float(row["cpus"]) for row in rows])
        self.assertEqual([8192, 16896], [float(row["memory_mb"]) for row in rows])
        self.assertEqual([102400, 205056], [float(row["provisioned_mib"]) for row in rows])
        self.assertIn("Matilda", source)
        self.assertIn("Vm", source)
        summary = app_module.build_inventory_import_summary(rows, source)
        self.assertEqual(2, summary["vm_count"])
        self.assertEqual(12, summary["total_vcpus"])
        self.assertEqual(25, summary["total_memory_gb"])
        self.assertEqual(301, summary["total_storage_gb"])

    def test_main_vm_sheet_wins_over_larger_infrastructure_and_excluded_tables(self):
        decoys = [vm_record(Hostname=f"excluded-{index}") for index in range(4)]
        generic = {"VM": "aggregate", "CPUs": 500, "Memory": 102400, "Provisioned MiB": 1048576}
        path = self.workbook([
            sheet("Import Summary", [generic], list(generic)),
            sheet("Esx", decoys),
            sheet("Vm Ipv6", decoys),
            sheet("Vm Template", decoys),
            sheet("Vm", [vm_record()]),
        ])

        rows, _ = app_module.load_vms_from_vinfo(path)

        self.assertEqual(["app-01"], [row["name"] for row in rows])
        self.assertEqual(4, float(rows[0]["cpus"]))

    def test_family_and_version_produce_os_names_used_by_existing_readiness_logic(self):
        cases = [
            ("Red Hat Enterprise Linux", "8", "Red Hat Enterprise Linux 8"),
            ("RHEL", "8", "Red Hat Enterprise Linux 8"),
            ("Windows", "2019", "Windows Server 2019"),
            ("Debian", "11", "Debian GNU/Linux 11"),
            ("SUSE Linux Enterprise Server", "12", "SUSE Linux Enterprise 12"),
            ("Oracle Linux", "Oracle Linux 8 (64-bit)", "Oracle Linux 8 (64-bit)"),
        ]
        for family, version, expected in cases:
            with self.subTest(family=family, version=version):
                rows, _ = self.load([vm_record(**{"Operating System": family, "OS Version": version})])
                self.assertEqual(expected, rows[0]["raw_os"])

    def test_generic_and_32_bit_os_evidence_is_not_lost_or_given_an_invented_release(self):
        cases = [
            ("Ubuntu", "Ubuntu Linux (64-bit)", "Ubuntu Linux (64-bit)"),
            ("Ubuntu", "", "Ubuntu"),
            ("", "", ""),
            ("Other", "Other (32-bit)", "Other (32-bit)"),
            ("Windows", "Windows Server 2008 (32-bit)", "Windows Server 2008 (32-bit)"),
        ]
        for family, version, expected in cases:
            with self.subTest(family=family, version=version):
                rows, _ = self.load([vm_record(**{"Operating System": family, "OS Version": version})])
                self.assertEqual(expected, rows[0]["raw_os"])

    def test_power_status_is_normalized_and_missing_status_stays_unknown(self):
        rows, _ = self.load([
            vm_record(Hostname="on", **{"Power Status": "Powered On"}),
            vm_record(Hostname="off", **{"Power Status": "Powered Off"}),
            vm_record(Hostname="missing", **{"Power Status": ""}),
        ])

        self.assertEqual(["On", "Off", "Unknown"], [row["power_state"] for row in rows])
        headers = [header for header in MATILDA_HEADERS if header != "Power Status"]
        rows, _ = self.load([vm_record()], headers)
        self.assertEqual("Unknown", rows[0]["power_state"])

    def test_complete_debian_description_does_not_repeat_the_family_alias(self):
        rows, _ = self.load([vm_record(**{
            "Operating System": "Debian", "OS Version": "Debian GNU/Linux 11 (64-bit)",
        })])
        self.assertEqual("Debian GNU/Linux 11 (64-bit)", rows[0]["raw_os"])

    def test_existing_generic_vm_table_keeps_its_cpu_mapping(self):
        generic = {"VM": "generic-01", "CPUs": 4, "Memory GB": 8,
                   "Storage GB": 100, "Logical Processors": 99}
        path = self.workbook([sheet("Vm", [generic], list(generic))])
        rows, source = app_module.load_vms_from_vinfo(path)
        self.assertEqual("generic-01", rows[0]["name"])
        self.assertEqual(4, float(rows[0]["cpus"]))
        self.assertNotIn("Matilda", source)

    def test_ubuntu_release_uses_the_same_family_as_rvtools(self):
        rows, _ = self.load([vm_record(**{"Operating System": "Ubuntu", "OS Version": "22.04"})])
        self.assertEqual("Ubuntu Linux 22.04", rows[0]["raw_os"])

    def test_suse_full_version_is_canonicalized_for_existing_readiness(self):
        rows, _ = self.load([vm_record(**{
            "Operating System": "SUSE Linux Enterprise Server",
            "OS Version": "SUSE Linux Enterprise Server 12 (64-bit)",
        })])
        self.assertEqual("SUSE Linux Enterprise 12 (64-bit)", rows[0]["raw_os"])

    def test_generic_vm_title_is_not_mistaken_for_a_matilda_header(self):
        path = self.workbook([{"name": "Vm", "rows": [
            ["Logical Processors", "Summary"],
            ["VM", "CPUs", "Memory GB", "Storage GB"],
            ["generic-01", 4, 8, 100],
        ]}])
        rows, source = app_module.load_vms_from_vinfo(path)
        self.assertEqual("generic-01", rows[0]["name"])
        self.assertEqual(4, float(rows[0]["cpus"]))
        self.assertNotIn("Matilda", source)

    def test_duplicate_hostnames_keep_both_rows_with_existing_name_provenance(self):
        rows, source = self.load([vm_record(), vm_record(**{"Logical Processors": 2})])

        self.assertEqual(["app-01", "app-01 [2]"], [row["name"] for row in rows])
        self.assertEqual(["app-01", "app-01"], [row["source_name"] for row in rows])
        self.assertEqual([1, 2], [row["duplicate_index"] for row in rows])
        summary = app_module.build_inventory_import_summary(rows, source)
        self.assertEqual(1, summary["duplicate_name_count"])
        self.assertEqual(1, summary["duplicate_row_count"])
        self.assertEqual(6, summary["total_vcpus"])

    def test_missing_required_matilda_columns_explain_which_field_is_missing(self):
        for missing in ("Hostname", "Logical Processors", "Memory(GB)", "Total Storage(GB)"):
            with self.subTest(missing=missing):
                headers = [header for header in MATILDA_HEADERS if header != missing]
                with self.assertRaises(ValueError) as caught:
                    self.load([vm_record()], headers)
                message = str(caught.exception).lower()
                self.assertIn("matilda", message)
                self.assertIn(missing.split("(")[0].lower(), message)

    def test_incomplete_matilda_table_does_not_fall_back_to_an_unrelated_complete_sheet(self):
        headers = [header for header in MATILDA_HEADERS if header != "Total Storage(GB)"]
        generic = {"VM": "wrong-scope", "CPUs": 20, "Memory": 8192, "Provisioned MiB": 102400}
        path = self.workbook([
            sheet("Vm", [vm_record()], headers),
            sheet("VMs", [generic], list(generic)),
        ])

        with self.assertRaises(ValueError) as caught:
            app_module.load_vms_from_vinfo(path)
        self.assertIn("total storage", str(caught.exception).lower())

    def test_zero_resource_dataset_uses_existing_sizing_validation(self):
        for field, diagnostic in (
            ("Logical Processors", "vCPU"),
            ("Memory(GB)", "RAM"),
            ("Total Storage(GB)", "storage"),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, f"No usable {diagnostic}"):
                    self.load([vm_record(**{field: 0})])

    def test_matilda_and_rvtools_have_equivalent_canonical_sizing_rows(self):
        matilda, _ = self.load([vm_record()])
        rvtools_path = self.workbook([{
            "name": "vInfo",
            "rows": [
                ["VM", "Powerstate", "OS according to the configuration file", "CPUs", "Memory", "Provisioned MiB"],
                ["app-01", "poweredOn", "Red Hat Enterprise Linux 8", 4, 8192, 102400],
            ],
        }], "rvtools.xlsx")

        rvtools, _ = app_module.load_vms_from_vinfo(rvtools_path)

        self.assertEqual(rvtools, matilda)

    def test_existing_inventory_upload_activates_matilda_and_persists_import_summary(self):
        path = self.workbook([sheet("Vm", [vm_record()])])
        with self.upload_client() as (client, catalog, _):
            response = self.upload(client, path)

            self.assertEqual(200, response.status_code)
            with client.session_transaction() as session:
                selected = session.get("selected_rvtools_file", "")
                summary = session.get("rvtools_import_summary", {})
                self.assertFalse(session.get("rvtools_rejected_info"))
            self.assertEqual(catalog, Path(selected).parent)
            self.assertTrue(Path(selected).is_file())
            self.assertEqual(1, summary["vm_count"])
            self.assertEqual(4, summary["total_vcpus"])
            self.assertEqual(8, summary["total_memory_gb"])
            self.assertEqual(100, summary["total_storage_gb"])
            self.assertIn("Matilda", summary["source"])
            rows, _ = app_module.load_vms_from_vinfo(selected)
            self.assertEqual("app-01", rows[0]["name"])

    def test_rejected_matilda_replacement_preserves_active_inventory_and_selections(self):
        headers = [header for header in MATILDA_HEADERS if header != "Total Storage(GB)"]
        path = self.workbook([sheet("Vm", [vm_record()], headers)])
        with self.upload_client() as (client, catalog, app_state):
            existing = catalog / "existing.csv"
            existing.write_text(
                "VM,Powerstate,CPUs,Memory,Provisioned MiB\n"
                "existing-01,poweredOn,2,4096,51200\n",
                encoding="utf-8",
            )
            state = app_module._default_app_state()
            state["selected_vm_names"] = ["existing-01"]
            state_path = app_state / "matilda_upload_test.json"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with client.session_transaction() as session:
                session["selected_rvtools_file"] = str(existing)
                session["rvtools_file_info"] = app_module.build_source_file_info(str(existing))

            with self.assertLogs(app_module.app.logger, level="ERROR"):
                response = self.upload(client, path)

            self.assertEqual(200, response.status_code)
            with client.session_transaction() as session:
                self.assertEqual(str(existing), session["selected_rvtools_file"])
            self.assertIn(b"Input not accepted for sizing", response.data)
            self.assertIn(b"Total Storage", response.data)
            self.assertTrue(existing.is_file())
            self.assertEqual(["existing-01"], json.loads(state_path.read_text())["selected_vm_names"])
            self.assertEqual([existing], list(catalog.iterdir()))

    def test_portable_package_roundtrip_retains_matilda_inventory_sizing_and_identity(self):
        rows, source = self.load([vm_record(), vm_record(**{"Logical Processors": 2})])
        package = portability.build_portable_package(
            {"name": "Matilda assessment", "app_state": {}},
            {
                "source_file_name": "Inventory Report.xlsx",
                "source_label": source.rsplit("::", 1)[-1],
                "import_summary": app_module.build_inventory_import_summary(rows, source),
                "rows": rows,
            },
            {"currency": "", "document": {}},
            exported_at="2026-09-15T12:00:00Z",
        )

        restored = portability.validate_portable_package(json.loads(portability.dumps_portable_package(package)))

        self.assertEqual(["app-01", "app-01 [2]"], [row["name"] for row in restored["inventory"]["rows"]])
        self.assertEqual([4, 2], [row["cpus"] for row in restored["inventory"]["rows"]])
        self.assertEqual([8192, 8192], [row["memory_mb"] for row in restored["inventory"]["rows"]])
        self.assertEqual([102400, 102400], [row["provisioned_mib"] for row in restored["inventory"]["rows"]])
        self.assertIn("Matilda", restored["inventory"]["source_label"])


if __name__ == "__main__":
    unittest.main()
