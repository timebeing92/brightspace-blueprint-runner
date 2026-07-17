#!/usr/bin/env bash
# Stable launcher for a managed Blueprint Wizard install (macOS / Linux).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIN_MAJOR=3
MIN_MINOR=11
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    --yes|-y)
      ASSUME_YES=1
      ;;
  esac
done

python_ok() {
  local py="$1"
  "$py" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

find_python() {
  local candidates=()
  if [ -n "${PYTHON:-}" ]; then
    candidates+=("$PYTHON")
  fi
  candidates+=(python3.13 python3.12 python3.11 python3)
  for py in "${candidates[@]}"; do
    if command -v "$py" >/dev/null 2>&1 && python_ok "$py"; then
      command -v "$py"
      return 0
    fi
  done
  return 1
}

ask_yes() {
  local prompt="$1"
  local default="${2:-n}"
  local reply
  if [ "$ASSUME_YES" -eq 1 ]; then
    return 0
  fi
  if [ "$default" = "y" ]; then
    read -r -p "$prompt [Y/n] " reply
    reply="${reply:-y}"
  else
    read -r -p "$prompt [y/N] " reply
    reply="${reply:-n}"
  fi
  case "$reply" in
    y|Y|yes|YES|Yes) return 0 ;;
    *) return 1 ;;
  esac
}

install_python() {
  echo "Python ${MIN_MAJOR}.${MIN_MINOR}+ was not found."
  case "$(uname -s)" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        if ask_yes "Install Python with Homebrew now?" "y"; then
          brew install python@3.12
          return 0
        fi
      else
        echo "Homebrew was not found. Install Python 3.11+ from https://www.python.org/downloads/ or install Homebrew first."
      fi
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        if ask_yes "Install Python, venv, and pip with apt now? This may ask for your sudo password." "y"; then
          sudo apt-get update
          sudo apt-get install -y python3 python3-venv python3-pip
          return 0
        fi
      elif command -v dnf >/dev/null 2>&1; then
        if ask_yes "Install Python with dnf now? This may ask for your sudo password." "y"; then
          sudo dnf install -y python3 python3-pip
          return 0
        fi
      elif command -v yum >/dev/null 2>&1; then
        if ask_yes "Install Python with yum now? This may ask for your sudo password." "y"; then
          sudo yum install -y python3 python3-pip
          return 0
        fi
      elif command -v pacman >/dev/null 2>&1; then
        if ask_yes "Install Python with pacman now? This may ask for your sudo password." "y"; then
          sudo pacman -S --needed python python-pip
          return 0
        fi
      else
        echo "No supported package manager was found. Install Python 3.11+ manually and rerun this command."
      fi
      ;;
    *)
      echo "Unsupported platform for automatic Python installation. Install Python 3.11+ manually and rerun this command."
      ;;
  esac
  return 1
}

if ! PY="$(find_python)"; then
  install_python || {
    echo "Cannot continue without Python ${MIN_MAJOR}.${MIN_MINOR}+." >&2
    exit 1
  }
  if ! PY="$(find_python)"; then
    echo "Python installation did not place a Python ${MIN_MAJOR}.${MIN_MINOR}+ command on PATH." >&2
    echo "Set PYTHON=/path/to/python3.11+ and rerun this command." >&2
    exit 1
  fi
fi

exec "$PY" "$HERE/launcher/stable_launcher.py" --install-root "$HERE" "$@"
