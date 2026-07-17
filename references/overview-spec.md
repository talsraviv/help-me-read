# Overview spec

## Articles (blog posts)

The framework below is written for talks, but it governs articles identically —
read "talk" as "article", "speaker" as "author", "watching" as "reading". The
differences, all mechanical:

- Quotes are verbatim passages from the article text and carry **no `start`
  field** — omit it entirely (the reader offers "find in article" instead of
  play-from-here). Same for `qa` entries.
- `moments` is always `[]` — demo moments are a video concept.
- The final section becomes **"Is it worth reading the original?"** — the full
  article is right there on the page below the overview, so focus on what the
  *original page* adds that the extracted text can't carry: embedded charts and
  images, interactive elements, code rendering, comment threads, the author's
  voice at full length.
- Concept diagrams follow the same rules; article structure (frameworks,
  step-by-step processes, comparisons) is often genuinely diagrammable.

## Talks

Produce an overview of the transcript that lets the user get the full value of
the talk **without watching it**. This is not a teaser or an abstract — it's a
faithful, self-contained substitute. A reader should come away understanding the
argument, the reasoning behind it, the concrete details (examples, numbers,
names, demos), and the nuances — as if they had watched attentively and taken
excellent notes. This is the user's own framework for making sense of a talk.
Follow it section by section.

Two rules govern everything:

1. **Elaborate — don't just gesture at ideas.** For each idea, explain it in
   full: what the speaker claims, *why* (their reasoning and evidence), the
   concrete examples / numbers / anecdotes they use to support it, and what
   follows from it. Draw out the logic that connects one idea to the next; if
   the speaker builds an argument in steps, walk the steps. Prose should carry
   the meaning on its own — a reader who skipped every quote should still fully
   understand the talk. Err on the side of more explanation. The user wants
   depth; a thin summary that sends them back to the video has failed.

2. **Ground everything in exact quotes.** For every substantive claim you
   attribute to the talk, give the speaker's verbatim words so the user can
   trust that the overview reflects what was actually said. Quote generously and
   exactly, with timestamps. Quotes are evidence that sits *alongside* your
   explanation — not a replacement for it. Paraphrase to connect and to explain,
   quote to prove.

Aim for substantial depth. Length should track the content: a tight 15-minute
talk might yield a few rich paragraphs per section; a dense hour-long talk,
considerably more. Never pad, but never cut a real idea short. When in doubt,
include the idea and explain it.

Use these sections, in this order:

## Main contribution
What is the main contribution or innovation of this talk relative to the state
of the art or the prior consensus? Or what is not necessarily novel but better
articulated than ever before, or put into words in a special way? State the
thesis as if it were the talk's one-sentence pitch, then **explain it in depth
and in simple terms**: what it responds to, how the argument works, and why it
matters. Walk through the core reasoning — don't just name the idea. Exact quotes
to illustrate.

## Most special takeaways
The most special, unique, non-obvious, intriguing, or novel takeaways. For each
one, explain the idea *and why it is striking, counterintuitive, or important*,
then give the exact quote(s) that back it.

## Outline of main ideas
A guided tour of the talk's main ideas in the order they're developed, plus the
overall thesis. This is the backbone of the overview — be thorough. For each
idea: explain it fully (the point, the reasoning, the examples/data the speaker
uses), then substantial exact quotes. A reader should be able to follow the whole
argument from this section alone.

## Unexpected / incoherent points
Any points that are surprising, or that don't cohere neatly with the rest.
Explain what's odd or in tension and why. Exact quotes.

## Everything else worth keeping
Concrete details worth remembering that didn't fit above — examples, numbers,
tools, names, definitions, memorable asides. Practical value often lives here, so
keep it rather than dropping it. Explain briefly and quote where useful.

## Q&A (if present)
If there's a Q&A portion, organize each question and answer. Explain the
substance of each answer (don't merely restate the question), using exact quotes
for the key points.

## Is it worth watching in full?
Now that you've conveyed the substance, help the user decide whether the
*original* still adds something the overview can't — delivery, live demos,
visuals, code, energy, or detail you couldn't fully capture. Give the questions
they should ask themselves to decide if it's worth their time, and for each, brief
bullets on what the talk offers that speaks to it (exact quotes where natural, but
not critical here).

## Visuals

Two visual layers accompany the overview. Both obey one principle: **a visual
appears only when it genuinely beats prose, and skipping is an explicit
decision, never a silent omission.**

### Concept diagrams

**Default is no diagram.** A figure earns its place only by beating prose:
*would a smart reader grasp the shape of the idea in 5 seconds, in a way a
paragraph can't deliver?* Skipping is an explicit decision, never a silent
omission — see `no_figure` below. A bad diagram is worse than none.

The figure's job is concept communication, and it serves one reader purpose:
the user glances at the hero figure to get the talk's one non-obvious idea
and decide whether to dig in. A figure that is merely *about* the talk —
accurate, tidy, neutral — fails that reader even when every craft rule below
passes.

Build each figure by this procedure, in order:

1. **Write the claim first.** One sentence the figure must prove — the
   strongest, most load-bearing claim of the talk, not its table of contents.
   ("Databricks' AI revenue tripled the ARR gap in three quarters", not "the
   post compares Databricks and Snowflake".)

   A claim is something a smart reader could be surprised by or disagree
   with. "The system has five parts" is anatomy — background, not a claim;
   "the whole design exists to keep the full trace away from the main agent"
   is a claim. If your sentence could serve as a neutral section heading in
   anyone's talk on the topic, it is not *this* talk's claim — keep looking.

2. **Check the sentence for inherent geometry.** A claim is drawable when it
   contains one of these:
   - a **quantity or trend** — numbers that can become lengths, positions, curves
   - a **contrast** — before/after, then/now, sold vs delivered, X vs Y
   - an **asymmetry** — one big / many small, expensive vs cheap, always-on vs
     on-demand
   - a **containment** — inside vs outside a boundary that matters (a context
     window, a sandbox, the team)
   - a **loop** — a cycle whose *closure* is the insight
   - a **genuine 2×2** — both axes are real dimensions the talk argues about

   No geometry in the sentence → no figure. Write an honest `no_figure.reason`
   instead; that is a respectable outcome, decoration is not.

3. **Encode the claim in the geometry; words only name the pieces.** Position,
   size, and color do the arguing:
   - quantities → bars, curves, dot timelines **drawn to scale**. When the
     talk's core claim rests on numbers, the hero figure IS the chart of those
     numbers.
   - contrast → two panels with the same skeleton, so the one difference pops.
   - asymmetry → *draw* it: if the point is one expensive brain and many cheap
     workers, the brain is visibly big and the workers visibly small — never a
     symmetric org chart with the asymmetry written in a footnote beneath it.
   - containment → things sit physically inside or outside the boundary.
   - loop → the return arrow is the visual event; make it unmissable.

   **Never invent data.** Draw only quantities and relations the talk itself
   asserts, using the talk's own numbers where they exist. A qualitative claim
   ("more editing strips more voice") gets a qualitative encoding — two
   endpoints, an arrow, a shaded zone — never a plotted curve with invented
   values, which fakes a precision the speaker never offered.

4. **Gate with the covered-labels test.** Mentally blank every word in the
   figure. Does the drawing still assert something — one thing bigger, a curve
   flattening while a line keeps climbing, dots piling up at the wrong end, a
   box left outside the wall? If blanking the labels leaves interchangeable
   rectangles, that is **prose-in-boxes**: the reader must read every box to
   learn anything, so the figure adds nothing over the caption. Rework the
   encoding or skip.

   Two named failures to check against:
   - **The box tower**: 3–6 stacked or chained rounded rectangles joined by
     "then" arrows. A process whose only structure is "step follows step" is
     a list, and a list is prose, not a figure.
   - **The neutral map**: an accurate boxes-and-arrows rendering of the
     system that is true, complete, and insight-free — a reference drawing,
     not an argument. Test it through the caption: if the caption can only
     say what the parts *are*, not what the shape *proves*, the figure is
     neutral. Skip it, or find the claim hiding in the structure (the
     asymmetry, the thing kept outside, the loop that closes) and draw that
     instead.

**Words inside the figure:**
- A node label is ≤4 words on one line, plus at most one ≤6-word sublabel.
  Sentences live in the caption and the prose, never in the figure.
- At most one free-floating annotation of ≤6 words, and it must be the
  punchline ("too late", "context lives here"), not narration. If you feel the
  figure needs a sentence to be understood, the sentence belongs in the
  caption — or the encoding is wrong.
- Labels use the talk's own vocabulary verbatim where possible; ~12 labeled
  elements max.

**Coral is the point.** Exactly one coral element or coral group — the gap,
the anomaly, the new thing the talk introduces. Ink `#333333` is structure;
muted `#c3bdb1` is background and the old world. When everything is coral,
nothing is.

**The caption completes the figure:** one line that tells the reader what to
*see* and why it matters, with the key number if there is one. It never
re-lists the labels.

**Worked example.** Claim: "buyers were sold linear intelligence-per-dollar,
but per-token pricing delivers a logarithmic curve — and context bends it
back." Blank the labels and it still argues: a dashed line keeps climbing, the
coral curve flattens away from it, one arrow pushes the curve back up.

    <svg viewBox="0 0 720 400" xmlns="http://www.w3.org/2000/svg">
      <line x1="80" y1="340" x2="680" y2="340" stroke="#333333" stroke-width="2"/>
      <line x1="80" y1="340" x2="80" y2="40" stroke="#333333" stroke-width="2"/>
      <text x="380" y="380" font-size="18" fill="#333333" text-anchor="middle">money spent (tokens)</text>
      <text x="36" y="200" font-size="18" fill="#333333" text-anchor="middle" transform="rotate(-90 36 200)">intelligence</text>
      <line x1="80" y1="340" x2="640" y2="70" stroke="#c3bdb1" stroke-width="3" stroke-dasharray="9 7"/>
      <text x="636" y="56" font-size="18" fill="#333333" text-anchor="end">what was sold: linear</text>
      <path d="M80,340 C120,210 170,175 260,168 C360,160 500,158 640,155" fill="none" stroke="#cf5a3c" stroke-width="4"/>
      <text x="270" y="140" font-size="18" fill="#cf5a3c">what you actually buy: logarithmic</text>
      <line x1="600" y1="150" x2="600" y2="100" stroke="#cf5a3c" stroke-width="3" stroke-dasharray="6 5"/>
      <polygon points="600,90 593,104 607,104" fill="#cf5a3c"/>
      <text x="586" y="122" font-size="18" fill="#333333" text-anchor="end">context bends it back</text>
    </svg>

    caption: "Intelligence per dollar: buyers were sold a linear curve but pay
    per token and get a logarithmic one — context is the lever that bends it
    back."

If you make **no** figures, set on the overview object:

    "no_figure": { "reason": "<one plain-english line a reader would respect>" }

The reason is rendered on the page (e.g. "narrative interview; no structural
core to diagram") — write it for the reader, not for a log. Never emit
`no_figure` when a figure exists.

Figures are blocks inside sections:

    { "type": "figure", "svg": "<svg viewBox=\"0 0 720 400\">…</svg>",
      "caption": "one-line caption" }

Placement and count: the **hero** figure expresses the talk's core concept
and goes first — the first block of the first section. Multiple figures are
welcome when the piece genuinely argues more than one structural concept:
each additional figure must earn its place through the full recipe with its
own distinct claim, and it sits inline in the section that argues that
concept. More is never better for its own sake — two figures proving two
real claims beat four that share one, and a figure added for coverage or
rhythm is decoration, which the recipe exists to prevent.

Craft constraints (all machine-checked by `scripts/check_figures.py`):
- Inline SVG with `viewBox="0 0 720 H"` where **H ≤ 420**, and no fixed
  width/height attributes. The reader caps figures at 420 CSS px tall: a
  taller viewBox scales the whole figure — text included — down below
  readability. Design wide, not tall; a sequence runs horizontally.
- Every `font-size` ≥ 16 (phone readability at the 720-wide viewBox). At 16px
  a character averages ~8px of width: a 20-character label needs ~160px of
  room, so size boxes to their **longest** label and keep text inside the
  canvas.
- Colors only from the theme: paper `#f4f4f3`, ink `#333333`, coral `#cf5a3c`,
  muted `#c3bdb1`. Do not set `font-family` — the page's font is inherited.
- No scripts, external references, raster images, or `foreignObject` — the
  build strips them, silently amputating the figure.

### Demo moments

Scan the chapters and transcript for **actual on-screen demonstrations** —
product walkthroughs, live coding, screen shares. Cues: chapter titles
containing "demo", phrases like "let me show you", "switching to my screen",
"as you can see here". Do NOT emit moments for conceptual walkthroughs, slide
narration, or verbal examples; if in doubt, it is not a demo.

Emit as a top-level `moments` array on the item (empty array when none):

    "moments": [
      { "kind": "demo",
        "start": 1234, "end": 1410,
        "title": "Live demo: the agent rebuilds the dashboard from a prompt",
        "frames": [] }
    ]

`start`/`end` bound the on-screen segment in seconds (`end` = where the demo
talk ends). `title` says what the viewer will *see*. Leave `frames` empty — a
deterministic script fills it. `kind` is `"demo"` for now (`slide`, `code`,
`chart` are reserved).

When demos exist, the "Is it worth watching in full?" section should point at
them ("the demos below are the main thing this overview can't fully capture").
