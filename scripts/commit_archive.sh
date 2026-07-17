#!/usr/bin/env bash
set -euo pipefail
# Commit the archive (data/items/ + data/assets/ + data/gmail_seen/ +
# data/retry/) so every add keeps git history. The archive is its own git repo
# at data/ (separate from the public machinery repo) so personal content never
# mixes with the shared code. Self-anchoring (follows the skill symlink) and a
# no-op when nothing changed.
#
# Usage: commit_archive.sh "reader: add <titles>"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DATA_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)/data"
MSG="${1:-reader: update archive}"
mkdir -p "$DATA_DIR/items" "$DATA_DIR/assets" "$DATA_DIR/gmail_seen" "$DATA_DIR/retry"
if [ ! -e "$DATA_DIR/.git" ]; then
  echo "archive is local-only (no private data repo configured); skipping commit"
  exit 0
fi
git -C "$DATA_DIR" add items assets gmail_seen retry
if git -C "$DATA_DIR" diff --cached --quiet; then
  echo "archive unchanged; nothing to commit"
else
  git -C "$DATA_DIR" commit -q -m "$MSG"
  echo "committed archive: $MSG"
fi
# Push the new commit (and any other unpushed local commits) so every add is
# backed up and visible to other sessions/machines. Best effort: offline just
# defers the push to the next sync.
bash "$SCRIPT_DIR/sync.sh" push || true
