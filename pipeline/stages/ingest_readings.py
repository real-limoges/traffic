"""Stage: ingest_readings — PeMS station_5min files -> readings_raw.parquet.

Input:  data/raw/pems-d04-*/d04_text_station_5min_YYYY_MM_DD.txt(.gz)
        Headerless CSV. First 12 columns (station-level aggregates):
        timestamp, station, district, freeway, direction, lane_type,
        station_length, samples, pct_observed, total_flow (veh/5min),
        avg_occupancy (fraction), avg_speed (mph). Per-lane columns follow;
        we ignore them — calibration works on the station aggregate.
Output: data/processed/readings_raw.parquet, restricted to stations in
        stations.parquet (so run ingest_metadata first).

Nothing is cleaned here beyond type coercion: this stage's contract is
"exactly what PeMS said, for the stations we care about". Quality rules
live in the quality_filter stage where they are individually auditable.
"""

import pandas as pd

from .. import config, paths

COLS = [
    "timestamp", "station_id", "district", "fwy", "direction", "lane_type",
    "station_length", "samples", "pct_observed", "flow_veh_5min",
    "occupancy", "speed_mph",
]


def run() -> None:
    if not paths.STATIONS.exists():
        raise FileNotFoundError("Run ingest_metadata first (no stations.parquet).")
    stations = pd.read_parquet(paths.STATIONS)
    keep_ids = set(stations["station_id"].tolist())

    pull = paths.find_pems_pull()
    files = paths.station_5min_files(pull)

    frames = []
    for f in files:
        df = pd.read_csv(
            f, header=None, usecols=range(12), names=COLS,
            compression="infer",
            dtype={
                "station_id": "int64", "district": "int64", "fwy": "int64",
                "direction": "str", "lane_type": "str",
            },
        )
        df = df[df["station_id"].isin(keep_ids)].copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="%m/%d/%Y %H:%M:%S")
        for col in ("samples", "pct_observed", "flow_veh_5min", "occupancy",
                    "speed_mph"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        frames.append(
            df[["timestamp", "station_id", "samples", "pct_observed",
                "flow_veh_5min", "occupancy", "speed_mph"]]
        )
        print(f"[ingest_readings] {f.name}: {len(df)} scoped rows")

    out = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["station_id", "timestamp"])
        .reset_index(drop=True)
    )
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(paths.READINGS_RAW, index=False)
    print(
        f"[ingest_readings] total {len(out)} rows, "
        f"{out['station_id'].nunique()} stations, "
        f"{out['timestamp'].dt.date.nunique()} days -> {paths.READINGS_RAW.name}"
    )
