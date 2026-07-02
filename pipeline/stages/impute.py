"""Stage: impute — readings_clean -> readings_final.

Fills short gaps only: runs of at most config.MAX_IMPUTE_GAP_INTERVALS
consecutive invalid/missing 5-minute intervals, within a single station
and calendar day, by linear interpolation of flow, occupancy and speed
between the valid neighbors. Longer gaps stay missing — inventing an hour
of traffic is fiction, not imputation (SCHEMA.md "Imputation").

Every imputed row carries imputed=True. Downstream, imputed rows count for
15-minute rolling flow aggregation (they keep short dropouts from
shattering sustained-rate windows) but are excluded from free-flow-speed
estimation and from the BPR fit, which use measurements only.
"""

import numpy as np
import pandas as pd

from .. import config, paths

VALUE_COLS = ["flow_veh_5min", "occupancy", "speed_mph"]


def _impute_day(day: pd.DataFrame) -> pd.DataFrame:
    """Reindex one station-day to the full 5-min grid and fill short gaps."""
    day = day.set_index("timestamp").sort_index()
    d0 = day.index[0].normalize()
    grid = pd.date_range(d0, d0 + pd.Timedelta(days=1), freq="5min",
                         inclusive="left")
    day = day.reindex(grid)
    day.index.name = "timestamp"

    ok = day["valid"].fillna(False).astype(bool)
    # Invalidate the values on not-ok rows so interpolation can't lean on
    # implausible or PeMS-imputed numbers.
    day.loc[~ok, VALUE_COLS] = np.nan

    gap_id = ok.cumsum()                       # constant within a gap run
    gap_len = (~ok).groupby(gap_id).transform("sum")
    fillable = ~ok & (gap_len <= config.MAX_IMPUTE_GAP_INTERVALS)

    interp = day[VALUE_COLS].interpolate(
        method="linear", limit_area="inside"
    )
    for col in VALUE_COLS:
        day.loc[fillable, col] = interp.loc[fillable, col]

    day["imputed"] = False
    day.loc[fillable & day[VALUE_COLS].notna().all(axis=1), "imputed"] = True
    day["valid"] = ok | day["imputed"]
    day["invalid_reason"] = day["invalid_reason"].fillna("missing")
    day.loc[day["valid"], "invalid_reason"] = ""
    return day.reset_index()


def run() -> None:
    if not paths.READINGS_CLEAN.exists():
        raise FileNotFoundError("Run quality_filter first (no readings_clean.parquet).")
    df = pd.read_parquet(paths.READINGS_CLEAN)
    df["date"] = df["timestamp"].dt.date

    pieces = []
    for (sid, _), day in df.groupby(["station_id", "date"], sort=True):
        filled = _impute_day(day.drop(columns=["date"]))
        filled["station_id"] = sid
        pieces.append(filled)

    out = pd.concat(pieces, ignore_index=True)
    out = out[
        ["timestamp", "station_id", "samples", "pct_observed",
         "flow_veh_5min", "occupancy", "speed_mph", "valid",
         "invalid_reason", "imputed"]
    ].sort_values(["station_id", "timestamp"]).reset_index(drop=True)
    out.to_parquet(paths.READINGS_FINAL, index=False)

    n_imp = int(out["imputed"].sum())
    print(
        f"[impute] {len(out)} rows on full 5-min grids, {n_imp} imputed "
        f"(gaps <= {config.MAX_IMPUTE_GAP_INTERVALS} intervals) "
        f"-> {paths.READINGS_FINAL.name}"
    )
