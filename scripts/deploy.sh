#!/usr/bin/env bash
set -euo pipefail
# Resolve the repo root from this script's own location (follows the skill
# symlink), so deploy works from any working directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR/.."
if [ ! -s config/surge-domain.txt ]; then
  echo "no surge domain configured — run the help-me-read skill once to complete setup (it writes config/surge-domain.txt)" >&2
  exit 1
fi
DOMAIN="$(tr -d '[:space:]' < config/surge-domain.txt)"
if [ -z "$DOMAIN" ]; then
  echo "config/surge-domain.txt is empty — run the help-me-read skill once to complete setup" >&2
  exit 1
fi
python3 "$SCRIPT_DIR/build.py"
# Smoke gate: a broken build must never replace the live site. Failures print
# a JSON report of what's wrong; fix and rerun.
python3 "$SCRIPT_DIR/smoke_test.py"
npx --yes surge ./site "$DOMAIN"
URL="https://$DOMAIN"
echo "deployed to $URL"
# Open the deployed site in the default browser (best-effort; harmless if headless).
( open "$URL" || xdg-open "$URL" ) >/dev/null 2>&1 || true
