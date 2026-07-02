# Before You Hand This to Fable

Every item here exists because skipping it caused a real problem on one of
the first two projects (wildfire SOC or Bay Area Braess's paradox). This
isn't aspirational best-practice — it's a record of specific corrections.

- [ ] **Framed as infrastructure, not a report.** The brief's opening states
      the deliverable is a pipeline + artifact contract, with the actual
      analysis as the exercise that proves it works — not the other way
      around. (Corrected after the wildfire project was first scoped as a
      one-off report.)
- [ ] **Phase 1's scope explicitly excludes Phase 2's analysis.** Fable is
      told directly not to do the statistical/optimization work, not just
      left to infer the boundary. (The whole reason for the split collapses
      if this isn't explicit — Fable is capable enough to just keep going.)
- [ ] **Every SCHEMA.md decision is traceable to a specific function**, not
      just described in prose. Documentation without this is not the same
      as being able to cheaply change your mind later.
- [ ] **Raw data is preserved untouched**, separate from processed data and
      artifacts. Nothing is ever cleaned in place.
- [ ] **One command regenerates everything** in `artifacts/` from `data/raw/`,
      deterministically (fixed seeds anywhere randomness appears).
- [ ] **Git from the first commit**, not added after the fact.
- [ ] **Any real access restriction on the data source is named explicitly**
      in the prompt (e.g. PeMS blocking programmatic bulk access) — don't
      assume Fable will discover and respect a provider's terms of use on
      its own initiative.
- [ ] **Known data-quality issues are stated up front**, not left for Fable
      to quietly discover and route around without documenting.
- [ ] **The Fable prompt never asks it to "explain its reasoning" or "show
      its thought process."** That phrasing can trigger the
      reasoning_extraction classifier and silently fall back to Opus. Ask
      for conclusions plus evidence instead.
- [ ] **Verification is via a fresh-context subagent at named checkpoints**,
      not self-critique in the same context.
- [ ] **A running NOTES.md is required**, logging decisions and why they
      were made, not just a final summary.
- [ ] **Progress claims must be audited against real tool output** before
      being reported — this is the single instruction Anthropic's own
      guidance credits with nearly eliminating fabricated status reports.
- [ ] **Effort is set explicitly** (high by default, xhigh for the hardest
      part) if running via Claude Code or the API.
- [ ] **Opus's prompt points only at `artifacts/` and `SCHEMA.md`**, never
      at raw data or Phase 1's code.
- [ ] **Opus is required to validate before trusting its own result** — e.g.
      does a fitted model reproduce known behavior, does a solved
      equilibrium reproduce observed data — before building further
      conclusions on top of it.
- [ ] **No site, no presentation layer, built in this pass.** `site/` stays
      a placeholder until that's a deliberate, separate decision.
