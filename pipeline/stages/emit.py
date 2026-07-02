"""Stage: emit — graph_structure + edge_calibration -> network_graph.json.

The only writer of the Phase 1 artifact. Deterministic output: nodes and
edges sorted by id, floats rounded to fixed precision, JSON key-sorted —
byte-identical output for byte-identical input.

Mainline edges take their VDF from their measurement (from-) station:
  t0_sec       = length_mi / ffs_mph * 3600
  capacity_vph = capacity_vphpl * lanes
  alpha, beta  from the station's BPR fit (or documented defaults)
Connector edges (no detectors) get the default connector VDF from
pipeline/config.py, flags making that unmistakable.

Every fallback that fired upstream surfaces here as edge flags:
"default_ffs", "default_capacity", "default_bpr", "thin_data",
"long_gap", "connectivity_assumed". Phase 2 can and should weight or
sensitivity-test against these.
"""

import json

import pandas as pd

from .. import config, paths


def _r(x: float, dp: int = config.ARTIFACT_FLOAT_DP) -> float:
    return round(float(x), dp)


def run() -> None:
    for p, hint in ((paths.GRAPH_STRUCTURE, "build_graph"),
                    (paths.EDGE_CALIBRATION, "calibrate")):
        if not p.exists():
            raise FileNotFoundError(f"Run {hint} first (missing {p.name}).")
    structure = json.loads(paths.GRAPH_STRUCTURE.read_text())
    calib = pd.read_parquet(paths.EDGE_CALIBRATION).set_index("station_id")
    pull = paths.find_pems_pull()

    edges_out = []
    n_default_vdf = 0
    for e in structure["edges"]:
        flags = list(e["flags"])
        if e["edge_type"] == "connector":
            vdf = {
                "t0_sec": _r(e["length_mi"] / config.CONNECTOR_SPEED_MPH * 3600),
                "capacity_vph": _r(
                    config.CONNECTOR_CAPACITY_VPHPL * config.CONNECTOR_LANES
                ),
                "alpha": config.BPR_ALPHA_DEFAULT,
                "beta": config.BPR_BETA_DEFAULT,
                "fit_method": "connector_default",
            }
            observed = None
            flags.append("default_vdf")
            n_default_vdf += 1
        else:
            sid = e["measurement_station"]
            if sid not in calib.index:
                # Station present in metadata but produced no readings.
                c = None
                flags += ["no_readings", "default_vdf", "thin_data"]
                n_default_vdf += 1
                vdf = {
                    "t0_sec": _r(
                        e["length_mi"] / config.FF_SPEED_DEFAULT_MPH * 3600
                    ),
                    "capacity_vph": _r(
                        config.CAPACITY_DEFAULT_VPHPL * e["lanes"]
                    ),
                    "alpha": config.BPR_ALPHA_DEFAULT,
                    "beta": config.BPR_BETA_DEFAULT,
                    "fit_method": "default",
                }
                observed = None
            else:
                c = calib.loc[sid]
                if c["ffs_method"] == "default":
                    flags.append("default_ffs")
                if c["capacity_method"] == "default":
                    flags.append("default_capacity")
                if c["bpr_method"] == "default":
                    flags.append("default_bpr")
                if bool(c["thin_station"]):
                    flags.append("thin_data")
                vdf = {
                    "t0_sec": _r(e["length_mi"] / c["ffs_mph"] * 3600),
                    "capacity_vph": _r(c["capacity_vphpl"] * e["lanes"]),
                    "alpha": _r(c["bpr_alpha"]),
                    "beta": _r(c["bpr_beta"]),
                    "fit_method": str(c["bpr_method"]),
                }
                observed = {
                    "ffs_mph": _r(c["ffs_mph"]),
                    "flow_vph_p5": _r(c["flow_vph_p5"]) if pd.notna(c["flow_vph_p5"]) else None,
                    "flow_vph_p50": _r(c["flow_vph_p50"]) if pd.notna(c["flow_vph_p50"]) else None,
                    "flow_vph_p95": _r(c["flow_vph_p95"]) if pd.notna(c["flow_vph_p95"]) else None,
                    "flow_vph_am_peak": _r(c["flow_vph_am_peak"]) if pd.notna(c["flow_vph_am_peak"]) else None,
                    "flow_vph_pm_peak": _r(c["flow_vph_pm_peak"]) if pd.notna(c["flow_vph_pm_peak"]) else None,
                    "n_days": int(c["n_days"]),
                    "coverage": _r(c["coverage"]),
                    "bpr_n_points": int(c["bpr_n_points"]),
                }
        edges_out.append(
            {
                "id": e["id"],
                "from": e["from"],
                "to": e["to"],
                "edge_type": e["edge_type"],
                "fwy": e["fwy"],
                "direction": e["direction"],
                "length_mi": e["length_mi"],
                "lanes": e["lanes"],
                "vdf": vdf,
                "observed": observed,
                "flags": sorted(set(flags)),
            }
        )

    artifact = {
        "meta": {
            "name": "Bay Area freeway network, calibrated (Phase 1)",
            "pems_pull": pull.name,
            "scope": {
                "district": config.DISTRICT,
                "routes": list(config.SCOPED_ROUTES),
                "lane_types": list(config.MAINLINE_TYPES),
            },
            "vdf_form": "t = t0 * (1 + alpha * (v/c)^beta)  [BPR]",
            "units": {
                "t0_sec": "seconds", "capacity_vph": "veh/hr (all lanes)",
                "length_mi": "miles", "flow_vph_*": "veh/hr (all lanes)",
                "ffs_mph": "miles/hr",
            },
            "counts": {
                "nodes": len(structure["nodes"]),
                "edges": len(edges_out),
                "edges_default_vdf": n_default_vdf,
            },
            "diagnostics": structure["diagnostics"],
            "schema": "artifacts/SCHEMA.md",
            "provenance": "PROVENANCE.md",
        },
        "nodes": structure["nodes"],
        "edges": edges_out,
    }
    config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    paths.NETWORK_GRAPH.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n"
    )
    print(
        f"[emit] {len(structure['nodes'])} nodes, {len(edges_out)} edges "
        f"({n_default_vdf} on default VDFs) -> {paths.NETWORK_GRAPH}"
    )
