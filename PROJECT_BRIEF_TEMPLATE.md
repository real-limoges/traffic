# Research Infrastructure Brief — [PROJECT NAME]
### Split Across Fable and Opus

## The actual goal

[One or two sentences: this is not "produce X report," it's "build a pipeline
where a clean, documented artifact is the deliverable, and X analysis is the
concrete exercise that proves the pipeline works."]

**Why split it this way:** [What specifically makes the data-acquisition
side unbounded/judgment-heavy for this project — a restrictive API, messy
real-world records, ambiguous edge cases? And what specifically makes the
analysis side bounded/well-specified — a named statistical method, a known
algorithm?]

## The research question

[What you actually want to know. State it as a real question with a real
possible negative answer, not a foregone conclusion.]

## Scope

[The specific slice of the problem — a region, a time range, a subset of the
domain — and why that scope is both tractable and meaningful, not arbitrary.]

## The artifact contract

```
repo/
  data/
    raw/                          # untouched downloads, never edited by hand
      [source]-<version/pull-id>/ # pin to a specific named release/pull
    processed/
      [intermediate].parquet      # cleaned, still "just data"
  analysis/
    *.py or *.qmd                 # Phase 2 lives here
  artifacts/                      # THE STABLE CONTRACT
    [primary_artifact].parquet    # << Phase 1 (Fable) stops here
                                   #   [describe the schema/fields]
    SCHEMA.md                     # << Phase 1 — every field, every cleaning
                                   #   decision, every known gap/caveat
    [analysis_results].json       # << Phase 2 (Opus)
    summary.json                  # << Phase 2 (Opus)
    figures/*.svg                 # << Phase 2 (Opus)
  paper/
    paper.qmd                     # renders from artifacts/ only
  site/                           # NOT built now — placeholder
  PROVENANCE.md                   # << Phase 1 — exact source version/pull
                                   #   details, fetch dates
  Makefile (or justfile)          # << Phase 1 — one command regenerates
                                   #   the primary artifact from data/raw/
```

## Phase 1 — Fable: [get the data into proper shape / describe the concrete goal]

### What "done" looks like
- `artifacts/[primary_artifact]`, fully populated, per the schema above
- `artifacts/SCHEMA.md` documenting every field, decision, and caveat —
  written so Opus (or you) never needs the acquisition code to trust the data
- `PROVENANCE.md` pinning the exact source version/pull used
- One command that regenerates the artifact from `data/raw/` deterministically
- [Any domain-specific known data-quality issues, stated explicitly, not
  left for Fable to discover and silently work around]
- Acquisition/cleaning logic structured as discrete, named, re-runnable
  stages, in a git repo from the first commit

### Non-goals for Phase 1
- No [the actual analysis method] — that's Opus's job in Phase 2
- No site
- [Any other domain-specific scope boundary — no simulation-from-scratch, no
  forecasting, no modeling adjacent systems not directly needed]

### Working notes for Fable specifically
- Framed at the upper end of difficulty on purpose — real judgment calls, not
  a checklist.
- Ask for verification via a fresh-context subagent at natural checkpoints
  rather than self-critique in the same context.
- Give it a running `NOTES.md` — one lesson per entry, including *why* each
  decision was made.
- Require it to audit every progress claim against real tool output before
  reporting, and to state plainly what's unverified.
- If working via Claude Code or the API: set effort to **high** by default,
  bump to **xhigh** if the work gets genuinely gnarly.
- Don't ask it to "explain its reasoning" or "show its thought process"
  verbatim — that phrasing can trip a classifier and silently fall back to
  Opus. Ask for conclusions plus evidence instead.

### Kickoff prompt for Fable

> [Write this as a holistic goal + constraints, not a step list — Fable's
> instruction-following is strong enough that over-specifying steps tends to
> constrain it into a worse path than it would find on its own. Cover: what
> the deliverable is, where the data comes from and any real access
> restrictions or known quality issues, the repo structure and artifact
> contract, the explicit instruction to stop before doing Phase 2's analysis,
> the git/modularity requirement, and the verification/NOTES.md/audit
> instructions above.]

## Phase 2 — Opus: [the bounded analysis]

Run this only after Phase 1's output has been spot-checked. Point Opus at
`artifacts/[primary_artifact]` and `artifacts/SCHEMA.md` — it shouldn't need
anything else.

### What "done" looks like
- [The specific analytical output — a fitted model, a solved optimization, a
  statistical test result — with a named, honest treatment of uncertainty,
  not a single point estimate presented as certain]
- A validation step: does the result sanity-check against something already
  known, before trusting anything built on top of it
- `summary.json` and `paper/paper.qmd` — honest about where the evidence is
  strong and where it isn't, aimed at a technically literate non-specialist

### Kickoff prompt for Opus

> [State the analytical question directly, point it at the artifact and
> schema, name the specific method to apply, require the validation step
> before trusting further results, and require honesty about confidence
> rather than rounding an ambiguous result up to a clean finding.]
