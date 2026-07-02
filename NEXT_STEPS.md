# NEXT STEPS — finishing Phase 1 once you have a PeMS account

**Start here when you come back.** This is the one doc that tells you
everything needed to turn the finished pipeline into the real
`artifacts/network_graph.json`. It assumes no memory of the session that
built this — a couple of days will have passed and the chat is gone.

---

## Where things stand

Phase 1 (the calibrated Bay Area freeway network model) is **built,
tested, and audited — except for the one step a machine can't do for you:
pulling the data.** Concretely:

- The pipeline exists: 8 named, re-runnable stages under `pipeline/`,
  driven by `make artifacts`.
- Its mechanics are verified against synthetic PeMS-format fixtures with
  planted ground truth — `make test` (8 passing tests) recovers the
  known free-flow speed / capacity / BPR curve and exercises every
  data-quality rule.
- **`artifacts/network_graph.json` does not exist yet**, on purpose.
  `make artifacts` refuses to fabricate one from fixture data — with no
  real pull under `data/raw/`, it stops with a message pointing back here.
- Documentation is complete and honest about what's unverified:
  `artifacts/SCHEMA.md` (every field + every calibration decision + known
  gaps), `PROVENANCE.md` (source pins, currently `PENDING`), `NOTES.md`
  (running decision log).

Nothing about the code is waiting on you. Only the data is.

---

## ⚠️ The one thing that trips people up

**The PeMS download happens in a web browser on your own machine, not
inside a Claude session.** Two independent reasons:

1. PeMS requires an interactive login and clicking through its Data
   Clearinghouse — there is deliberately no bulk API to script.
2. Claude's cloud execution environment blocks outbound access to all
   Caltrans hosts anyway (verified: proxy returns 403). A fresh Claude
   session **days from now will still be blocked** — this is not a
   temporary state that clears.

So the clean path is: **do the whole thing locally.** Clone the repo on
your own machine, download the data there, run `make artifacts` there,
then commit only the small outputs (see step 6). The raw PeMS files
(multi-GB) are `.gitignore`d and are *not* meant to travel through git —
`PROVENANCE.md` + `data/raw/SHA256SUMS` are the committed record of what
you pulled.

---

## The steps

### 1. Get the PeMS account (the slow part — a few days)
Register at <https://pems.dot.ca.gov>. Account approval is what takes
time; everything below is quick once you're in.

### 2. Set up the code locally (one-time, ~2 min)
Requires Python 3.11+.
```bash
git clone <this repo> && cd traffic
git checkout claude/phase-1-network-model-fyjrbz
pip install -r requirements.txt
make test        # optional sanity check — 8 tests, needs no data
```

### 3. Download the two data sources
Full click-path and exact filenames are in **`data/raw/README.md`** — the
authoritative spec. In brief:

- **PeMS detector data** (needs your account): PeMS → *Tools → Data
  Clearinghouse* → District 4. Download **Station 5-Minute** files for a
  full recent month (≥ 20 weekdays, no major holidays — May 2026 is a fine
  default) plus the **Station Metadata** file dated at or before the end of
  that range. Drop them all, flat, into
  `data/raw/pems-d04-<start>-<end>/` (e.g. `pems-d04-20260501-20260531/`).
  Leave the 5-min files gzipped.
- **Highway topology** (public, no account): export the **State Highway
  Network Lines** layer as GeoJSON from
  <https://gisdata-caltrans.opendata.arcgis.com> to
  `data/raw/caltrans-network-topology/shn_lines.geojson`.

### 4. Pin what you pulled
```bash
make pin-raw     # writes data/raw/SHA256SUMS and prints the checksums
```
Then edit **`PROVENANCE.md`**: replace every `PENDING` with the actual
fetch date, the pull-directory name, the metadata file's date, the
portal's "Data Updated" date for the SHN layer, and paste in the
checksums. This is what makes the run reproducible a year from now.

### 5. Build the artifact
```bash
make artifacts   # runs all 8 stages: data/raw/ -> artifacts/network_graph.json
```
Deterministic — same input yields byte-identical output. If a stage stops
with a clear error (e.g. the metadata file lacks an expected column, or a
scoped route is missing from the topology export), it's telling you
something real about the download; fix the input and re-run. Individual
stages are re-runnable too: `python3 -m pipeline.run calibrate` etc.
(see `python3 -m pipeline.run` with no args for the list).

### 6. Commit the outputs
```bash
git add artifacts/network_graph.json PROVENANCE.md data/raw/SHA256SUMS
git commit -m "Phase 1: generate network_graph.json from <pull id>"
git push
```
(The raw data itself stays local and gitignored — that's intended.)

---

## Before you trust it — a 15-minute sanity pass

The pipeline is honest about what it *can't* self-verify without real
data. `artifacts/SCHEMA.md` → "Known gaps" is the full list; the three
worth eyeballing once the artifact exists:

- **Map check.** Open `artifacts/network_graph.json`, spot-check a handful
  of node lat/lon against a map — are stations on the freeways they claim,
  in postmile order? PeMS occasionally has stale coordinates.
- **Default-VDF fraction.** Check `meta.counts.edges_default_vdf` against
  total edges. A small fraction is fine; if most edges fell back to
  default volume-delay functions, the pull was too short or too sparse —
  grab more days and re-run. (Per-edge `flags` say exactly which estimate
  defaulted and why.)
- **Interchanges.** `meta.diagnostics` reports crossings detected and any
  that went unanchored. Sanity-check the count against the real
  interchanges among I-80/101/280/580/880.

If those look right, Phase 1 is genuinely done and the artifact is ready
for Phase 2 (Opus solves equilibrium and hunts the Braess paradox —
that phase reads only `artifacts/`, never this pipeline or the raw data).

---

## Map of the repo (where to look for what)

| You want… | Look at |
|---|---|
| These instructions | **`NEXT_STEPS.md`** (this file) |
| Exact download filenames & folder layout | `data/raw/README.md` |
| What every artifact field means + why each calibration choice | `artifacts/SCHEMA.md` |
| Source pins / reproducibility record | `PROVENANCE.md` |
| Why decisions were made, chronologically | `NOTES.md` |
| The pipeline code (one file per stage) | `pipeline/stages/` |
| Every tunable threshold in one place | `pipeline/config.py` |
| Commands | `Makefile` (`make artifacts`, `make test`, `make pin-raw`) |
| The overall two-phase plan | `PROJECT_BRIEF.md` |

Bringing a fresh Claude session up to speed later? Point it at
`PROJECT_BRIEF.md`, this file, and `artifacts/SCHEMA.md` — that's enough
to resume without re-deriving anything.
