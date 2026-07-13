#!/usr/bin/env bash
# Double-clickable launcher for the Blueprint Wizard (macOS).
# Finder opens this in Terminal; it then runs blueprint_wizard.sh from this folder.
cd "$(dirname "$0")"
exec bash ./blueprint_wizard.sh "$@"
