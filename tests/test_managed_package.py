from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import make_managed_install_bundle as managed  # noqa: E402


def test_initial_pointer_records_one_complete_release_pair() -> None:
    manifest = {
        "runner": {"commit": "1" * 40},
        "bundle": {"commit": "2" * 40},
    }

    pointer = managed.initial_pointer("2.8.0", manifest)

    assert pointer == {
        "schema": "coursecraft.wizard_install_pointer/1",
        "launcher_protocol": 1,
        "current_version": "2.8.0",
        "previous_version": "",
        "activated_at_utc": "1980-01-01T00:00:00Z",
        "runner_commit": "1" * 40,
        "bundle_commit": "2" * 40,
    }


def test_candidate_start_here_preserves_the_unreleased_boundary() -> None:
    assert "not a published release" in managed.START_HERE
    assert "outside version folders" in managed.START_HERE
    assert "old-version deletion remain disabled" in managed.START_HERE
