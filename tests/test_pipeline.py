"""End-to-end pipeline tests on the synthetic PeMS-format fixture.

These prove the MECHANICS: format parsing, scope filtering, quality rules,
imputation, graph structure, interchange connectors, ground-truth VDF
recovery, artifact determinism. They say nothing about the real Bay Area
network — that requires the real PeMS pull (see PROVENANCE.md).
"""

import json

import pandas as pd
import pytest

from pipeline import config, paths
from pipeline.stages import (
    build_graph, calibrate, emit, impute,
    ingest_metadata, ingest_readings, ingest_topology, quality_filter,
)
from tests.fixtures.make_fixture import (
    DEAD_DAY_STATION, GAP_STATION, STATIONS, THIN_STATION, TRUTH,
    write_fixture,
)

PROCESSED_FILES = {
    "STATIONS": "stations.parquet",
    "READINGS_RAW": "readings_raw.parquet",
    "READINGS_CLEAN": "readings_clean.parquet",
    "QUALITY_REPORT": "quality_report.json",
    "READINGS_FINAL": "readings_final.parquet",
    "TOPOLOGY": "topology.json",
    "GRAPH_STRUCTURE": "graph_structure.json",
    "EDGE_CALIBRATION": "edge_calibration.parquet",
}


@pytest.fixture(scope="module")
def pipeline_run(tmp_path_factory):
    """Run the full pipeline once on the fixture; yield output locations."""
    tmp = tmp_path_factory.mktemp("fixture-run")
    raw, proc, art = tmp / "data/raw", tmp / "data/processed", tmp / "artifacts"
    write_fixture(raw)

    mp = pytest.MonkeyPatch()
    mp.setattr(config, "RAW_DIR", raw)
    mp.setattr(config, "PROCESSED_DIR", proc)
    mp.setattr(config, "ARTIFACTS_DIR", art)
    for name, fname in PROCESSED_FILES.items():
        mp.setattr(paths, name, proc / fname)
    mp.setattr(paths, "NETWORK_GRAPH", art / "network_graph.json")

    for stage in (ingest_metadata, ingest_readings, quality_filter, impute,
                  ingest_topology, build_graph, calibrate, emit):
        stage.run()
    yield {"raw": raw, "proc": proc, "art": art}
    mp.undo()


def _artifact(run):
    return json.loads((run["art"] / "network_graph.json").read_text())


def test_scope_filter_and_dedup(pipeline_run):
    stations = pd.read_parquet(pipeline_run["proc"] / "stations.parquet")
    ids = set(stations["station_id"])
    assert {900001, 900002, 900003}.isdisjoint(ids), "out-of-scope rows leaked"
    assert 900004 not in ids, "duplicate-postmile station not collapsed"
    assert ids == {s[0] for s in STATIONS}


def test_quality_rules_fired(pipeline_run):
    report = json.loads((pipeline_run["proc"] / "quality_report.json").read_text())
    assert report["invalid_by_reason"].get("pems_imputed", 0) > 0
    assert report["invalid_by_reason"].get("implausible", 0) > 0
    assert report["dead_station_days"] >= 1
    assert THIN_STATION in report["thin_stations_lt_min_days"]

    clean = pd.read_parquet(pipeline_run["proc"] / "readings_clean.parquet")
    dead = clean[clean["station_id"] == DEAD_DAY_STATION]
    assert dead["timestamp"].dt.date.nunique() == 11, "dead day not dropped"


def test_imputation_short_gaps_only(pipeline_run):
    final = pd.read_parquet(pipeline_run["proc"] / "readings_final.parquet")
    g = final[final["station_id"] == GAP_STATION].set_index("timestamp")
    day = g[g.index.date.astype(str) == "2026-05-06"]
    short_gap = day.iloc[100:102]
    long_gap = day.iloc[150:160]
    assert short_gap["imputed"].all(), "2-interval gap should be imputed"
    assert short_gap["flow_veh_5min"].notna().all()
    assert not long_gap["imputed"].any(), "10-interval gap must NOT be imputed"
    assert long_gap["flow_veh_5min"].isna().all()


def test_graph_structure(pipeline_run):
    art = _artifact(pipeline_run)
    nodes = {n["id"]: n for n in art["nodes"]}
    edges = art["edges"]
    assert len(nodes) == len(STATIONS)
    ml = [e for e in edges if e["edge_type"] == "mainline"]
    # 4 chains x (4 stations - 1) edges
    assert len(ml) == 4 * 3
    # Chain orientation: E chains ascend postmile, W descend.
    for e in ml:
        a, b = nodes[e["from"]], nodes[e["to"]]
        if e["direction"] in ("E", "N"):
            assert b["abs_pm"] > a["abs_pm"]
        else:
            assert b["abs_pm"] < a["abs_pm"]
    cn = [e for e in edges if e["edge_type"] == "connector"]
    # 2 dirs x 2 dirs x 2 transfer orders = 8 movements at the crossing
    assert len(cn) == 8
    assert all("connectivity_assumed" in e["flags"] for e in cn)
    # Connectors anchor at the stations nearest the crossing point.
    for e in cn:
        for nid in (e["from"], e["to"]):
            n = nodes[nid]
            assert abs(n["abs_pm"] - (2.0 if n["fwy"] == 80 else 11.0)) < 0.6


def test_calibration_recovers_ground_truth(pipeline_run):
    art = _artifact(pipeline_run)
    good = [
        e for e in art["edges"]
        if e["edge_type"] == "mainline" and e["vdf"]["fit_method"] == "fitted"
        and not set(e["flags"]) & {"thin_data", "default_ffs", "default_capacity"}
    ]
    assert len(good) >= 6, "most healthy edges should get a real BPR fit"
    for e in good:
        obs = e["observed"]
        assert abs(obs["ffs_mph"] - TRUTH["ffs_mph"]) < 3.0
        cap_pl = e["vdf"]["capacity_vph"] / e["lanes"]
        assert abs(cap_pl - TRUTH["capacity_vphpl"]) / TRUTH["capacity_vphpl"] < 0.15
        assert abs(e["vdf"]["beta"] - TRUTH["beta"]) < 1.0
        assert 0.5 * TRUTH["alpha"] < e["vdf"]["alpha"] < 2.0 * TRUTH["alpha"]
        # Observed flow ranges present and ordered.
        assert obs["flow_vph_p5"] <= obs["flow_vph_p50"] <= obs["flow_vph_p95"]


def test_fallbacks_are_flagged(pipeline_run):
    art = _artifact(pipeline_run)
    thin_edges = [
        e for e in art["edges"]
        if e["edge_type"] == "mainline"
        and e["id"].startswith(f"ML_80E_{THIN_STATION}_")
    ]
    # The thin station feeds one edge; it must be defaulted and flagged.
    assert thin_edges, "edge measured by thin station missing"
    for e in thin_edges:
        assert "thin_data" in e["flags"]
        assert e["vdf"]["fit_method"] == "default"


def test_artifact_units_and_consistency(pipeline_run):
    art = _artifact(pipeline_run)
    for e in art["edges"]:
        v = e["vdf"]
        assert v["t0_sec"] > 0 and v["capacity_vph"] > 0
        assert 0 < v["alpha"] <= 1.5 and 1.0 <= v["beta"] <= 10.0
        if e["edge_type"] == "mainline" and e["observed"]:
            implied_ffs = e["length_mi"] / (v["t0_sec"] / 3600.0)
            assert abs(implied_ffs - e["observed"]["ffs_mph"]) < 0.5
    counts = art["meta"]["counts"]
    assert counts["nodes"] == len(art["nodes"])
    assert counts["edges"] == len(art["edges"])


def test_determinism(pipeline_run):
    first = (pipeline_run["art"] / "network_graph.json").read_bytes()
    for stage in (quality_filter, impute, build_graph, calibrate, emit):
        stage.run()
    second = (pipeline_run["art"] / "network_graph.json").read_bytes()
    assert first == second, "artifact must be byte-identical on re-run"
