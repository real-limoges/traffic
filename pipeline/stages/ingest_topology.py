"""Stage: ingest_topology — SHN GeoJSON -> topology.json.

Input:  data/raw/caltrans-network-topology/shn_lines.geojson — the public
        Caltrans "State Highway Network Lines" layer. Field names vary a
        little between portal exports, so the route-number property is
        looked up from a candidate list rather than hard-coded.
Output: data/processed/topology.json with, per scoped route, a merged
        geometry, plus the crossing points between every pair of scoped
        routes (candidate interchange locations for build_graph).

Crossing detection (SCHEMA.md "Interchange detection"): shapely
intersection of the two routes' merged geometries. Intersections can be
points (a genuine crossing), line segments (route concurrencies, e.g. the
I-80/I-580 co-alignment in the East Bay — represented by their endpoints),
or clusters of near-duplicate points where carriageway lines cross
repeatedly. Representative points are clustered within CLUSTER_MI and
each cluster becomes one crossing, positioned at the cluster centroid.
Deterministic: points sorted before greedy clustering.
"""

import json
import math

from shapely.geometry import shape
from shapely.ops import unary_union

from .. import config, paths

ROUTE_PROP_CANDIDATES = ("Route", "ROUTE", "route", "RTE", "RteNum", "ROUTE_ID")
CLUSTER_MI = 2.0
MI_PER_DEG_LAT = 69.0


def _mi_per_deg_lon(lat: float) -> float:
    return 69.17 * math.cos(math.radians(lat))


def _dist_mi(p1, p2) -> float:
    lat = (p1[1] + p2[1]) / 2.0
    dx = (p1[0] - p2[0]) * _mi_per_deg_lon(lat)
    dy = (p1[1] - p2[1]) * MI_PER_DEG_LAT
    return math.hypot(dx, dy)


def _route_number(props: dict):
    for key in ROUTE_PROP_CANDIDATES:
        if key in props and props[key] is not None:
            try:
                return int(props[key])
            except (TypeError, ValueError):
                continue
    return None


def _representative_points(geom) -> list[tuple[float, float]]:
    """Points summarizing an intersection geometry (lon, lat)."""
    if geom.is_empty:
        return []
    gt = geom.geom_type
    if gt == "Point":
        return [(geom.x, geom.y)]
    if gt in ("LineString", "LinearRing"):
        c = list(geom.coords)
        return [c[0], c[-1]]
    if gt.startswith("Multi") or gt == "GeometryCollection":
        pts = []
        for g in geom.geoms:
            pts.extend(_representative_points(g))
        return pts
    return []


def _cluster(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Greedy deterministic clustering; returns cluster centroids."""
    pts = sorted(points)
    clusters: list[list[tuple[float, float]]] = []
    for p in pts:
        for cl in clusters:
            if any(_dist_mi(p, q) <= CLUSTER_MI for q in cl):
                cl.append(p)
                break
        else:
            clusters.append([p])
    return [
        (sum(p[0] for p in cl) / len(cl), sum(p[1] for p in cl) / len(cl))
        for cl in clusters
    ]


def run() -> None:
    topo_path = paths.topology_file()
    gj = json.loads(topo_path.read_text())
    feats = gj.get("features", [])
    if not feats:
        raise ValueError(f"{topo_path} contains no features.")

    by_route: dict[int, list] = {r: [] for r in config.SCOPED_ROUTES}
    n_matched = 0
    for feat in feats:
        rt = _route_number(feat.get("properties", {}) or {})
        if rt in by_route:
            by_route[rt].append(shape(feat["geometry"]))
            n_matched += 1
    missing = [r for r, geoms in by_route.items() if not geoms]
    if missing:
        raise ValueError(
            f"Topology file has no features for scoped route(s) {missing}. "
            f"Route property tried: {ROUTE_PROP_CANDIDATES}. Check the "
            "export includes the whole SHN Lines layer."
        )

    merged = {r: unary_union(geoms) for r, geoms in by_route.items()}

    crossings = []
    routes = sorted(merged)
    for i, ra in enumerate(routes):
        for rb in routes[i + 1:]:
            inter = merged[ra].intersection(merged[rb])
            pts = _cluster(_representative_points(inter))
            for k, (lon, lat) in enumerate(pts):
                crossings.append(
                    {
                        "id": f"X_{ra}_{rb}_{k}",
                        "routes": [ra, rb],
                        "lon": round(lon, config.ARTIFACT_COORD_DP),
                        "lat": round(lat, config.ARTIFACT_COORD_DP),
                    }
                )

    out = {
        "source_file": topo_path.name,
        "routes": {
            str(r): {
                "n_features": len(by_route[r]),
                "length_deg": round(merged[r].length, 6),
            }
            for r in routes
        },
        "crossings": crossings,
    }
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    paths.TOPOLOGY.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(
        f"[ingest_topology] {n_matched} features matched scoped routes; "
        f"{len(crossings)} route-pair crossings detected -> {paths.TOPOLOGY.name}"
    )
