# NOTES — running log, one lesson per entry

Newest entries at the bottom. Each entry: what was decided/learned, and why.

## 2026-07-02 — Environment audit before writing any code
Probed the execution environment first instead of assuming. Findings, from
actual tool output: no PeMS credentials anywhere in the environment; the
network proxy returns 403 CONNECT for `pems.dot.ca.gov`, `dot.ca.gov` GIS
hosts, `data.ca.gov`, and `zenodo.org` (only package registries and the
scoped GitHub repo are allowlisted). Consequence: the real data pull is
impossible from this session — not because of PeMS's no-bulk-access terms
but because of the sandbox's own egress policy. Decision: build Phase 1 as
what it is contractually — a deterministic pipeline from `data/raw/` to
`artifacts/network_graph.json` — against PeMS's documented Clearinghouse
file formats, prove the mechanics with clearly-labeled synthetic test
fixtures, and leave `PROVENANCE.md` with explicit PENDING pins plus exact
download instructions. Explicitly rejected: substituting a third-party
mirror of old PeMS exports (e.g. the PEMS-BAY/PeMSD4 research datasets).
The brief makes registered-account acquisition part of "done", those
mirrors are speed-only or anonymize station locations, and swapping sources
is a scope decision the project owner should make, not me.

## 2026-07-02 — Templates were at repo root, not in place
The brief says `PROVENANCE.md` and `artifacts/SCHEMA.md` "already exist as
skeletons". In reality the repo has `PROVENANCE.template.md` and
`SCHEMA.template.md` at the root. Instantiated them at the paths the
artifact contract specifies and left the templates untouched (they're the
template's property, not this project's).

## 2026-07-02 — 5-minute data over hourly
Chose the Clearinghouse `station_5min` product as the calibration input
rather than `station_hour`. Reason: capacity estimation needs sub-hourly
resolution (practical capacity is estimated from high-percentile 15-minute
flow rates, the standard HCM-style approach; hourly averages smear the
peaks), and the 5-min product carries the `% Observed` field per interval,
which is the only honest way to distinguish PeMS's own imputation from
ground truth. Cost: bigger files (~15–40 MB/day gzipped for D4), accepted.

## 2026-07-02 — Graph nodes from detectors + interchanges, not raw GIS
Decided the routable graph's backbone is the ordered chain of mainline
detector stations per (freeway, direction) using PeMS absolute postmile,
with interchange nodes inserted where scoped freeways cross (crossings
located from SHN geometry, then snapped to the postmile axis). Rejected
building the graph purely from SHN geometry: SHN lines carry no
detector linkage, so every edge would then need a second matching step
back to detectors anyway; postmile ordering *is* Caltrans's own linear
reference and gives edge lengths directly (ΔAbs_PM), with the geometry
kept for coordinates and crossing detection. Consequence documented in
SCHEMA.md: edge granularity = inter-detector spacing (~0.3–1 mi typical),
which is the natural resolution of the data.

## 2026-07-02 — No fabricated artifact
`make artifacts` fails loudly (with instructions) when `data/raw/` has no
PeMS pull, rather than emitting a graph built from fixture data. A
synthetic `network_graph.json` in `artifacts/` would be indistinguishable
from a real one to Phase 2 — the exact failure mode the artifact contract
exists to prevent. Synthetic data lives only under `tests/fixtures/` and is
generated on the fly by tests, never committed under `data/` or
`artifacts/`.

## 2026-07-02 — Calibration design: three estimates, three flagged fallbacks
Free-flow speed from low-occupancy night medians (not the speed limit —
sensors drift), practical capacity from p99 of sustained 15-min rates
(HCM-style; hourly averages smear peaks, single 5-min spikes lie), BPR
alpha/beta by exact log-space linearization fit only on genuinely
congested points, with an acceptance box. Every fallback is a flag on the
edge, never a silent substitution — Phase 2 must be able to weight edges
by how much of their VDF is measurement vs default. The known bias worth
remembering: on segments that never saturate, the capacity estimator
measures peak demand instead, so v/c runs hot there. Documented in
SCHEMA.md rather than "fixed" with a fudge factor.

## 2026-07-02 — Test what can be tested: plant ground truth, recover it
With no real data available, the honest verification target is the
mechanics: the fixture generator writes format-faithful PeMS files from a
KNOWN BPR curve (ffs 65, cap 2000 vphpl, alpha 0.3, beta 3) plus every
defect class the quality rules claim to handle. The suite recovered ffs
within 3 mph, capacity within 15%, beta within 1.0, confirmed each rule
fired (PeMS-imputed exclusion, implausible speeds, dead day dropped, thin
station defaulted, 2-interval gap imputed, 10-interval gap left missing),
and confirmed byte-identical artifacts across re-runs. First run caught a
real test-design bug: the "thin" station was planted at a chain terminus,
where it measures no edge — moved mid-chain.

## 2026-07-02 — Deviation from the brief's tree: three readings files, not one
The brief's artifact contract sketches `data/processed/detector_readings.parquet`;
the pipeline instead writes `readings_raw` / `readings_clean` /
`readings_final.parquet` — one file per stage boundary, so each quality and
imputation decision has an inspectable before/after. Deliberate deviation,
noted here rather than silently made.

## 2026-07-02 — Fresh-context audit round 1: 1 major, 7 minor, 5 nits
A fresh-context subagent audited the repo against the brief (it also
independently verified determinism across separate processes with
different hash seeds, and confirmed BPR math/units clean and scope
discipline intact). The real catch: `meta.counts.edges_default_vdf`
undercounted fully-default edges — thin-data mainline edges whose entire
VDF is defaults weren't counted or flagged, which would have made the
artifact's headline honesty signal read systematically low on real data,
where thin stations are the dominant default class. Fixed by flagging
`default_vdf` whenever all three estimates are defaults. Also fixed from
the audit: Rule D now measures against the full 288-interval day (a day
with 20 present-and-valid rows is 93% silent, not 100% valid) with an
absent-rows fixture case added; the quality report tallies reasons before
dead-day removal so no exclusion loses its reason; metadata selection
enforces "dated at or before range end" instead of silently taking the
latest; SNAP_SLACK/CROSSING_CLUSTER_MI moved into config.py where the
docs said all thresholds live; the determinism test re-runs all eight
stages; SCHEMA.md now states the alpha-capacity error coupling
(cap_err^beta), actual coverage semantics, actual rounding, and the
broadened `no_readings` meaning. Lesson: the self-reporting fields of an
artifact need the same adversarial scrutiny as the estimates — an honest
graph with a dishonest honesty-counter is still dishonest.
