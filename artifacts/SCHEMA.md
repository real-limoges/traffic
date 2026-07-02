# Artifact Schema — `artifacts/network_graph.json`

This file is what Phase 2 (or anyone else) reads instead of the
acquisition/cleaning code. It documents every field, every calibration
decision (each pointed at the exact code that implements it), and every
known gap.

> **STATUS: schema complete, artifact not yet generated.** The pipeline is
> built and verified against synthetic PeMS-format fixtures with planted
> ground truth (`make test`), but the real PeMS pull has not happened —
> see PROVENANCE.md for why and `data/raw/README.md` for the manual steps.
> `make artifacts` produces `network_graph.json` deterministically once
> the raw data is in place. Everything below describes that output
> exactly; nothing about the schema depends on the data values.

## Top-level structure

```json
{ "meta": {...}, "nodes": [...], "edges": [...] }
```

Volume-delay function on every edge (standard BPR form):

```
t(v) = t0_sec * (1 + alpha * (v / capacity_vph) ^ beta)
```

with `v` in veh/hr summed across lanes. All flows in this artifact are
station totals (all lanes), never per-lane, unless the field name says
`vphpl`.

## `meta`

| Field | Type | Description | Known caveats |
|---|---|---|---|
| `name` | str | Human label for the artifact | |
| `pems_pull` | str | Name of the raw pull directory (pins the date range; cross-check PROVENANCE.md) | |
| `scope.district` | int | PeMS district (4 = Bay Area) | |
| `scope.routes` | int[] | Freeway numbers included (80, 101, 280, 580, 880) | I-680, I-980, SR-24, SR-92 etc. are absent — see Known gaps |
| `scope.lane_types` | str[] | PeMS lane types used as graph edges (`ML`) | HOV lanes deliberately excluded — see decisions |
| `vdf_form`, `units` | str/obj | Formula and units, restated machine-adjacent | |
| `counts` | obj | node/edge totals and how many edges run on default (uncalibrated) VDFs | If `edges_default_vdf` is a large fraction, treat results with suspicion |
| `diagnostics` | obj | From graph construction: long-gap edge count, crossings detected/unanchored | |

## `nodes[]`

| Field | Type | Description | Known caveats |
|---|---|---|---|
| `id` | str | `"S<station_id>"` — every node is a mainline detector station | There are no separate "interchange nodes"; see decisions |
| `type` | str | Always `"station"` | |
| `station_id` | int | PeMS station ID (joins back to raw data) | |
| `fwy` | int | Freeway number | |
| `direction` | str | `N`/`S`/`E`/`W` — a node belongs to ONE directional carriageway | The two directions of a freeway are separate node chains |
| `abs_pm` | float | PeMS absolute postmile (miles); position along the route | |
| `lat`, `lon` | float | WGS84, 6 dp | From PeMS metadata; occasional stations have stale coords |
| `lanes` | int | Mainline lane count at the station | |
| `name` | str | PeMS station name (human orientation only) | |

## `edges[]`

| Field | Type | Description | Known caveats |
|---|---|---|---|
| `id` | str | `ML_<fwy><dir>_<fromSid>_<toSid>` or `CN_<crossing>_<from>_<to>` | Stable across re-runs of the same pull |
| `from`, `to` | str | Node ids; edge is DIRECTED with traffic flow | |
| `edge_type` | str | `"mainline"` or `"connector"` | Connectors are assumed, not observed — see decisions |
| `fwy` | int\|null | Freeway number; null for connectors | |
| `direction` | str | `N/S/E/W` for mainline; `"80E->880N"` style for connectors | |
| `length_mi` | float | Mainline: \|ΔAbs_PM\| between endpoints. Connectors: fixed `CONNECTOR_LENGTH_MI` (0.5) | Postmile differences, not driven geometry; ~exact on freeways |
| `lanes` | int | From the measurement station (mainline) or `CONNECTOR_LANES`=1 | Lane drops mid-segment are invisible |
| `vdf.t0_sec` | float | Free-flow traversal time, seconds | |
| `vdf.capacity_vph` | float | Practical capacity, veh/hr, all lanes | |
| `vdf.alpha`, `vdf.beta` | float | BPR shape parameters | |
| `vdf.fit_method` | str | `"fitted"` (per-edge regression), `"default"` (canonical 0.15/4.0), `"connector_default"` | ALWAYS check this before trusting an edge |
| `observed` | obj\|null | Real-data summary for the measurement station; null for connectors | |
| `observed.ffs_mph` | float | Estimated free-flow speed | |
| `observed.flow_vph_{p5,p50,p95}` | float | Percentiles of observed hourly-scaled flow (all valid 5-min intervals × 12) | Includes nights/weekends; not peak-only |
| `observed.flow_vph_{am,pm}_peak` | float | Weekday 7–9h / 16–18h mean flows | Phase 2's equilibrium sanity check material |
| `observed.n_days` | int | Days of valid data behind the calibration | |
| `observed.coverage` | float | Fraction of 5-min intervals valid after quality rules | |
| `observed.bpr_n_points` | int | Congested 15-min points behind the alpha/beta fit | Small values mean the fit is weak even if `fitted` |
| `flags` | str[] | See flag table below | |

### Edge flags

| Flag | Meaning |
|---|---|
| `long_gap` | Consecutive detectors > 5 mi apart (`config.MAX_SEGMENT_GAP_MI`); the edge exists but its calibration extrapolates across a detector desert |
| `connectivity_assumed` | Connector inferred from geometry crossing, not from ramp data; the movement may not physically exist |
| `default_vdf` / `default_ffs` / `default_capacity` / `default_bpr` | The named quantity fell back to configured defaults instead of being estimated from data |
| `thin_data` | Measurement station had < `MIN_CALIBRATION_DAYS` (10) valid days; ALL its estimates are defaults |
| `no_readings` | Station present in metadata but produced zero readings in the pull |

## Cleaning and calibration decisions

Every decision names the exact code. Constants live in
`pipeline/config.py`; changing a call = edit constant/function, re-run
`make artifacts`.

### Station scope
- **What was decided:** District 4 only; freeways 80, 101, 280, 580, 880;
  lane type `ML` only. HOV excluded.
- **Why:** The brief scopes to the Bay Area trunk network. HOV lanes are
  access-restricted parallel facilities; folding their flow into mainline
  capacity would bias VDFs optimistic.
- **Where in the code:** `pipeline/config.py: SCOPED_ROUTES,
  MAINLINE_TYPES`; filter in
  `pipeline/stages/ingest_metadata.py: run()`.
- **What would change if you disagreed:** Add route numbers / `"HV"` to the
  constants and re-run; the graph gains chains, nothing else changes.

### Duplicate stations at one postmile
- **What was decided:** When several station IDs share (fwy, dir, Abs_PM),
  keep the one with the most lanes, tie-break lowest ID.
- **Why:** These are typically detector replacements; the fullest
  cross-section is likeliest the live mainline station. Deterministic.
- **Where in the code:** `pipeline/stages/ingest_metadata.py: run()`
  (sort + drop_duplicates block).
- **What would change:** A coverage-based pick (most valid data) would be
  better but couples metadata ingest to readings; revisit if real data
  shows replaced-detector ghosts.

### Quality rules A–E
- **What was decided:** (A) intervals with `pct_observed` < 75 or
  `samples`=0 are "PeMS-imputed", excluded from calibration; (B) nulls
  excluded; (C) implausible values excluded (speed outside 3–100 mph,
  occupancy > 1, per-lane 5-min flow > 250); (D) station-days < 50% valid
  dropped whole; (E) stations with < 10 valid days are never calibrated
  (defaults + `thin_data`).
- **Why:** PeMS's `% Observed` is the only honest boundary between
  measurement and PeMS's own imputation model. Rows are marked, not
  deleted, so `data/processed/quality_report.json` can account for every
  exclusion.
- **Where in the code:** `pipeline/stages/quality_filter.py: run()`;
  thresholds `pipeline/config.py: MIN_PCT_OBSERVED …
  MIN_CALIBRATION_DAYS`.
- **What would change:** Any threshold is one constant. Loosening
  `MIN_PCT_OBSERVED` to 50 admits more PeMS-imputed data (smoother but
  model-flavored); the quality report shows exactly how many rows move.

### Imputation
- **What was decided:** Linear interpolation of flow/occupancy/speed for
  gaps ≤ 3 consecutive 5-min intervals, within one station-day; longer
  gaps stay missing. Imputed rows flagged, excluded from free-flow and
  BPR estimation, included in 15-min rolling windows.
- **Why:** Short dropouts are detector hiccups; bridging them keeps
  sustained-rate windows intact. Inventing longer stretches is fiction.
- **Where in the code:** `pipeline/stages/impute.py: _impute_day()`;
  `config.MAX_IMPUTE_GAP_INTERVALS`.
- **What would change:** Raise the gap limit or switch to day-of-week
  profile filling in `_impute_day()`; the `imputed` flag keeps any such
  change auditable downstream.

### Chain orientation
- **What was decided:** N/E chains run in increasing absolute postmile,
  S/W in decreasing.
- **Why:** Caltrans postmiles increase generally south→north and
  west→east; this is the PeMS convention.
- **Where in the code:** `pipeline/stages/build_graph.py: _chains()`.
- **What would change:** If a route violated the convention locally, its
  edges would point against traffic; spot-check `abs_pm` monotonicity
  against a map when the real artifact exists (flagged as unverified in
  Known gaps).

### Interchange detection and connectors
- **What was decided:** Freeway crossings come from shapely intersections
  of the SHN route geometries (concurrencies contribute their segment
  endpoints; nearby points cluster within 2 mi). Each crossing anchors to
  the NEAREST detector node per (route, direction) within 3 mi; connector
  edges are added for every direction-pair movement, 0.5 mi long, 40 mph,
  1 lane, default BPR, flagged `connectivity_assumed`.
- **Why:** SHN lines carry no ramp topology, so which movements exist
  cannot be observed — assuming all and flagging is honest; anchoring to
  detectors keeps edge granularity uniform instead of splicing unmeasured
  stub segments.
- **Where in the code:**
  `pipeline/stages/ingest_topology.py: run(), _cluster()`;
  `pipeline/stages/build_graph.py: run()` (connector block);
  `config.INTERCHANGE_SNAP_MI, CONNECTOR_*`.
- **What would change:** A real ramp inventory (e.g. PeMS `FF` detectors
  or OpenStreetMap ramps) could replace assumed movements; that is a new
  ingest stage, not a rewrite — connectors are isolated in one block and
  one flag.

### Edge ↔ measurement station assignment
- **What was decided:** A mainline edge takes ALL its traffic data from
  its upstream (from-) station.
- **Why:** Traffic crossing the upstream detector is what enters the
  segment; one unambiguous source beats averaging two detectors that may
  disagree about lane counts and quality.
- **Where in the code:** `pipeline/stages/build_graph.py: run()`
  (`measurement_station` field), consumed in
  `pipeline/stages/emit.py: run()`.
- **What would change:** Averaging from/to stations would smooth noise at
  the cost of mixing cross-sections; change it in `emit.py` only.

### Free-flow speed
- **What was decided:** Median speed over non-imputed valid intervals in
  22:00–05:00 with occupancy < 0.08, clamped to [50, 75] mph; < 100 usable
  observations → 65 mph default + flag.
- **Why:** Low-occupancy night traffic is as close to unconstrained as
  freeway data gets; the clamp guards against sensor bias (chronically
  miscalibrated speed traps).
- **Where in the code:** `pipeline/stages/calibrate.py: _ff_speed()`;
  `config.FF_*`.
- **What would change:** Wider clamp admits real 80 mph free-flow
  stretches at the risk of trusting hot sensors.

### Capacity
- **What was decided:** 99th percentile of sustained 15-minute flow rates
  (rolling 3×5-min, ≥2 valid) per lane, clamped to [1400, 2400]
  veh/hr/lane; no usable windows → 1900 default + flag.
- **Why:** HCM-style practical capacity from observed sustained maxima;
  15-min smoothing kills single-interval spikes; p99 resists outliers
  while still reaching the congested regime.
- **Where in the code:** `pipeline/stages/calibrate.py:
  _sustained_rates(), _capacity()`; `config.CAPACITY_*, ROLLING_*`.
- **Known bias, stated plainly:** on segments that never saturate during
  the pull, p99 measures peak *demand*, not capacity — capacity is then
  underestimated and v/c overestimated. Fixture tests show ~±10% recovery
  when the segment does reach saturation.
- **What would change:** A fundamental-diagram fit (flow vs occupancy
  breakpoint) is the principled upgrade; it slots into `_capacity()`.

### BPR fit
- **What was decided:** `log(t/t0 − 1) = log α + β·log(v/c)` by OLS over
  non-imputed congested 15-min points (t/t0 > 1.05, v/c > 0.2); accepted
  only with ≥ 200 points and α ∈ [0.01, 1.5], β ∈ [1, 10]; otherwise
  canonical (0.15, 4.0) + flag.
- **Why:** Log-space linearizes BPR exactly; the acceptance box rejects
  fits driven by noise on barely-congested segments rather than shipping
  absurd exponents.
- **Where in the code:** `pipeline/stages/calibrate.py: _bpr_fit()`;
  `config.BPR_*`.
- **What would change:** Robust regression (Huber) or per-corridor
  pooling for thin segments; both are local to `_bpr_fit()`.

### Determinism
- **What was decided:** No randomness anywhere; sorted groupbys and
  iteration; artifact JSON key-sorted, floats rounded (coords 6 dp, rest
  4 dp). Byte-identical re-runs are a test
  (`tests/test_pipeline.py: test_determinism`).
- **Where in the code:** `pipeline/stages/emit.py`; `config.ARTIFACT_*`.

## Known gaps and limitations

- **The artifact does not exist yet.** Real PeMS data has not been pulled
  (no credentials / no Caltrans network route from the build environment —
  PROVENANCE.md). Everything above is verified against synthetic
  format-faithful fixtures only.
- **No OD demand.** The contract is the network + VDFs + observed flow
  ranges. Phase 2 must construct demand (e.g. OD estimation matching
  `observed.flow_vph_*`) and validate equilibrium flows against the same
  fields.
- **Network completeness:** only the five scoped routes. Missing real
  Bay Area links (I-680, I-980, SR-24, SR-92, SR-237, bridges' approaches
  beyond scoped routes) mean some real-world routing alternatives don't
  exist in the model; Braess candidates near scope boundaries are suspect.
- **Connector movements are assumed complete** (`connectivity_assumed`) —
  some modeled ramps don't exist (e.g. left-exit restrictions, missing
  movements at partial interchanges). Phase 2 should sensitivity-test
  against pruning these.
- **On/off-ramps to surface streets are not modeled at all.** Traffic can
  only enter/exit the model at nodes via Phase 2's demand loading;
  intermediate metering/queueing at ramps is invisible.
- **Edge granularity = detector spacing.** Sub-segment features (lane
  drops, weaving sections) are smeared into the segment VDF.
- **Capacity ≈ demand on never-saturated segments** (see Capacity
  decision) — biases those edges toward too-small capacity.
- **PeMS coordinate/postmile errors** exist in the wild (stations with
  stale metadata). The dedup rule and clamps catch some; a map-level
  visual audit is listed as REQUIRED VERIFICATION once real data lands.
- **Unverified until real data:** chain-orientation convention per route,
  crossing detection against the real SHN export's property names
  (`ingest_topology.ROUTE_PROP_CANDIDATES` covers common variants and
  fails loudly otherwise), and the fraction of edges landing on default
  VDFs.
