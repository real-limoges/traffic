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
