#!/usr/bin/env bash
# Keep the archive repo (data/) in sync with its private GitHub remote so it
# can be driven from multiple sessions, harnesses, and machines without
# clobbering the archive. The machinery repo (this checkout) is public and
# separate: `pull` also fast-forwards it, best effort, so machinery
# improvements propagate between machines — but machinery commits/pushes stay
# deliberate and are never made here.
#
# Usage:
#   sync.sh pull    # ff-pull the machinery repo; fetch + rebase data/ from
#                   # origin, then flush local data commits up
#   sync.sh push    # push data/ branch to origin (pull-and-retry if rejected)
#   sync.sh         # pull then push (a full sync)
#
# All network operations are BEST EFFORT: if there is no remote or the network
# is down, we warn and exit 0 so the skill still works offline. If data/ is not
# a git repo (archive backup not configured), everything is a quiet no-op.
# Self-anchoring (follows the skill symlink), so it runs from any working
# directory.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
DATA_DIR="$REPO_DIR/data"

log() { echo "sync: $*"; }

data_repo() { [ -e "$DATA_DIR/.git" ]; }

have_remote() { git -C "$DATA_DIR" remote get-url origin >/dev/null 2>&1; }

data_branch() { git -C "$DATA_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main; }

# The archive is one file per item (data/items/<id>.json), so concurrent adds
# from different machines touch different files and merge natively — no custom
# merge driver. The one case git can't auto-resolve (both machines added the
# SAME id with different content) aborts the rebase below and keeps local state.

# Best-effort fast-forward of the machinery repo. --ff-only never merges or
# rewrites; skipped entirely when the tree is dirty (work in progress wins).
pull_machinery() {
  git -C "$REPO_DIR" remote get-url origin >/dev/null 2>&1 || return 0
  if ! git -C "$REPO_DIR" diff --quiet 2>/dev/null || \
     ! git -C "$REPO_DIR" diff --cached --quiet 2>/dev/null; then
    log "machinery repo has local changes; skipping its pull"; return 0
  fi
  if git -C "$REPO_DIR" pull --ff-only --quiet origin 2>/dev/null; then
    log "machinery repo up to date"
  else
    log "machinery pull skipped (offline, diverged, or nothing to do)"
  fi
  return 0
}

do_pull() {
  pull_machinery
  if ! data_repo; then log "data/ is not a git repo (archive local-only); skipping pull"; return 0; fi
  if ! have_remote; then log "no 'origin' remote on data/; skipping pull"; return 0; fi
  local BRANCH; BRANCH="$(data_branch)"
  if ! git -C "$DATA_DIR" fetch --quiet origin "$BRANCH" 2>/dev/null; then
    log "fetch failed (offline?); continuing without pull"; return 0
  fi
  # Rebase our local commits on top of origin; --autostash protects
  # uncommitted work.
  if git -C "$DATA_DIR" rebase --autostash "origin/$BRANCH" >/dev/null 2>&1; then
    log "pulled origin/$BRANCH"
  else
    log "rebase hit a conflict git could not auto-resolve; aborting rebase, leaving local state untouched"
    git -C "$DATA_DIR" rebase --abort >/dev/null 2>&1
    return 0
  fi
  git -C "$DATA_DIR" gc --auto --quiet 2>/dev/null || true
  flush
}

# Push any local data commits that origin doesn't have yet.
flush() {
  data_repo || return 0
  have_remote || return 0
  local BRANCH ahead; BRANCH="$(data_branch)"
  ahead="$(git -C "$DATA_DIR" rev-list --count "origin/$BRANCH..$BRANCH" 2>/dev/null || echo 0)"
  if [ "${ahead:-0}" -gt 0 ]; then do_push; fi
}

do_push() {
  if ! data_repo; then log "data/ is not a git repo (archive local-only); skipping push"; return 0; fi
  if ! have_remote; then log "no 'origin' remote on data/; skipping push"; return 0; fi
  local BRANCH; BRANCH="$(data_branch)"
  if git -C "$DATA_DIR" push --quiet origin "$BRANCH" 2>/dev/null; then
    log "pushed $BRANCH -> origin"; return 0
  fi
  # Rejected (remote moved). Pull to integrate, then push once more.
  log "push rejected; pulling then retrying"
  do_pull
  if git -C "$DATA_DIR" push --quiet origin "$BRANCH" 2>/dev/null; then
    log "pushed $BRANCH -> origin"
  else
    log "push still failing (offline or auth?); local commits kept, will retry next sync"
  fi
}

case "${1:-sync}" in
  pull) do_pull ;;
  push) do_push ;;
  sync) do_pull; do_push ;;
  *) echo "usage: sync.sh [pull|push|sync]" >&2; exit 2 ;;
esac
exit 0
