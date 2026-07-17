# Overview output schema

Return exactly one JSON object with these two top-level keys (no prose around
it, no markdown fences):

    {
      "overview": {
        "no_figure": { "reason": "why no diagram was made" },   // ONLY when there are zero figure blocks; omit otherwise
        "sections": [
          { "heading": "main contribution",
            "blocks": [
              {"type":"figure","svg":"<svg viewBox=\"0 0 720 400\">…</svg>","caption":"one-line caption"},
              {"type":"prose","text":"..."},
              {"type":"quote","text":"exact words from the transcript/article","start": 252}
            ] }
        ],
        "qa": [ {"question":"...","start": 248,
                 "answer":[ {"type":"prose","text":"..."} ]} ]
      },
      "moments": [ {"kind":"demo","start":1234,"end":1410,
                    "title":"Live demo: what you'll see","frames":[]} ]
    }

Field rules:

- Block `type` is `prose`, `quote`, or `figure` — nothing else.
- **Videos:** every quote's `start` is the transcript timestamp (seconds,
  integer) where those words are said — take it from the `[seconds]` markers
  in the brief's transcript. `qa[].start` is where the question is asked.
- **Articles (blogs):** quotes are verbatim passages from the article text and
  carry **no `start` field** (omit it entirely, same for `qa`), and `moments`
  is always `[]`.
- Quotes must be the source's exact words — they are machine-verified against
  the transcript/article after you return, and a quote that doesn't match
  verbatim (or carries a wrong timestamp) fails the item.
- `no_figure.reason` is required when there are zero figures, forbidden when
  figures exist. Figures are optional-by-default — see the Visuals section of
  the spec; every figure must be built by its four-step procedure.
- `moments` must be `[]` when there are no true on-screen demos. Leave each
  demo's `frames` as `[]` — a deterministic script fills it later.
- `qa` is optional — omit it (or use `[]`) when the source has no Q&A portion.
