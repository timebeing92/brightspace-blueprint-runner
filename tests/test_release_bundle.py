from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "make_release_bundle.py"
SPEC = importlib.util.spec_from_file_location("make_release_bundle", MODULE_PATH)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class RunnerReleaseBundleTests(unittest.TestCase):
    def test_start_here_explains_the_safe_update_boundary(self) -> None:
        self.assertIn("--check-for-updates", release.START_HERE)
        self.assertIn("--no-update-check", release.START_HERE)
        self.assertIn("never replaces files", release.START_HERE)
        self.assertIn("--no-syllabus-fetch", release.START_HERE)
        self.assertIn("Package-local course text remains primary", release.START_HERE)

    def test_remote_normalization_removes_credentials(self) -> None:
        self.assertEqual(
            release.normalized_remote("https://token@github.com/example/repo.git"),
            "https://github.com/example/repo.git",
        )

    def test_deterministic_zip_preserves_executable_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "blueprint-wizard-v2.5.1"
            source.mkdir()
            launcher = source / "Blueprint Wizard.command"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            launcher.chmod(0o755)
            first = root / "first.zip"
            second = root / "second.zip"
            release.deterministic_zip(source, first)
            release.deterministic_zip(source, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                info = archive.getinfo(
                    "blueprint-wizard-v2.5.1/Blueprint Wizard.command"
                )
                self.assertEqual((info.external_attr >> 16) & 0o777, 0o755)

    def test_schema_receipt_uses_bundle_contract_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            schemas = bundle / "schemas"
            schemas.mkdir()
            ids = [
                "coursecraft.activities/1",
                "coursecraft.blueprint/4",
                "coursecraft.run/1",
                "coursecraft.rubrics/1",
                "coursecraft.structure/1",
                "coursecraft.progress/1",
            ]
            names = [
                "activities_schema.json",
                "blueprint_schema.json",
                "run_identity_schema.json",
                "rubrics_schema.json",
                "structure_schema.json",
                "progress_events_schema.json",
            ]
            for name, schema_id in zip(names, ids, strict=True):
                (schemas / name).write_text(
                    json.dumps({"$id": schema_id}), encoding="utf-8"
                )
            rows = release.schema_receipt(bundle)
            self.assertEqual([row["schema"] for row in rows], ids)

    def test_runtime_receipt_hashes_the_shipped_structure_extractor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            scripts = bundle / "scripts"
            scripts.mkdir()
            (scripts / "build_blueprint_bundle.py").write_text(
                "# pipeline entry point\n", encoding="utf-8"
            )
            (scripts / "reconstruct_course_structure.py").write_text(
                "# nested-inline-heading regression protected\n", encoding="utf-8"
            )

            rows = release.runtime_receipt(bundle)

            self.assertEqual(
                [row["path"] for row in rows],
                [
                    "brightspace-blueprint-bundle/scripts/build_blueprint_bundle.py",
                    "brightspace-blueprint-bundle/scripts/reconstruct_course_structure.py",
                ],
            )
            self.assertTrue(all(len(row["sha256"]) == 64 for row in rows))

    def test_release_manifest_records_the_bundle_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            (bundle / "VERSION").write_text("1.3.0\n", encoding="utf-8")
            schemas = bundle / "schemas"
            scripts = bundle / "scripts"
            schemas.mkdir()
            scripts.mkdir()
            schema_rows = (
                ("activities_schema.json", "coursecraft.activities/1"),
                ("blueprint_schema.json", "coursecraft.blueprint/4"),
                ("run_identity_schema.json", "coursecraft.run/1"),
                ("rubrics_schema.json", "coursecraft.rubrics/1"),
                ("structure_schema.json", "coursecraft.structure/1"),
                ("progress_events_schema.json", "coursecraft.progress/1"),
            )
            for name, schema_id in schema_rows:
                (schemas / name).write_text(
                    json.dumps({"$id": schema_id}), encoding="utf-8"
                )
            (scripts / "build_blueprint_bundle.py").write_text(
                "--no-syllabus-fetch\nlinked_syllabus_fetch_requested\n"
                "content retained as primary\nclassify_delivery\n"
                '"delivery": delivery\n',
                encoding="utf-8",
            )
            (scripts / "reconstruct_course_structure.py").write_text(
                "collect_syllabus_supplements\nsupplemental_linked_syllabus\n"
                "DEFAULT_SYLLABUS_HOSTS\npackage_html_link\n",
                encoding="utf-8",
            )
            (schemas / "progress_events_schema.json").write_text(
                '{"delivery":{"usable":true,"empty":false,'
                '"core_failures":[]}}\n',
                encoding="utf-8",
            )

            manifest = release.release_manifest(
                version="2.8.0",
                runner_ref="r" * 40,
                runner_commit="r" * 40,
                bundle_ref="b" * 40,
                bundle_commit="b" * 40,
                bundle_remote="https://github.com/example/bundle.git",
                bundle_root=bundle,
            )

            self.assertEqual(manifest["bundle"]["version"], "1.3.0")

    def test_release_capability_requires_the_linked_syllabus_procedure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            scripts = bundle / "scripts"
            scripts.mkdir()
            (scripts / "build_blueprint_bundle.py").write_text(
                "--no-syllabus-fetch\nlinked_syllabus_fetch_requested\n"
                "package-local content retained as primary\nclassify_delivery\n"
                '"delivery": delivery\n',
                encoding="utf-8",
            )
            (scripts / "reconstruct_course_structure.py").write_text(
                "collect_syllabus_supplements\nsupplemental_linked_syllabus\n"
                "DEFAULT_SYLLABUS_HOSTS\npackage_html_link\n",
                encoding="utf-8",
            )
            schemas = bundle / "schemas"
            schemas.mkdir()
            (schemas / "progress_events_schema.json").write_text(
                '{"delivery":{"usable":true,"empty":false,'
                '"core_failures":[]}}\n',
                encoding="utf-8",
            )

            capabilities = release.bundle_capabilities(bundle)

            self.assertEqual(
                capabilities["linked_syllabus_supplement"]["network_boundary"],
                "allowlisted_best_effort_nonfatal",
            )
            self.assertEqual(
                capabilities["linked_syllabus_supplement"]["discovery_shapes"],
                ["manifest_item_link", "package_html_link"],
            )
            self.assertEqual(
                capabilities["delivery_usability"]["consumer_rule"],
                "do_not_present_outputs_when_usable_is_false",
            )
            (scripts / "reconstruct_course_structure.py").write_text(
                "# missing capability markers\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "lacks required release markers"):
                release.bundle_capabilities(bundle)


if __name__ == "__main__":
    unittest.main()
