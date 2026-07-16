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
                "coursecraft.blueprint/4",
                "coursecraft.rubrics/1",
                "coursecraft.progress/1",
            ]
            names = [
                "blueprint_schema.json",
                "rubrics_schema.json",
                "progress_events_schema.json",
            ]
            for name, schema_id in zip(names, ids, strict=True):
                (schemas / name).write_text(
                    json.dumps({"$id": schema_id}), encoding="utf-8"
                )
            rows = release.schema_receipt(bundle)
            self.assertEqual([row["schema"] for row in rows], ids)


if __name__ == "__main__":
    unittest.main()
