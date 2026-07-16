#!/usr/bin/env bash
# One-command installer for the Blueprint Wizard (macOS / Linux).
#
#   curl -fsSL https://raw.githubusercontent.com/timebeing92/brightspace-blueprint-runner/main/install_blueprint_wizard.sh | bash
#
# Clones the runner and its pipeline bundle as sibling folders (into
# ./blueprint-wizard/ by default, or the folder named as the first
# argument), then checks out the verified pair recorded in
# installer-compatibility.lock. Re-running fetches and installs the current
# recorded pair instead of combining two independent moving branch heads.
#
# Requires git and access to the repos. If you'd rather not use git, use
# the release zip from GitHub Releases instead — same result.
set -euo pipefail

REPO_BASE="${BLUEPRINT_WIZARD_REPO_BASE:-https://github.com/timebeing92}"
TARGET_DIR="${1:-blueprint-wizard}"
LOCK_FILE="installer-compatibility.lock"
INSTALLER_REF="refs/blueprint-wizard-installer/main"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required for this install path." >&2
  echo "Install git, or download the release zip from GitHub Releases instead." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

ensure_repo() {
  local repo="$1"
  local url="$2"
  if [ -d "$repo/.git" ]; then
    if [ -n "$(git -C "$repo" status --porcelain)" ]; then
      echo "$repo has local changes; refusing to replace its checkout." >&2
      echo "Commit, stash, or move those changes, then rerun the installer." >&2
      exit 1
    fi
    echo "== $repo already present — fetching verified release metadata"
  else
    echo "== cloning $repo"
    git clone --no-checkout "$url" "$repo"
  fi
}

lock_value() {
  local key="$1"
  printf '%s\n' "$LOCK_TEXT" |
    awk -F= -v wanted="$key" '$1 == wanted { print substr($0, index($0, "=") + 1); exit }'
}

require_lock_value() {
  local key="$1"
  local value
  value="$(lock_value "$key")"
  if [ -z "$value" ]; then
    echo "Installer compatibility record is missing $key." >&2
    exit 1
  fi
  printf '%s' "$value"
}

install_pinned_ref() {
  local repo="$1"
  local url="$2"
  local ref="$3"
  local expected_commit="$4"
  local fetched_ref="refs/blueprint-wizard-installer/${repo}"
  local resolved

  case "$ref" in
    v[0-9]*)
      ;;
    *)
      echo "Refusing non-release ref for $repo: $ref" >&2
      exit 1
      ;;
  esac
  if ! [[ "$expected_commit" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Invalid recorded commit for $repo: $expected_commit" >&2
    exit 1
  fi

  git -C "$repo" fetch --quiet --force "$url" \
    "refs/tags/$ref:$fetched_ref"
  resolved="$(git -C "$repo" rev-parse --verify "$fetched_ref^{commit}")"
  if [ "$resolved" != "$expected_commit" ]; then
    echo "Release identity mismatch for $repo $ref." >&2
    echo "Expected $expected_commit but fetched $resolved; no checkout changed." >&2
    exit 1
  fi
  git -C "$repo" checkout --quiet --detach "$expected_commit"
  echo "   installed $ref ($expected_commit)"
}

RUNNER_REPO="brightspace-blueprint-runner"
BUNDLE_REPO="brightspace-blueprint-bundle"
RUNNER_URL="$REPO_BASE/$RUNNER_REPO.git"
BUNDLE_URL="$REPO_BASE/$BUNDLE_REPO.git"

ensure_repo "$RUNNER_REPO" "$RUNNER_URL"

# Fetch only the official main branch into a private ref. This reads the
# generated compatibility record without moving the user's local branches.
git -C "$RUNNER_REPO" fetch --quiet --force "$RUNNER_URL" \
  "+refs/heads/main:$INSTALLER_REF"
LOCK_TEXT="$(git -C "$RUNNER_REPO" show "$INSTALLER_REF:$LOCK_FILE")"

LOCK_SCHEMA="$(require_lock_value schema)"
RUNNER_REF="$(require_lock_value runner_ref)"
RUNNER_COMMIT="$(require_lock_value runner_commit)"
BUNDLE_REF="$(require_lock_value bundle_ref)"
BUNDLE_COMMIT="$(require_lock_value bundle_commit)"

if [ "$LOCK_SCHEMA" != "coursecraft.runner_compatibility/1" ]; then
  echo "Unsupported installer compatibility schema: $LOCK_SCHEMA" >&2
  exit 1
fi

ensure_repo "$BUNDLE_REPO" "$BUNDLE_URL"
install_pinned_ref "$RUNNER_REPO" "$RUNNER_URL" "$RUNNER_REF" "$RUNNER_COMMIT"
install_pinned_ref "$BUNDLE_REPO" "$BUNDLE_URL" "$BUNDLE_REF" "$BUNDLE_COMMIT"

{
  printf 'schema=%s\n' "$LOCK_SCHEMA"
  printf 'installed_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'runner_ref=%s\n' "$RUNNER_REF"
  printf 'runner_commit=%s\n' "$RUNNER_COMMIT"
  printf 'bundle_ref=%s\n' "$BUNDLE_REF"
  printf 'bundle_commit=%s\n' "$BUNDLE_COMMIT"
} > INSTALL_RECEIPT.txt

echo
echo "Installed into: $(pwd)"
echo "Verified pair: runner $RUNNER_REF + bundle $BUNDLE_REF"
echo "Receipt: $(pwd)/INSTALL_RECEIPT.txt"
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
