#!/usr/bin/env bash
# One-command installer for the Blueprint Wizard (macOS / Linux).
#
#   curl -fsSL https://raw.githubusercontent.com/timebeing92/brightspace-blueprint-runner/main/install_blueprint_wizard.sh | bash
#
# Clones the runner and its pipeline bundle as sibling folders (into
# ./blueprint-wizard/ by default, or the folder named as the first
# argument), then hands off to the wizard, which walks through everything
# else on first run. Re-running updates both repos with `git pull`.
#
# Requires git and access to the repos. If you'd rather not use git, use
# the release zip from GitHub Releases instead — same result.
set -euo pipefail

REPO_BASE="${BLUEPRINT_WIZARD_REPO_BASE:-https://github.com/timebeing92}"
TARGET_DIR="${1:-blueprint-wizard}"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required for this install path." >&2
  echo "Install git, or download the release zip from GitHub Releases instead." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

for repo in brightspace-blueprint-runner brightspace-blueprint-bundle; do
  if [ -d "$repo/.git" ]; then
    echo "== $repo already present — pulling latest"
    git -C "$repo" pull --ff-only
  else
    echo "== cloning $repo"
    git clone "$REPO_BASE/$repo" "$repo"
  fi
done

echo
echo "Installed into: $(pwd)"
echo "Starting the wizard (rerun any time with:"
echo "  bash $(pwd)/brightspace-blueprint-runner/blueprint_wizard.sh)"
echo

# When piped through `curl | bash`, stdin is the pipe — reattach the
# wizard's prompts to the terminal.
if [ -t 0 ]; then
  exec bash brightspace-blueprint-runner/blueprint_wizard.sh
elif (exec < /dev/tty) 2>/dev/null; then
  exec bash brightspace-blueprint-runner/blueprint_wizard.sh < /dev/tty
else
  echo "No terminal available for the interactive wizard. Run it with:"
  echo "  bash $(pwd)/brightspace-blueprint-runner/blueprint_wizard.sh"
fi
