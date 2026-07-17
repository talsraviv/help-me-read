#!/usr/bin/env bash
# Read-only environment report for the help-me-read skill's first-run setup.
# Prints one JSON object of facts; the skill narrates them and guides the user
# through whatever is missing. Never installs, writes, or prompts.
#
# Usage: doctor.sh
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"

have() { command -v "$1" >/dev/null 2>&1; }
ver() { "$@" 2>/dev/null | head -1 | tr -d '"' ; }
jbool() { if [ "$1" = 0 ]; then echo true; else echo false; fi; }

PY=false; PY_VER=""
if have python3; then PY=true; PY_VER="$(ver python3 --version)"; fi
YTDLP=false; YTDLP_VER=""
if have yt-dlp; then YTDLP=true; YTDLP_VER="$(ver yt-dlp --version)"; fi
NODE=false; NODE_VER=""
if have node; then NODE=true; NODE_VER="$(ver node --version)"; fi
NPX=false
if have npx; then NPX=true; fi

PILLOW=false
if [ "$PY" = true ] && python3 -c "import PIL" >/dev/null 2>&1; then PILLOW=true; fi

# Same candidate list as smoke_test.py — a headless render is optional polish.
CHROME=""
for c in \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "/Applications/Chromium.app/Contents/MacOS/Chromium" \
  /usr/bin/google-chrome /usr/bin/chromium /usr/bin/chromium-browser; do
  if [ -x "$c" ]; then CHROME="$c"; break; fi
done

SURGE_AUTH=false
if [ -f "$HOME/.netrc" ] && grep -q "surge" "$HOME/.netrc" 2>/dev/null; then SURGE_AUTH=true; fi

DOMAIN_SET=false; DOMAIN=""
if [ -s "$REPO_DIR/config/surge-domain.txt" ]; then
  DOMAIN_SET=true
  DOMAIN="$(tr -d '[:space:]' < "$REPO_DIR/config/surge-domain.txt")"
fi
LABEL_SET=false; LABEL=""
if [ -s "$REPO_DIR/config/gmail-label.txt" ]; then
  LABEL_SET=true
  LABEL="$(tr -d '[:space:]' < "$REPO_DIR/config/gmail-label.txt")"
fi

DATA_REPO=false; DATA_REMOTE=""
if [ -e "$REPO_DIR/data/.git" ]; then
  DATA_REPO=true
  DATA_REMOTE="$(git -C "$REPO_DIR/data" remote get-url origin 2>/dev/null || true)"
fi

FONTS_LOCAL=false
if [ -f "$REPO_DIR/assets/fonts-local/book.ttf" ] && [ -f "$REPO_DIR/assets/fonts-local/bold.ttf" ]; then
  FONTS_LOCAL=true
fi

cat <<EOF
{
  "required": {
    "python3": {"ok": $PY, "version": "$PY_VER"},
    "yt_dlp": {"ok": $YTDLP, "version": "$YTDLP_VER"},
    "node": {"ok": $NODE, "version": "$NODE_VER"},
    "npx": {"ok": $NPX}
  },
  "optional": {
    "pillow": {"ok": $PILLOW, "for": "video frame thumbnails"},
    "chrome": {"ok": $([ -n "$CHROME" ] && echo true || echo false), "path": "$CHROME", "for": "headless render check before deploy"},
    "fonts_local_override": {"ok": $FONTS_LOCAL, "for": "custom typeface (bundled Gelasio used otherwise)"}
  },
  "config": {
    "surge_domain": {"set": $DOMAIN_SET, "value": "$DOMAIN"},
    "surge_authenticated": $SURGE_AUTH,
    "gmail_label": {"set": $LABEL_SET, "value": "$LABEL"},
    "data_repo": {"initialized": $DATA_REPO, "remote": "$DATA_REMOTE"}
  }
}
EOF
