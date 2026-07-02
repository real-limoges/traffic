# Research Infrastructure Brief — Braess's Paradox in Bay Area Freeways
### Split Across Fable and Opus

> Instantiated from `research-project-template`. Repo: `traffic`.

## The actual goal

Same shape as this template exists to enforce: Fable does the unbounded,
judgment-heavy work of turning messy real-world sensor data into a clean,
calibrated, verified network model. Opus does the bounded, well-specified
work of solving traffic assignment on that model and hunting for genuine
Braess-paradox edges. Neither model does the other's job.

**Why split it this way:** PeMS is real-world-messy in a way that has no
clean specification — Caltrans deliberately blocks programmatic bulk access
(registered-account, manual/batch-download only, not a clean API), ~40,000
detectors have real outages and bad readings that need judgment to reconcile,
and turning raw detector/postmile metadata into an actual routable network
graph with realistic per-segment cost functions is genuine engineering
judgment. Once that calibrated graph exists, solving for user equilibrium and
system optimum is a mechanical application of an established method
(Frank-Wolfe / method of successive averages traffic assignment) — well-
specified, textbook operations research, no reason to pay Fable's rate for it.

## The research question

Are there real segments of the Bay Area freeway network where selfish,
user-equilibrium routing is measurably worse than it would be without that
segment — genuine Braess-paradox-consistent edges — detectable from actual
PeMS flow and travel-time data, rather than the synthetic toy networks most
Braess's-paradox demonstrations use?

Background, for context, not to be taken on faith: Braess's paradox is a
proven result — in certain network topologies, adding capacity can make
travel times worse for everyone, because drivers routing toward their own
individual optimum push the system away from its collective optimum. It's not
a metaphor; it's a theorem about the gap between Nash-equilibrium routing and
system-optimal routing, and there are documented real-world cases (Seoul,
NYC) where closing a road measurably improved traffic.

## Scope

**Bay Area freeway network** (I-80, I-880, I-580, I-280, US-101, and their
major interchanges) rather than statewide — dense PeMS coverage, personally
relevant, computationally tractable for a first real pass. Expand later if
the methodology holds up.

## The artifact contract

```
traffic/
  data/
    raw/
      pems-<region>-<date-range>/    # raw detector data, via PeMS's own
                                      # registered-account access — no scraping
                                      # automation that violates their terms
      caltrans-network-topology/     # highway/interchange GIS data
    processed/
      detector_readings.parquet
  analysis/
    *.py or *.qmd                    # Phase 2 assignment + paradox detection
  artifacts/                         # the STABLE CONTRACT
    network_graph.json               # << Phase 1 (Fable) stops here
                                      #   nodes = interchanges/ramps, edges =
                                      #   segments, each with a calibrated
                                      #   volume-delay function (BPR-style:
                                      #   free-flow time, capacity, calibration
                                      #   params), observed flow ranges
    SCHEMA.md                        # << Phase 1 — every field, every
                                      #   calibration choice, every gap
                                      #   (sensor outages, imputation method,
                                      #   how conflicting readings were
                                      #   reconciled)
    equilibrium_results.json         # << Phase 2 (Opus)
    braess_candidates.json           # << Phase 2 (Opus)
    summary.json                     # << Phase 2 (Opus)
    figures/*.svg
  paper/
    paper.qmd                        # renders from artifacts/ only
  site/                              # NOT built now — placeholder
  PROVENANCE.md                      # << Phase 1 — PeMS pull dates, detector
                                      #   station list version, network
                                      #   topology source/version
  Makefile                           # << Phase 1 — one command regenerates
                                      #   network_graph.json from data/raw/
```

## Phase 1 — Fable: build the calibrated network

### What "done" looks like
- `artifacts/network_graph.json` fully populated: a routable graph of the Bay
  Area freeway network, each edge carrying a calibrated volume-delay function
  derived from real PeMS flow/speed/occupancy history
- `artifacts/SCHEMA.md` (skeleton already in this repo) filled in completely
  — every field, every calibration decision, every known gap — written so
  Opus never needs to see the acquisition or calibration code to trust the
  network
- `PROVENANCE.md` (skeleton already in this repo) filled in, pinning the
  exact PeMS pull and the network topology source
- Data acquired through PeMS's actual registered-account access path — not
  scraping that violates their access terms. This is a real constraint, not a
  suggestion: work within it rather than around it.
- One command (`make artifacts`) regenerating `network_graph.json` from
  `data/raw/` deterministically
- The acquisition and calibration logic structured as discrete, named,
  re-runnable stages, git-committed as it goes — disagreeing with a
  calibration choice later should mean editing a function and re-running,
  not redoing the pipeline

### Non-goals for Phase 1
- No traffic assignment solving (user equilibrium / system optimum) — Opus's
  job in Phase 2
- No real-time forecasting or prediction — this is a static model built from
  historical data
- No transit or rail modeling — freeways only
- No live site — `site/` stays a placeholder

### Working notes for Fable specifically
- Framed at the upper end of difficulty on purpose. Real judgment calls, not
  a checklist.
- Ask for verification via a fresh-context subagent at natural checkpoints —
  after initial data acquisition, after network topology construction, after
  cost-function calibration — rather than self-critique in the same context.
- Give it a running `NOTES.md` — one lesson per entry, including *why* each
  cleaning or calibration decision was made.
- Require it to audit every progress claim against real tool output before
  reporting, and to state plainly what's unverified.
- If working via Claude Code or the API: set effort to **high** by default,
  bump to **xhigh** if the network reconstruction gets genuinely gnarly.
- Don't ask it to "explain its reasoning" or "show its thought process"
  verbatim — that phrasing can trip a classifier and silently fall back to
  Opus. Ask for conclusions plus evidence instead.

### Kickoff prompt for Fable

> This repo was created from a template — `Makefile`, `.gitignore`,
> `PROVENANCE.md`, and `artifacts/SCHEMA.md` already exist as skeletons for
> you to fill in, not files to create from scratch. Read them first.
>
> I want you to build a calibrated, routable network model of the Bay Area
> freeway system from real Caltrans PeMS sensor data — not answer the
> research question yet. The deliverable is `artifacts/network_graph.json`: a
> graph where nodes are interchanges/ramps and edges are freeway segments,
> each edge carrying a calibrated volume-delay function (free-flow travel
> time, practical capacity, calibration parameters) derived from real
> historical flow, speed, and occupancy data — plus documentation complete
> enough that someone else can trust and use it without reading your
> acquisition code.
>
> Source: Caltrans' Performance Measurement System (PeMS) —
> https://dot.ca.gov/programs/traffic-operations/mpr/pems-source . This
> requires a free registered account, and Caltrans deliberately does not
> support programmatic bulk access — work within their actual access path
> (manual or batch export through the registered account), not around it. You
> will also need Caltrans highway/interchange topology data to build the
> graph structure itself, not just the detector readings.
>
> Scope this to the Bay Area freeway network (I-80, I-880, I-580, I-280,
> US-101 and their major interchanges), not statewide. PeMS has real known
> data quality issues — detector outages, dropped readings, occasional bad
> sensors — handle these explicitly and document your approach (imputation
> method, how you reconciled conflicting readings) rather than quietly
> dropping data.
>
> Fill in `PROVENANCE.md` with the exact PeMS pull (date range, detector
> station list version) and topology source. Structure the acquisition and
> calibration logic as discrete, named, re-runnable stages, and point each
> documented decision in `SCHEMA.md` at exactly where in the code it's
> implemented. Commit as you go — this repo already has git history from the
> template; don't start over. One command (`make artifacts`) should
> regenerate `network_graph.json` from `data/raw/` deterministically.
>
> Do not solve for traffic equilibrium or attempt any paradox detection —
> stop once the network model and its documentation are complete and
> verified. That's a separate phase.
>
> This is genuinely open-ended on the data-acquisition and calibration
> judgment calls — use your own judgment and check in with me only if
> something is truly ambiguous. Verify your own work with a fresh-context
> subagent at natural checkpoints. Keep a running `NOTES.md` as you go. Before
> reporting anything as done, audit the claim against actual tool output from
> this session, and say plainly if something's still unverified.

## Phase 2 — Opus: solve the network and hunt for the paradox

Run this only after Phase 1's output has been spot-checked. Point Opus at
`artifacts/network_graph.json` and `artifacts/SCHEMA.md` — it shouldn't need
anything else.

### What "done" looks like
- `artifacts/equilibrium_results.json` — a user-equilibrium flow solution
  (Frank-Wolfe or method of successive averages) and a system-optimum flow
  solution for the calibrated network
- A sanity check *before* trusting anything further: does the modeled
  equilibrium roughly reproduce the flows actually observed in the PeMS data?
  If not, say so plainly rather than proceeding as if the model were validated
- `artifacts/braess_candidates.json` — for each edge, the counterfactual
  total-system travel time under user equilibrium with that edge removed,
  ranked by whether removal actually improves total travel time (the real
  Braess-paradox test), with honest sensitivity treatment rather than a
  single point estimate presented as certain
- `summary.json` and `paper/paper.qmd` — clear about what a "candidate" edge
  means (a model-based prediction) versus what would be required to confirm
  it against reality, aimed at a technically literate non-specialist

### Kickoff prompt for Opus

> Read `artifacts/network_graph.json` and `artifacts/SCHEMA.md` in this repo.
> Using that calibrated network, solve for the user-equilibrium traffic
> assignment (drivers routing to minimize their own travel time) and the
> system-optimum assignment (routing that minimizes total system travel
> time). Before doing anything further, sanity-check the equilibrium solution
> against the actual observed PeMS flows in the dataset and report plainly
> whether the model reproduces reality reasonably well.
>
> Then run the actual test: for each edge in the network, compute the
> counterfactual total system travel time under user equilibrium if that edge
> were removed. Rank edges by whether their removal would improve total
> travel time — that's the definition of a genuine Braess-paradox-consistent
> edge, a segment whose presence makes selfish routing collectively worse.
> Write the equilibrium solutions to `artifacts/equilibrium_results.json` and
> the ranked candidates to `artifacts/braess_candidates.json`.
>
> Write a headline summary to `artifacts/summary.json` and a full write-up to
> `paper/paper.qmd` that renders to PDF via Quarto, computing nothing inline
> that isn't sourced from the artifacts. Be explicit about the distinction
> between a modeled candidate edge and a confirmed real-world finding, and be
> honest about where the model's assumptions are doing a lot of work versus
> where the result is robust.
