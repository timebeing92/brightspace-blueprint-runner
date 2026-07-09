# Brightspace Blueprint Runner

This is a small one-terminal runner for the adjacent
`brightspace-blueprint-bundle` project.

The runner does not replace the bundle pipeline. It checks the local machine,
prepares the bundle's `.venv`, installs Python dependencies when needed, checks
optional render tools, prompts for an export file, and then calls the bundle's
own `scripts/build_blueprint_bundle.py`.

## Quickstart

From this folder:

```bash
bash blueprint_wizard.sh
```

The wizard will:

1. Check for Python 3.11 or newer.
2. Offer to install Python with the system package manager if it is missing.
3. Create or reuse the bundle-local `.venv`.
4. Install or refresh Python packages from the bundle's `requirements.txt`.
5. Prompt for the Brightspace export ZIP/folder path. You can drag the export
   into Terminal and press Return.
6. Ask for an optional output label.
7. Ask which pipeline options to use.
8. Run the blueprint pipeline and print the output folder.

Default bundle location:

```text
../brightspace-blueprint-bundle
```

Use a different bundle folder:

```bash
bash blueprint_wizard.sh --bundle-dir /path/to/brightspace-blueprint-bundle
```

## Doctor Mode

Check the machine without running an export:

```bash
bash blueprint_wizard.sh --doctor
```

Check and offer to fix missing bundle dependencies:

```bash
bash blueprint_wizard.sh --doctor --fix
```

## Notes

- Python package installs happen inside the bundle's `.venv`.
- System tools are installed only after an explicit prompt.
- LibreOffice/`soffice` and Poppler are only required for DOCX visual render QA.
- This runner is intended for macOS/Linux shell use. Windows users can still run
  the bundle's `bootstrap.ps1` and direct Python command from the bundle README.
