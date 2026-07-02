"""Stage runner: python3 -m pipeline.run <stage|group> [...].

Stages (in canonical order):
  ingest_metadata   PeMS station metadata -> stations.parquet
  ingest_readings   PeMS 5-min files      -> readings_raw.parquet
  quality_filter    quality rules         -> readings_clean.parquet + report
  impute            short-gap filling     -> readings_final.parquet
  ingest_topology   SHN GeoJSON           -> topology.json
  build_graph       graph structure       -> graph_structure.json
  calibrate         VDF parameters        -> edge_calibration.parquet
  emit              final artifact        -> artifacts/network_graph.json

Groups: data (first four), graph (last four), all.
Each stage is independently re-runnable; disagreeing with a documented
decision means editing its function/constant and re-running from that
stage, not redoing the pipeline.
"""

import sys

from .stages import (
    build_graph,
    calibrate,
    emit,
    impute,
    ingest_metadata,
    ingest_readings,
    ingest_topology,
    quality_filter,
)

STAGES = {
    "ingest_metadata": ingest_metadata.run,
    "ingest_readings": ingest_readings.run,
    "quality_filter": quality_filter.run,
    "impute": impute.run,
    "ingest_topology": ingest_topology.run,
    "build_graph": build_graph.run,
    "calibrate": calibrate.run,
    "emit": emit.run,
}
GROUPS = {
    "data": ["ingest_metadata", "ingest_readings", "quality_filter", "impute"],
    "graph": ["ingest_topology", "build_graph", "calibrate", "emit"],
    "all": list(STAGES),
}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    names: list[str] = []
    for a in argv:
        if a in GROUPS:
            names.extend(GROUPS[a])
        elif a in STAGES:
            names.append(a)
        else:
            print(f"Unknown stage {a!r}. Known: {list(STAGES)} + {list(GROUPS)}")
            return 2
    for n in names:
        try:
            STAGES[n]()
        except FileNotFoundError as exc:
            print(f"\n[{n}] BLOCKED:\n{exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
