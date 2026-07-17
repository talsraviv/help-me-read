# Setup — running help-me-read on a new machine

This repo IS the `help-me-read` skill. Installing it means putting the repo
where your coding agent looks for skills — either cloned directly into the
skills directory, or cloned elsewhere and symlinked in. Your personal
library —
one JSON file per item under `data/items/`, plus frame images under
`data/assets/` — is gitignored by this repo and can optionally be its own
private git repo, kept in sync across machines through its own remote.

## New machine — one-time bootstrap

    # Simplest: clone straight into your agent's skills directory
    git clone https://github.com/<you>/help-me-read.git ~/.claude/skills/help-me-read

    # …or, to keep the code with your other projects (nicer for hacking on it),
    # clone anywhere and symlink it in — the skill works identically:
    #   git clone https://github.com/<you>/help-me-read.git ~/help-me-read
    #   ln -s ~/help-me-read ~/.claude/skills/help-me-read

    # Then invoke the skill in your agent — the first run walks you through the
    # rest (dependency check, picking your site's address, optional Gmail
    # label, optional private backup of your library)

If you already back your library up to a private data repo, also restore it:

    git clone https://github.com/<you>/help-me-read-data.git ~/help-me-read/data
    bash ~/help-me-read/scripts/sync.sh pull

From then on the skill pulls the latest archive at the start of every run and
pushes each add back up automatically. Concurrent adds from different
machines are different files under `data/items/`, so git merges them
natively; there is no custom merge driver to register.

## Prerequisites

`scripts/doctor.sh` checks all of these and the skill's first-run setup walks
you through them:

- `python3` (3.9+).
- `yt-dlp` — `brew install yt-dlp` (fetches transcripts).
- `node` / `npx` — for `surge` deploys and the deploy smoke gate's JS check.
- Surge auth — `npx surge login` once (token lands in `~/.netrc`). The reader
  deploys to the domain you chose in `config/surge-domain.txt`.
- Optional: Pillow (`python3 -m pip install Pillow`) — crops demo frames from
  YouTube storyboards; without it demo cards render without thumbnails.
- Optional: the Gmail MCP connector — for the label-an-email-to-queue-it flow.

## Two repos, one working copy (the privacy design)

- **This repo (public)** holds only machinery: scripts, template, tests, the
  skill itself. Nothing personal is ever committed here — `data/`, `config/`
  values, and `assets/fonts-local/` are gitignored.
- **`data/` (optional private repo)** holds your library: items, frame
  assets, Gmail ledgers, retry queue. If you initialize it as a git repo with
  a private remote, `commit_archive.sh` commits and pushes it after every
  add; if not, it simply stays local.
- Custom typeface: drop `book.ttf` and `bold.ttf` into `assets/fonts-local/`
  (gitignored) and builds use them instead of the bundled Gelasio. This is
  how a commercially licensed font stays usable without ever being committed.

## How sync is wired (for the curious / future agents)

- `scripts/sync.sh [pull|push|sync]` — best-effort; offline, no-remote, or
  no-data-repo just skips so the skill still works. `pull` = fast-forward the
  machinery repo (skipped if you have local edits), then fetch +
  `rebase --autostash` the data repo + flush unpushed commits; `push` = push
  the data repo, pull-and-retry if rejected. Self-anchoring.
- Concurrent adds touch different `data/items/<id>.json` files → native git
  merge. The only unresolvable case is both machines adding the SAME id with
  different content; the rebase then aborts leaving local state intact —
  either copy is fine, resolve by keeping one.
- SKILL.md pulls at the start of every run; `commit_archive.sh` pushes after
  each add.
- Machinery improvements you commit go to this repo, deliberately — the sync
  scripts never auto-commit code.

## Caveats

- Two sessions editing *code* (SKILL.md / scripts) on the same on-disk tree
  simultaneously can still interleave — normal git conflicts there.
- GitHub is the intended sync path, **not** a shared folder. If a clone lives
  inside Dropbox/iCloud, don't run git operations on the same synced folder from
  two machines at once — a file-sync service writing `.git` mid-operation can
  corrupt it. A plain clone on a non-synced path avoids this entirely.
