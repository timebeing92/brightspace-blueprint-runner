from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
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
