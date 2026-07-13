#!/usr/bin/env bash
# Double-clickable launcher for the Blueprint Wizard (macOS).
# Finder opens this in Terminal; it then runs blueprint_wizard.sh from this folder.
exec bash "$(dirname "$0")/blueprint_wizard.sh" "$@"
