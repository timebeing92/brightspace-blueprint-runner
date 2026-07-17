from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import make_managed_review_kit as review  # noqa: E402


def test_review_kit_name_cannot_be_confused_with_a_release() -> None:
    name = review.kit_name("1234567890abcdef")

    assert name == "UNRELEASED-blueprint-wizard-stable-launcher-review-1234567"
    assert "v2.7.0" not in name


def test_reviewer_readme_discloses_status_identity_and_test_boundary() -> None:
    text = review.review_readme(
        version="2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
        candidate_sha256="a" * 64,
    )

    assert "UNRELEASED TEST BUILD" in text
    assert "unsigned on both macOS and Windows" in text
    assert "has not been notarized" in text
    assert review.APP_FOLDER in text
    assert "future A-to-B network update" in text
    assert "1" * 40 in text
    assert "2" * 40 in text
    assert "a" * 64 in text


def test_install_tree_manifest_is_sorted_and_hashed(tmp_path: Path) -> None:
    app = tmp_path / review.APP_FOLDER
    app.mkdir()
    (app / "z.txt").write_text("last\n", encoding="utf-8")
    (app / "a.txt").write_text("first\n", encoding="utf-8")

    manifest = review.install_tree_manifest(app)

    assert manifest["schema"] == "coursecraft.wizard_review_install_tree/1"
    assert [row["path"] for row in manifest["files"]] == ["a.txt", "z.txt"]
    assert all(len(row["sha256"]) == 64 for row in manifest["files"])
