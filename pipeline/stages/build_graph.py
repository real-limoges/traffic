"""Stage: build_graph — stations + topology -> graph_structure.json.

The routable graph, before calibration:

Nodes = scoped mainline detector stations, id "S<station_id>".
Mainline edges = consecutive stations along each (freeway, direction)
chain, ordered by absolute postmile. Direction orientation follows the
Caltrans postmile convention: postmiles increase generally south->north
and west->east, so N/E chains run in increasing Abs_PM and S/W chains in
decreasing Abs_PM (SCHEMA.md "Chain orientation"). Edge length = |ΔAbs_PM|
in miles. Gaps longer than config.MAX_SEGMENT_GAP_MI still get an edge
(the road exists) but carry a "long_gap" flag: calibration there is
extrapolation across a detector desert.

Interchanges (SCHEMA.md "Interchange detection"): each topology crossing
is anchored, per involved route and direction, to the NEAREST station
node on that chain (within config.INTERCHANGE_SNAP_MI * SNAP_SLACK).
Connector edges are then added between the anchored nodes of the two
routes, one per direction-pair movement, flagged connectivity_assumed —
SHN lines cannot say which ramp movements physically exist, so all
movements are included and Phase 2 must treat pruning as fair game.
Anchoring to the nearest detector rather than splicing an exact gore
point keeps edge granularity uniform (inter-detector spacing) at the cost
of placing connectors up to ~1 detector-spacing from the true ramp.
"""

import json
import math

import pandas as pd

from .. import config, paths

MI_PER_DEG_LAT = 69.0
SNAP_SLACK = 3.0  # nearest-station anchor may be this x snap radius away

INCREASING_DIRS = ("N", "E")
DECREASING_DIRS = ("S", "W")


def _dist_mi(lon1, lat1, lon2, lat2) -> float:
    lat = (lat1 + lat2) / 2.0
    dx = (lon1 - lon2) * 69.17 * math.cos(math.radians(lat))
    dy = (lat1 - lat2) * MI_PER_DEG_LAT
    return math.hypot(dx, dy)


def _chains(stations: pd.DataFrame) -> dict[tuple[int, str], pd.DataFrame]:
    chains = {}
    for (fwy, direction), grp in stations.groupby(["fwy", "direction"], sort=True):
        ascending = direction in INCREASING_DIRS
        if not ascending and direction not in DECREASING_DIRS:
            raise ValueError(f"Unexpected direction code {direction!r} on Fwy {fwy}")
        chains[(int(fwy), str(direction))] = grp.sort_values(
            "abs_pm", ascending=ascending
        ).reset_index(drop=True)
    return chains


def run() -> None:
    if not paths.STATIONS.exists():
        raise FileNotFoundError("Run ingest_metadata first (no stations.parquet).")
    if not paths.TOPOLOGY.exists():
        raise FileNotFoundError("Run ingest_topology first (no topology.json).")
    stations = pd.read_parquet(paths.STATIONS)
    topology = json.loads(paths.TOPOLOGY.read_text())

    nodes = {}
    for row in stations.sort_values("station_id").itertuples():
        nodes[f"S{row.station_id}"] = {
            "id": f"S{row.station_id}",
            "type": "station",
            "station_id": int(row.station_id),
            "fwy": int(row.fwy),
            "direction": row.direction,
            "abs_pm": round(float(row.abs_pm), 3),
            "lat": round(float(row.lat), config.ARTIFACT_COORD_DP),
            "lon": round(float(row.lon), config.ARTIFACT_COORD_DP),
            "lanes": int(row.lanes),
            "name": str(row.name),
        }

    edges = []
    n_long_gap = 0
    chains = _chains(stations)
    for (fwy, direction), chain in sorted(chains.items()):
        for i in range(len(chain) - 1):
            a, b = chain.iloc[i], chain.iloc[i + 1]
            length = abs(float(b.abs_pm) - float(a.abs_pm))
            if length <= 0:
                continue  # identical postmiles were deduped upstream
            flags = []
            if length > config.MAX_SEGMENT_GAP_MI:
                flags.append("long_gap")
                n_long_gap += 1
            edges.append(
                {
                    "id": f"ML_{fwy}{direction}_{int(a.station_id)}_{int(b.station_id)}",
                    "from": f"S{int(a.station_id)}",
                    "to": f"S{int(b.station_id)}",
                    "edge_type": "mainline",
                    "fwy": fwy,
                    "direction": direction,
                    "length_mi": round(length, 3),
                    "lanes": int(a.lanes),
                    "measurement_station": int(a.station_id),
                    "flags": flags,
                }
            )

    # ---- connectors at detected crossings -------------------------------
    unanchored = []
    connectors = []
    for crossing in topology["crossings"]:
        ra, rb = crossing["routes"]
        lon, lat = crossing["lon"], crossing["lat"]
        anchors = {}  # (route, direction) -> (node_id, dist)
        for route in (ra, rb):
            for (fwy, direction), chain in chains.items():
                if fwy != route:
                    continue
                d = chain.apply(
                    lambda r: _dist_mi(lon, lat, float(r.lon), float(r.lat)),
                    axis=1,
                )
                j = int(d.idxmin())
                if d[j] <= config.INTERCHANGE_SNAP_MI * SNAP_SLACK:
                    anchors[(fwy, direction)] = (
                        f"S{int(chain.iloc[j].station_id)}",
                        float(d[j]),
                    )
        got_a = any(k[0] == ra for k in anchors)
        got_b = any(k[0] == rb for k in anchors)
        if not (got_a and got_b):
            unanchored.append(crossing["id"])
            continue
        for (fa, da), (na, _) in sorted(anchors.items()):
            for (fb, db), (nb, _) in sorted(anchors.items()):
                if fa == fb or na == nb:
                    continue
                connectors.append(
                    {
                        "id": f"CN_{crossing['id']}_{na}_{nb}",
                        "from": na,
                        "to": nb,
                        "edge_type": "connector",
                        "crossing": crossing["id"],
                        "fwy": None,
                        "direction": f"{fa}{da}->{fb}{db}",
                        "length_mi": config.CONNECTOR_LENGTH_MI,
                        "lanes": config.CONNECTOR_LANES,
                        "measurement_station": None,
                        "flags": ["connectivity_assumed"],
                    }
                )

    # The same (from,to) pair can arise from two nearby crossings; keep one.
    seen = set()
    deduped = []
    for c in sorted(connectors, key=lambda c: c["id"]):
        key = (c["from"], c["to"])
        if key not in seen:
            seen.add(key)
            deduped.append(c)
    edges.extend(deduped)

    out = {
        "nodes": [nodes[k] for k in sorted(nodes)],
        "edges": sorted(edges, key=lambda e: e["id"]),
        "diagnostics": {
            "n_stations": len(nodes),
            "n_mainline_edges": sum(1 for e in edges if e["edge_type"] == "mainline"),
            "n_connector_edges": len(deduped),
            "n_long_gap_edges": n_long_gap,
            "crossings_total": len(topology["crossings"]),
            "crossings_unanchored": sorted(unanchored),
        },
    }
    paths.GRAPH_STRUCTURE.write_text(json.dumps(out, indent=2, sort_keys=True))

    # Connectivity check — report, don't fail: Phase 2 needs to know.
    try:
        import networkx as nx

        g = nx.DiGraph()
        g.add_nodes_from(nodes)
        g.add_edges_from((e["from"], e["to"]) for e in edges)
        n_weak = nx.number_weakly_connected_components(g)
        largest_strong = max(
            (len(c) for c in nx.strongly_connected_components(g)), default=0
        )
        print(
            f"[build_graph] connectivity: {n_weak} weakly connected "
            f"component(s); largest strongly connected component = "
            f"{largest_strong}/{len(nodes)} nodes"
        )
    except ImportError:
        print("[build_graph] networkx unavailable; connectivity not checked")

    d = out["diagnostics"]
    print(
        f"[build_graph] {d['n_stations']} nodes, {d['n_mainline_edges']} "
        f"mainline edges ({d['n_long_gap_edges']} long-gap), "
        f"{d['n_connector_edges']} connectors from {d['crossings_total']} "
        f"crossings ({len(d['crossings_unanchored'])} unanchored) "
        f"-> {paths.GRAPH_STRUCTURE.name}"
    )
