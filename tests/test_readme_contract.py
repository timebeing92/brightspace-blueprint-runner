from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
INSTALL_GUIDE = ROOT / "INSTALL_AND_TROUBLESHOOT.md"
WIZARD_ART = ROOT / "docs" / "assets" / "blueprint-wizard-terminal.svg"


def test_readme_keeps_the_user_facing_blueprint_wizard_boundary() -> None:
    text = README.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert 'src="docs/assets/blueprint-wizard-terminal.svg"' in text
    assert "you could turn off Wi-Fi or work from a cave" in normalized
    assert "There is no AI involved whatsoever" in normalized
    assert "The Wizard reads and reports. It does not:" in text
    assert "upstream living library and development lab" in normalized
    assert "do not need to access, install, or operate the Workbench" in normalized
    assert "open a GitHub issue" in normalized
    assert "Do not post course exports" in normalized


def test_readme_prominently_links_the_blueprint_install_guide() -> None:
    text = README.read_text(encoding="utf-8")

    assert "[!IMPORTANT]" in text
    assert "blueprint-wizard-managed-vX.Y.Z.zip" in text
    assert "Code > Download ZIP" in text
    assert "System Settings > Privacy & Security" in text
    assert "click **Open**,\n> then **Open Anyway**" in text
    assert "(INSTALL_AND_TROUBLESHOOT.md)" in text
    assert text.index("[!IMPORTANT]") < text.index("## What it produces")


def test_blueprint_install_guide_is_product_specific_and_complete() -> None:
    text = INSTALL_GUIDE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "Install, update, and troubleshoot Blueprint Wizard" in text
    assert "blueprint-wizard-managed-vX.Y.Z.zip" in text
    assert "Blueprint Wizard.command" in text
    assert "Blueprint Bundle engine" in normalized
    assert "System Settings > Privacy & Security" in text
    assert "click **Open**, then **Open Anyway**" in normalized
    assert "blueprint_wizard_launcher.sh --health" in text
    assert "blueprint_wizard_launcher.sh --update" in text
    assert "blueprint_wizard_launcher.sh --rollback" in text
    assert "user-data/logs/" in text
    assert "course exports" in text


def test_readme_wizard_art_is_valid_accessible_svg() -> None:
    root = ET.parse(WIZARD_ART).getroot()
    namespace = {"svg": "http://www.w3.org/2000/svg"}

    title = root.find("svg:title", namespace)
    description = root.find("svg:desc", namespace)

    assert title is not None
    assert title.text == "Blueprint Wizard terminal splash"
    assert description is not None
    assert "color pixel-art wizard" in " ".join(description.itertext()).lower()
    assert root.attrib["role"] == "img"
    assert root.attrib["aria-labelledby"] == "wizard-title wizard-desc"
