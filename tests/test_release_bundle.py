from __future__ import annotations

import importlib.util
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
    def test_deterministic_zip_preserves_executable_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "blueprint-wizard-v2.5"
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
                    "blueprint-wizard-v2.5/Blueprint Wizard.command"
                )
                self.assertEqual((info.external_attr >> 16) & 0o777, 0o755)

    def test_schema_receipt_uses_bundle_contract_ids(self) -> None:
        bundle = ROOT.parent / "brightspace-blueprint-bundle"
        rows = release.schema_receipt(bundle)
        self.assertEqual(
            [row["schema"] for row in rows],
            [
                "coursecraft.blueprint/4",
                "coursecraft.rubrics/1",
                "coursecraft.progress/1",
            ],
        )


if __name__ == "__main__":
    unittest.main()
