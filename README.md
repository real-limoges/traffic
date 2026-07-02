# Research Pipeline Template

> **This repo is an instantiated project (Bay Area Braess's paradox), not a
> blank template.** If you're here to finish the data pull, go straight to
> [`NEXT_STEPS.md`](NEXT_STEPS.md). The rest of this file documents the
> template pattern the project was built from.

A reusable scaffold for "Fable does the unbounded data engineering, Opus does
the bounded analysis" projects. Two live instances of this pattern already
exist — the wildfire self-organized-criticality project and the Bay Area
Braess's-paradox project — built independently, by hand, before this template
existed. This is the extracted version, so the next project doesn't require
re-deriving the pattern in conversation.

## How to use this

1. Copy this directory to a new repo for the new project.
2. Copy `PROJECT_BRIEF_TEMPLATE.md` to `PROJECT_BRIEF.md` and fill in the
   bracketed placeholders. This document becomes both your working brief and,
   largely verbatim, what you paste to Fable and then to Opus.
3. Work through `CHECKLIST.md` before handing anything to Fable. Every item
   on it exists because skipping it caused a real problem in one of the first
   two projects.
4. `git init` from the very first commit — before any code, not after.

## The core convention

- `data/raw/` — untouched downloads, never edited by hand, pinned to a
  specific named version/release/pull date in `PROVENANCE.md`
- `data/processed/` — intermediate cleaned data, still "just data"
- `artifacts/` — **the stable contract.** The only thing anything downstream
  (a paper, a future site, a different model, you in a year) is allowed to
  depend on. Must include `SCHEMA.md`.
- `analysis/` — the actual modeling code, usually Phase 2 / Opus's territory
- `paper/` — renders from `artifacts/` alone; nothing computed inline
- `site/` — placeholder directory; not built until you explicitly decide to
  build it
- One command (`make all`, or equivalent) regenerates everything in
  `artifacts/` from `data/raw/`, deterministically
- Cleaning/calibration logic lives in discrete, named, individually
  re-runnable functions — never one monolithic script. Every decision
  documented in `SCHEMA.md` should point at exactly where in the code it's
  implemented, so disagreeing with a call later means editing a function and
  re-running, not redoing the pipeline.

## The phase split

- **Phase 1 (Fable):** the unbounded, judgment-heavy work — acquiring messy
  real-world data (often through access paths that actively resist automation,
  as with both PeMS and, less severely, FRAP), cleaning it, building whatever
  structure the domain needs (a dataset, a network graph, whatever), and
  documenting every decision. Stops *before* any actual statistical or
  optimization analysis — that boundary should be stated explicitly in
  Fable's prompt, not left implicit.
- **Phase 2 (Opus):** bounded, well-specified — applying an established
  method to the artifact Phase 1 produced. Reads only `artifacts/` and
  `SCHEMA.md`, never the acquisition code or raw data directly. This is
  usually the actual fitting, solving, or hypothesis-testing step, and it's
  cheap to re-run whenever a Phase 1 decision changes.

## Why the split, generally

The pattern that's held across both projects so far: data acquisition and
cleaning in the real world has no clean specification — there's always a
judgment call about how to handle a gap, a duplicate, an access restriction,
an outlier. That's where paying for Fable's long-horizon autonomy and
self-verification is worth it. Once the data is clean and documented, the
actual analytical method is usually textbook — a known statistical test, a
known optimization algorithm — and Opus is very good at that without needing
the frontier price tag.
