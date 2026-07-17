# help me read

A coding-agent skill that turns links you paste — YouTube videos, blog
posts, newsletter essays — into a beautiful personal reading site, deployed
to your own fixed URL. Works with any agent harness that supports skills.

Paste a link (or ten). The skill fetches the transcript or article, writes an
analytical overview with verified quotes and figures, adds it to your
archive, and deploys the updated site. For videos you get a player, chapter
moments with frame thumbnails, and the full transcript; for articles, the
extracted full text. Optionally, label an email in Gmail and the next run
picks it up automatically — great for Substack newsletters and podcast
emails.

![the reader](docs/screenshot.png)

## Quickstart

The easiest way: paste this to your coding agent:

> Set this up for me: https://github.com/talsraviv/help-me-read

Your agent will clone it, install the skill, and walk you through the couple
of things only you can do (about two minutes). Prefer to do it by hand?
Installing is just cloning into your agent's skills directory:

```bash
git clone https://github.com/talsraviv/help-me-read.git ~/.claude/skills/help-me-read
```

Then paste a YouTube link to your agent and say "help me read this".

Planning to customize the skill, or keep your own fork evolving? Clone it
wherever you keep projects and symlink it in instead — it works identically,
and the code lives where you like to edit:

```bash
git clone https://github.com/talsraviv/help-me-read.git ~/help-me-read
ln -s ~/help-me-read ~/.claude/skills/help-me-read
```

Either way, the first run detects a fresh install and walks you through
everything else: checking dependencies (`python3`, `yt-dlp`, `node`), picking
your site's address (a free `*.surge.sh` subdomain), and the optional extras.
After that, every invocation is fully autonomous — paste links, get a
deployed site.

### For coding agents

If you're an AI agent and your user asked you to set this up:

1. Clone this repo straight into the skills directory
   (`git clone https://github.com/talsraviv/help-me-read.git ~/.claude/skills/help-me-read`,
   adapting the path to your harness). If your user wants to customize the
   skill, clone it where they keep projects and symlink it in instead.
   Avoid Dropbox/iCloud-synced folders — file sync can corrupt `.git`.
2. Run `bash ~/help-me-read/scripts/doctor.sh` — it prints a JSON report of
   required and optional dependencies plus config state. Help your user
   install whatever is missing.
3. Follow the "First run on this machine?" section of `SKILL.md` — it is
   written for you and covers the rest of setup conversationally.
4. Two steps belong to the human, not you: running `npx surge login` (never
   handle their credentials) and creating the `help-me-read` label in their
   Gmail. Everything else you can do directly.
5. When setup completes, deploy the empty reader so your user immediately
   sees their site live, then invite them to paste their first link.

## How it works

The pipeline is deterministic scripts with exactly one AI step:

1. **Parse** the paste into items (YouTube URL → video, other URL → article,
   bare title → YouTube search). If a Gmail label is configured, also scan
   for newly labeled emails and extract the content they point to.
2. **Fetch** — `yt-dlp` pulls metadata + transcript; articles get readable
   text extraction. Failures are queued and retried on every future run;
   nothing is ever silently lost.
3. **Write the overview** — the one AI step. A generated writer's brief
   (spec + schema + transcript, see `references/overview-spec.md`) produces
   an analytical overview: sections, figures, grounded quotes, key moments.
4. **Verify** — scripts check every quote is verbatim and every timestamp is
   where the words are actually said. The model doesn't get to grade its own
   homework.
5. **Build + deploy** — one light `index.html` plus a lazy-loaded payload
   per item, so the page stays fast forever. A smoke test gates every
   deploy; a broken build never replaces your live site.

## Your library is yours

The public machinery and your personal content are strictly separated:

- **This repo** holds only the machinery — scripts, template, tests, the
  skill. It never contains personal data.
- **`data/`** (gitignored) holds your library: items, assets, ledgers. The
  setup flow can optionally make it a private git repo so your archive is
  backed up and synced across machines.
- **`config/`** values (your domain, your Gmail label) are gitignored, with
  committed `.example` templates.
- **Fonts**: the site ships with [Gelasio](https://fonts.google.com/specimen/Gelasio)
  (SIL OFL). Prefer your own typeface — including a commercially licensed
  one? Drop `book.ttf` and `bold.ttf` into `assets/fonts-local/` (gitignored)
  and builds use them automatically.

## Requirements

- A coding agent harness that supports skills (and MCP, for the optional
  Gmail queue)
- `python3`, `yt-dlp`, `node`/`npx` — checked by `scripts/doctor.sh`, guided
  by the first-run setup
- Optional: Pillow (frame thumbnails), Chrome (pre-deploy render check),
  Gmail MCP connector (the email queue)

See [SETUP.md](SETUP.md) for details, multi-machine sync, and the privacy
design.

## License

MIT — see [LICENSE](LICENSE). The bundled Gelasio fonts are licensed
separately under the SIL Open Font License (`assets/fonts/OFL.txt`).
