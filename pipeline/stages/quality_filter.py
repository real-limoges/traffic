"""Stage: quality_filter — readings_raw -> readings_clean + quality_report.

Each rule below is a named, individually-auditable decision; SCHEMA.md
points here. Rows are never deleted for quality reasons — they are marked
`valid=False` with a reason, so the report can say exactly what was
excluded and why. Whole station-days and whole stations can be dropped
(rules D and E), and those ARE removed from the output, but counted first.

Rules (in order):
  A `pems_imputed`   pct_observed < config.MIN_PCT_OBSERVED, or samples==0.
                     Below the threshold the value is mostly PeMS's own
                     imputation model, not a measurement.
  B `missing`        flow, occupancy or speed is null.
  C `implausible`    speed outside (MIN_SPEED_MPH, MAX_SPEED_MPH),
                     occupancy > MAX_OCCUPANCY, or per-lane 5-min flow
                     above MAX_FLOW_PER_LANE_5MIN.
  D `dead_day`       station-days with < MIN_VALID_FRACTION_PER_DAY of
                     intervals valid are dropped whole: a mostly-dead day
                     indicts the detector, not the traffic.
  E `thin_station`   stations left with < MIN_CALIBRATION_DAYS days are
                     flagged in the report (their edges will use default
                     VDFs); their rows are kept for flow statistics.
"""

import json

import pandas as pd

from .. import config, paths


def run() -> None:
    if not paths.READINGS_RAW.exists():
        raise FileNotFoundError("Run ingest_readings first (no readings_raw.parquet).")
    df = pd.read_parquet(paths.READINGS_RAW)
    stations = pd.read_parquet(paths.STATIONS)[["station_id", "lanes"]]
    df = df.merge(stations, on="station_id", how="left", validate="m:1")

    n_total = len(df)
    reason = pd.Series("", index=df.index)

    # Rule A — PeMS-imputed values are not measurements.
    a = (df["pct_observed"].fillna(0) < config.MIN_PCT_OBSERVED) | (
        df["samples"].fillna(0) <= 0
    )
    reason[a] = "pems_imputed"

    # Rule B — outright missing.
    b = (
        df["flow_veh_5min"].isna()
        | df["occupancy"].isna()
        | df["speed_mph"].isna()
    ) & ~a
    reason[b] = "missing"

    # Rule C — physically implausible.
    per_lane_flow = df["flow_veh_5min"] / df["lanes"].clip(lower=1)
    c = (
        (df["speed_mph"] > config.MAX_SPEED_MPH)
        | (df["speed_mph"] < config.MIN_SPEED_MPH)
        | (df["occupancy"] > config.MAX_OCCUPANCY)
        | (per_lane_flow > config.MAX_FLOW_PER_LANE_5MIN)
    ) & ~a & ~b
    reason[c] = "implausible"

    df["valid"] = reason == ""
    df["invalid_reason"] = reason
    df["date"] = df["timestamp"].dt.date

    # Rule D — drop whole dead station-days.
    day_valid = df.groupby(["station_id", "date"])["valid"].mean()
    dead = day_valid[day_valid < config.MIN_VALID_FRACTION_PER_DAY]
    dead_index = pd.MultiIndex.from_frame(dead.reset_index()[["station_id", "date"]])
    row_key = pd.MultiIndex.from_frame(df[["station_id", "date"]])
    is_dead_day = row_key.isin(dead_index)
    n_dead_day_rows = int(is_dead_day.sum())
    df = df[~is_dead_day].copy()

    # Rule E — stations too thin to calibrate (reported, not removed).
    days_per_station = df[df["valid"]].groupby("station_id")["date"].nunique()
    thin = sorted(
        int(s) for s in days_per_station[
            days_per_station < config.MIN_CALIBRATION_DAYS
        ].index
    )
    # Stations with zero valid rows disappear from days_per_station; they
    # are equally uncalibratable and must be counted too.
    all_ids = set(int(s) for s in stations["station_id"])
    seen_ids = set(int(s) for s in days_per_station.index)
    silent = sorted(all_ids - seen_ids)

    report = {
        "rows_in": n_total,
        "rows_out": len(df),
        "invalid_by_reason": {
            k: int(v)
            for k, v in df["invalid_reason"].value_counts().items()
            if k
        },
        "dead_station_day_rows_dropped": n_dead_day_rows,
        "dead_station_days": int(len(dead)),
        "thin_stations_lt_min_days": thin,
        "stations_with_no_valid_data": silent,
        "thresholds": {
            "MIN_PCT_OBSERVED": config.MIN_PCT_OBSERVED,
            "MIN_VALID_FRACTION_PER_DAY": config.MIN_VALID_FRACTION_PER_DAY,
            "MIN_CALIBRATION_DAYS": config.MIN_CALIBRATION_DAYS,
        },
    }

    out = df.drop(columns=["date", "lanes"]).reset_index(drop=True)
    out.to_parquet(paths.READINGS_CLEAN, index=False)
    paths.QUALITY_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"[quality_filter] {n_total} rows in, {len(out)} out; invalid "
        f"marked: {report['invalid_by_reason']}; dead station-days: "
        f"{report['dead_station_days']}; thin stations: {len(thin)}; "
        f"silent stations: {len(silent)} -> {paths.READINGS_CLEAN.name}, "
        f"{paths.QUALITY_REPORT.name}"
    )
