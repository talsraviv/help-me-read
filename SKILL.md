---
name: help-me-read
description: >-
  Add pasted YouTube videos (links, titles, or newsletter subject lines) and
  blog posts / articles (any non-YouTube url) to a personal HTML reader and
  deploy it. Every invocation ALSO scans Gmail for threads with the user's
  configured reading label (if one is set up) and adds the content those
  emails point to. Use whenever the user pastes one or more links or titles
  and wants to read, digest, summarize, or "add these to my reader / my site /
  help me read" — or asks to check/scan their labeled email, even with nothing
  pasted. Handles a single item or a batch of 10-15 at once. Builds one
  self-contained page per item with an analytical overview, plus player and
  transcript for videos or the extracted full article for blogs, then deploys
  to a fixed url.
---

# help me read

Turn pasted items — YouTube videos and blog posts — into entries in one
HTML reader, then deploy it. The archive is one file per item in
`data/items/`; the page is built from a template and pushed to a fixed surge
url.

### Locate the reader (run this first, from anywhere)

    REPO="$(cd ~/.claude/skills/help-me-read 2>/dev/null && pwd -P)" || REPO="$(cd ~/.claude/skills/help-me-read-youtube 2>/dev/null && pwd -P)" || REPO="$(git rev-parse --show-toplevel)"

(The second path is the skill's pre-rename name, still resolving on machines
that installed before the rename.)

If that resolves to nothing, the skill isn't installed on this machine —
bootstrap per `SETUP.md` (clone + symlink), then re-resolve. Invoke every
script by its `"$REPO/scripts/..."` path; scripts anchor their own data /
template / output paths to the repo.

Then pull the latest archive so this session builds on what other
sessions/machines already added (best-effort; offline just continues):

    bash "$REPO/scripts/sync.sh" pull

Concurrent adds from different machines are different files under
`data/items/`, so they merge natively — no conflicts to resolve.

### First run on this machine? (setup — one conversation, then never again)

If `config/surge-domain.txt` is missing or empty, this machine hasn't been
set up. Walk the user through setup BEFORE processing any items — this is the
one time the skill is conversational rather than autonomous:

1. **Check the environment.** Run `bash "$REPO/scripts/doctor.sh"` and report
   what's missing, with the install command for each gap. Required:
   `python3`, `yt-dlp` (`brew install yt-dlp` or `pipx install yt-dlp`),
   `node`/`npx` (`brew install node`). Optional (say what each unlocks, don't
   block on them): Pillow (`pip3 install Pillow` — video frame thumbnails),
   Chrome (headless render check before deploy), the Gmail MCP connector
   (email scanning). Wait for the user to install required pieces; re-run
   doctor.sh to confirm.
2. **Pick the site's address.** Propose 2-3 surge.sh subdomains like
   `<their-name>-reader.surge.sh` (free, first-come-first-served). If
   doctor.sh shows `surge_authenticated: false`, have the user run
   `npx surge login` in their own terminal — creating an account is just
   email + password, but never handle those credentials yourself. Write the
   chosen domain to `config/surge-domain.txt` (one line, nothing else).
3. **Offer the Gmail queue — optional but recommended**, especially for
   Substack newsletters and podcast emails: any email they label simply gets
   its content added to the reader on the next run. Tell the user to create a
   Gmail label named exactly `help-me-read` (in Gmail: scroll the left
   sidebar → "Create new label" → type `help-me-read`), then write
   `help-me-read` to `config/gmail-label.txt`. If they decline or the Gmail
   MCP isn't connected, skip — the reader works purely on pasted links, and
   this can be enabled any time later.
4. **Offer private git backup of the archive — optional.** Their reading
   library lives in `data/` (gitignored — it never mixes with this public
   code repo). If they want it backed up / synced across machines:
   `git -C "$REPO/data" init -b main` (create `data/` first if needed), then
   create a PRIVATE repo (`gh repo create <user>/help-me-read-data --private`)
   and add it as `origin` of `data/`. If not, skip — everything stays local
   and this too can be enabled later.

Then continue with the normal workflow below (or, if nothing was pasted,
finish by deploying the empty reader so the user sees their site live).

## Operating principle — fully autonomous

The user's only job is to paste urls/titles and invoke this skill. You do
everything else, in one pass, through to a live deploy, without asking for
confirmation:

- Don't pause to confirm choices. Resolve → fetch → overview → verify → add →
  commit → deploy in a single run.
- Never abort the batch because one item failed. Skip failures, keep going,
  and record them (step 6) so they show on the site.
- Be radically transparent: successes and failures go to the site's status
  banner AND the chat. The site is the primary surface.
- The invocation is complete only when the site is deployed and you've
  reported the url. If you attempted at least one item, always write status
  and deploy — even if every item failed.

## Workflow

### 1. Parse the paste into a list

Split the message into items: urls, bare titles, or newsletter subject lines.
YouTube urls → video items; any other url → blog post. A bare title/subject is
resolved by YouTube search — take `fetch_item`'s best match automatically, but
include the resolved title and channel in the report so the user can spot a
wrong pick. (Articles need a url; there is no blog search.)

An empty paste is a valid invocation — it means "just drain the Gmail queue"
(step 1b).

### 1b. Scan the Gmail reading label (every invocation, when configured)

Skip this step entirely if `config/gmail-label.txt` is missing or empty —
the user hasn't enabled the Gmail queue.

The user labels emails with their reading label in Gmail (then archives them
out of the inbox); every invocation also drains that queue. This needs the
Gmail MCP tools (`search_threads`, `get_thread`) — if they aren't available
in this session (headless run, connector not connected), say so in the
report and continue with pasted items only.

1. Find labeled threads — query by label NAME in kebab-case, not the
   `Label_…` id (the id form returns nothing), and include archived mail:

       search_threads  query: "label:$(cat "$REPO/config/gmail-label.txt") in:anywhere"

2. Filter out threads earlier runs already handled (deterministic, no
   tokens):

       python3 "$REPO/scripts/gmail_ledger.py" check <threadId> [<threadId>…]

   Only the ids under `"new"` continue; `"seen"` threads are done — never
   re-fetch or re-judge them.
3. Read the email bodies in ONE sub-agent, never in the main loop —
   newsletter bodies run 90–140KB each and would swamp the context that
   still has overviews to coordinate. A fast/cheap model is fine: this is
   link-picking, not writing. Dispatch a single sub-agent with
   the new threads' `{threadId, subject}` list and this task: *"For each
   thread, call the Gmail MCP `get_thread`. When the result is saved to a
   file (the usual case for newsletters), run*

       python3 "$REPO/scripts/extract_links.py" "<saved-file>"

   *which prints the candidate links in ranked buckets — `links` (named
   urls), `other_links` (social/podcast mirrors, demoted but never deleted),
   `wrapped_links` (tracking redirects) — plus the body's opening lines,
   with quoted-printable url mangling repaired. For a small inline result,
   read the links directly. Decide per thread what content the email points
   to (rubric below), then reply with compact JSON ONLY —
   `[{"threadId", "subject", "emailFile": "<saved-file path or null>",
   "bodyWords": <extract_links body_words>, "items": [{"url", "kind":
   "video|blog"}], "confidence": "high|low", "why": "<one line>"}]` — no
   prose, no body text. When no candidate is plausible, or two
   interpretations are genuinely defensible, do NOT guess: return that
   thread with `"escalate": true` and `why` instead of items."*

   Judgment rubric (include it verbatim in the sub-agent prompt):
   - A YouTube link → video item; an article/blog link → blog item.
   - Prefer the clean canonical url over tracking/redirect wrappers
     (`substack.com/redirect/…`, blogtrottr, utm-laden links) when both
     appear; `fetch_item` does follow redirects if a wrapper is all there is.
   - One email can yield multiple items — use judgment and take everything
     of standalone value. But a podcast newsletter whose essay is a
     companion writeup of the episode it links (show notes, an episode
     recap — e.g. Peter Yang's podcast emails) yields ONE item: the YouTube
     episode, not the essay. Only take both when the written piece stands
     alone from the episode. Ignore boilerplate links:
     unsubscribe, app badges, social icons, "listen on Spotify/Apple"
     mirrors of a YouTube link you already took.
   - If the email body IS the content (a newsletter essay with no separate
     canonical page), use its own web version ("View in browser" / the
     Substack post url). Still return that url even when the web version is
     paywalled (paid-subscriber posts) — step 2 rebuilds the item from the
     email body via `emailFile`, so the paywall costs nothing.

   Threads the sub-agent marks `escalate` (or `confidence: low` where its
   `why` doesn't convince you), judge yourself: call `get_thread` for just
   those, run `extract_links.py` on the saved result, and decide with full
   context. This should be the rare path — most emails are unambiguous —
   so the expensive read stays proportional to actual ambiguity.
4. Append these items to the step-1 list; from here they flow through the
   same pipeline as pasted items. Sanity-check each Gmail-scan item at
   fetch time, using output you already have: if `fetch_item`'s printed
   `title` shares nothing with the email's subject or snippet, suspect a
   wrong pick — re-judge that thread yourself (as in the escalate path)
   before any overview is written. Never ship an overview of a page that
   doesn't match its email.
5. At the end of the run (step 6), mark EVERY thread scanned this run —
   added, duplicate, or failed — so no thread is ever judged twice:

       python3 "$REPO/scripts/gmail_ledger.py" mark <threadId> --subject "<subject>" --result "<item ids added / already in archive / failed: why>"

   Failures still get marked: the retry queue (step 1c) owns re-attempts, so
   a thread is never judged twice even when its content failed. Ledger
   records are per-thread files in `data/gmail_seen/`, committed by
   `commit_archive.sh`, so machines merge natively.

### 1c. Drain the retry queue (every invocation)

Nothing is ever lost: items that couldn't be built before wait in
`data/retry/` and every invocation retries them.

    python3 "$REPO/scripts/retry_queue.py" list

Append each entry to the step-1 list (its record carries url, kind, title,
source, and — for upgrades — the archived `itemId`). They flow through the
same pipeline; the queue bookkeeping happens at fetch time (step 2):

- Retry succeeds → continue through overview/verify/add as normal, then
  `retry_queue.py remove "<url>" --result "added <id>"`. For an `upgrade`
  entry, run `add_item.py` with `--replace` so the full version supplants
  the partial one.
- Retry fails again → `retry_queue.py bump "<url>" --reason "<why>"` and
  move on. No status entry needed — queued items already surfaced in the
  banner the run they first failed; re-listing them every run is noise.
- Entry has `"stale": true` (too many attempts / too old) → stop waiting and
  **salvage**: build the best item the available material supports (partial
  captions, email body, page metadata + description — whatever exists), state
  plainly in its overview what's missing and why, add it, then
  `retry_queue.py remove "<url>" --result "salvaged as <id>"`. A found-again
  partial item beats a forgotten perfect one. Only when there is truly
  nothing to build from (no metadata, dead url) remove the entry and record
  it in `skipped` as permanently unavailable.

### 2. Fetch each item (deterministic, no tokens)

    python3 "$REPO/scripts/fetch_item.py" "<url-or-title>" --out "<scratch>/item-N.json"

Prints `{"ok": true, ...}` or an `error`. Videos get metadata + transcript;
blog urls get article extraction. Transient rate limits are retried inside
the script. A printed error never kills the batch — route the item by the
**failure policy** below and keep processing the rest.

**Failure policy — hold on to everything.** The user would rather see
partial content than lose it; a skip is the last resort, and even a skip is
queued for retry rather than dropped:

- **Likely to fix itself with time** (fresh upload with no captions yet or
  visibly truncated captions — compare the transcript's last timestamp to
  the video `duration`; transient page failure): queue it and move on:

      python3 "$REPO/scripts/retry_queue.py" add "<url>" --kind video|blog --reason "<why>" --title "<title>" --source "<source>" [--thread <gmailThreadId>]

  Every future invocation retries it automatically (step 1c) and salvages a
  best-effort item once it goes stale, so it surfaces in the reader either
  way.
- **Partial content in hand, full version might exist** (email preview stub
  of an unreadable page, paywalled post rebuilt from a truncated email):
  build the item from what you have NOW — the overview must say plainly
  what's missing ("built from the email preview; the full article adds …") —
  and also queue an upgrade so a later run can replace it with the full
  version:

      python3 "$REPO/scripts/retry_queue.py" add "<url>" --kind blog --reason "<what's missing>" --upgrade --item-id "<id>"

- **Genuinely short content** (a real short/reel whose captions cover the
  whole runtime): not a failure — just proportion: short transcript, short
  overview.
- **Permanently unavailable** (dead url, video removed): the only true skip
  — record it in `skipped` with the reason; nothing to queue.

Early dedup: if the printed `id` already exists as `data/items/<id>.json`
(`test -f`), the item is already in the reader — skip steps 3–5 for it and
record it as already-present, not a failure. This saves the whole overview
cost on re-pastes and re-labeled emails.

Paywall fallback (Gmail-scan blog items only): when the web fetch errors
with "could not extract readable article text", or its printed `words` is
under ~40% of the thread's `bodyWords` (a paywall stub of a paid-subscriber
post — Lenny's paid emails, some every.to pieces), rebuild the item from the
email itself:

    python3 "$REPO/scripts/fetch_item.py" "<canonical-url>" --html-file "<emailFile>" --title "<post title>" --out "<scratch>/item-N.json"

The item keeps the canonical url (same id, link, and dedup); only the
article text comes from the email. This is why the scan sub-agent reports
`emailFile` and `bodyWords` per thread.

### 3. Write the overview (the only AI step)

Generate the writer's brief — spec, output schema, and compact transcript in
one file:

    python3 "$REPO/scripts/brief_item.py" --item "<scratch>/item-N.json" --out "<scratch>/brief-N.md"

The brief is self-contained: whoever reads it needs no other context.

- **Single new item:** read the brief yourself, write the overview, and save
  the raw JSON object (exactly the shape the brief's schema section shows) to
  `<scratch>/overview-N.json`.
- **Batch (more than one):** dispatch one sub-agent per item, on your
  strongest writing model, in parallel. Each sub-agent's entire task: *"Read
  `<scratch>/brief-N.md` and follow it. Write the overview for this item.
  Save your output — one raw JSON object, no fences, exactly the schema in
  the brief — to `<scratch>/overview-N.json` with the Write tool. Reply with
  one line only: item id, sections, figures, quotes, moments (or what
  blocked you)."* Sub-agents must NOT return the JSON as their message.
- On a platform without sub-agents, write the overviews one at a time.

Then validate + merge each (deterministic, no tokens):

    python3 "$REPO/scripts/merge_overview.py" --item "<scratch>/item-N.json" --overview "<scratch>/overview-N.json"

On `"ok": false`, fix the listed schema errors in the overview file and rerun.

### 4. Verify figures and quotes (deterministic, no tokens)

    python3 "$REPO/scripts/check_figures.py" --item "<scratch>/item-N.json" --fix
    python3 "$REPO/scripts/check_quotes.py" --item "<scratch>/item-N.json"

`--fix` auto-repairs the mechanical figure issues (palette, font sizes);
remaining figure errors (viewBox too tall, missing caption, no_figure
contradiction) you fix in the item file directly. Treat figure warnings as a
prompt to re-judge the figure against the spec's Visuals rubric.

`check_quotes` enforces the grounding contract: every quote verbatim, every
timestamp where the words are said. On errors, correct the quote text /
`start` in the item file (against the brief's transcript) and rerun until
`"ok": true`. Do not paraphrase your way past it — find the words actually
said.

### 5. Fill demo frames (deterministic, no tokens — video items with moments)

    python3 "$REPO/scripts/extract_frames.py" --item "<scratch>/item-N.json"

Writes frame images under `data/assets/<id>/`. Warnings never fail the item —
mention them in the chat report only.

### 6. Add, record status, commit, deploy — always finish here

    python3 "$REPO/scripts/add_item.py" --item "<scratch>/item-N.json"

(`"added": false` = it was already in the archive. Pass `--replace` only
when completing an `upgrade` retry entry, so the full version supplants the
partial item under the same id.)

Write the run status — every attempted item, successes and failures, honest
plain-english reasons (the site renders this as its banner):

    python3 "$REPO/scripts/write_status.py" '{"added": [{"id": "...", "title": "...", "source": "..."}], "skipped": [{"input": "<exactly what the user pasted>", "resolved": "<title if known>", "reason": "<why>"}]}'

An item that went to the retry queue goes in `skipped` with a reason ending
"— queued for retry" so the banner shows it's parked, not lost. Partial adds
go in `added` like any other item.

Then commit and deploy — always, both are safe to run every time:

    bash "$REPO/scripts/commit_archive.sh" "reader: add <short titles>"
    bash "$REPO/scripts/deploy.sh"

`commit_archive.sh` commits `data/items/` + `data/assets/` +
`data/gmail_seen/` + `data/retry/` and pushes.
`deploy.sh` rebuilds, runs a smoke gate (a broken build never replaces the
live site — on failure, fix what its report names and rerun), deploys to the
fixed url, and opens it in the browser.

### 7. Report (chat mirror of the site)

State briefly: the live url (`https://` + the domain in
`config/surge-domain.txt`), what was
added (with resolved titles for searches), anything skipped and why, and
what the retry queue did this run (retried and landed / bumped and still
waiting / salvaged). For items that came from the Gmail scan, name the email
they came from (subject) and what content you picked out of it, so a wrong
judgment call is easy to spot.

## Notes

- yt-dlp is called with the android/web/tv clients to dodge the PO-token block
  that otherwise drops captions. Do not change that.
- Prerequisites (`yt-dlp`, `node`/`npx`, Pillow, surge auth) are checked by
  `scripts/doctor.sh` and installed during first-run setup — see `SETUP.md`.
  If a step fails on a missing one, report the one-time fix instead of
  silently failing.
- **Privacy contract:** everything user-specific — archive items, Gmail
  ledgers, retry queue, status, config values — lives ONLY under `data/` and
  `config/` (both gitignored by this public repo). Never write personal data
  anywhere else in the repo, and never commit it to the machinery repo.
- The reader is one page at one fixed url. Heavy content (transcripts, article
  text) lives in per-item payload files the page fetches on demand, so the
  index stays light forever. Share links are the same page with a `#/s/<id>`
  hash (focus, not security).
- Never `Read` item files after step 5 or archive files in `data/items/` —
  drive everything through the scripts. (Frame paths are small, but transcripts
  make item files big; the scripts print every fact you need.)
- The old "digest one video to my Desktop" behavior still lives in
  `scripts/fetch_transcript.py`.
