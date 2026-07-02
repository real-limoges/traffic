"""Stage: calibrate — readings_final -> edge_calibration.parquet.

Per-station volume-delay calibration; emit() later attaches each mainline
edge's parameters from its measurement (from-) station. Three estimates
per station, each with an explicit fallback and a method flag so the
artifact never hides which numbers are measured and which are defaults:

Free-flow speed (SCHEMA.md "Free-flow speed"):
  median speed over non-imputed valid intervals in the night window
  config.FF_HOURS with occupancy < FF_OCC_MAX, clamped to
  FF_SPEED_CLAMP_MPH. Fewer than FF_MIN_OBS usable intervals ->
  FF_SPEED_DEFAULT_MPH, method "default".

Practical capacity per lane (SCHEMA.md "Capacity"):
  CAPACITY_PERCENTILE of sustained 15-minute flow rates (rolling
  ROLLING_INTERVALS x 5-min windows with >= ROLLING_MIN_VALID valid
  intervals, scaled to veh/hr/lane), clamped to CAPACITY_CLAMP_VPHPL.
  No usable windows -> CAPACITY_DEFAULT_VPHPL, method "default".

BPR alpha/beta (SCHEMA.md "BPR fit"):
  t/t0 = 1 + alpha*(v/c)^beta  =>  log(t/t0 - 1) = log(alpha) + beta*log(v/c)
  ordinary least squares in log space over congested 15-min points
  (t/t0 > BPR_FIT_MIN_RATIO, v/c > BPR_FIT_MIN_VC, non-imputed).
  Fewer than BPR_FIT_MIN_POINTS points, or a fit outside
  BPR_ALPHA_BOUNDS/BPR_BETA_BOUNDS, falls back to the canonical
  (0.15, 4.0), method "default". Deterministic: numpy lstsq, no seeds.

Observed flow ranges: 5th/50th/95th percentile of hourly-scaled station
flow over valid intervals, plus AM (7-9) / PM (16-18) weekday peak means —
Phase 2's reality check material.
"""

import numpy as np
import pandas as pd

from .. import config, paths


def _ff_speed(grp: pd.DataFrame) -> tuple[float, str, int]:
    obs = grp[
        grp["valid"] & ~grp["imputed"]
        & grp["timestamp"].dt.hour.isin(config.FF_HOURS)
        & (grp["occupancy"] < config.FF_OCC_MAX)
    ]["speed_mph"].dropna()
    if len(obs) < config.FF_MIN_OBS:
        return config.FF_SPEED_DEFAULT_MPH, "default", int(len(obs))
    lo, hi = config.FF_SPEED_CLAMP_MPH
    return float(np.clip(obs.median(), lo, hi)), "observed", int(len(obs))


def _sustained_rates(grp: pd.DataFrame) -> pd.DataFrame:
    """15-min sustained rates: veh/hr (station) + mean speed, per window."""
    g = grp.set_index("timestamp").sort_index()
    flow = g["flow_veh_5min"].where(g["valid"])
    speed = g["speed_mph"].where(g["valid"])
    measured = g["valid"] & ~g["imputed"]
    n_valid = flow.notna().rolling(config.ROLLING_INTERVALS).sum()
    out = pd.DataFrame(
        {
            "flow_vph": flow.rolling(config.ROLLING_INTERVALS, min_periods=1)
            .mean() * 12.0,
            "speed_mph": speed.rolling(config.ROLLING_INTERVALS, min_periods=1)
            .mean(),
            "all_measured": measured.rolling(config.ROLLING_INTERVALS)
            .min().fillna(0).astype(bool),
        }
    )
    return out[n_valid >= config.ROLLING_MIN_VALID].dropna(
        subset=["flow_vph", "speed_mph"]
    )


def _capacity(rates: pd.DataFrame, lanes: int) -> tuple[float, str, int]:
    if rates.empty:
        return config.CAPACITY_DEFAULT_VPHPL, "default", 0
    per_lane = rates["flow_vph"] / max(lanes, 1)
    cap = float(np.percentile(per_lane, config.CAPACITY_PERCENTILE))
    lo, hi = config.CAPACITY_CLAMP_VPHPL
    return float(np.clip(cap, lo, hi)), "observed", int(len(per_lane))


def _bpr_fit(rates: pd.DataFrame, ffs: float, cap_vphpl: float,
             lanes: int) -> tuple[float, float, str, int]:
    pts = rates[rates["all_measured"]].copy()
    pts = pts[pts["speed_mph"] > 0]
    ratio = ffs / pts["speed_mph"]          # t/t0 = ffs/speed for fixed length
    vc = pts["flow_vph"] / (cap_vphpl * max(lanes, 1))
    keep = (ratio > config.BPR_FIT_MIN_RATIO) & (vc > config.BPR_FIT_MIN_VC)
    ratio, vc = ratio[keep], vc[keep]
    n = int(len(ratio))
    if n < config.BPR_FIT_MIN_POINTS:
        return config.BPR_ALPHA_DEFAULT, config.BPR_BETA_DEFAULT, "default", n
    y = np.log(ratio.values - 1.0)
    x = np.log(vc.values)
    A = np.column_stack([np.ones_like(x), x])
    (log_alpha, beta), *_ = np.linalg.lstsq(A, y, rcond=None)
    alpha = float(np.exp(log_alpha))
    beta = float(beta)
    a_lo, a_hi = config.BPR_ALPHA_BOUNDS
    b_lo, b_hi = config.BPR_BETA_BOUNDS
    if not (a_lo <= alpha <= a_hi and b_lo <= beta <= b_hi):
        return config.BPR_ALPHA_DEFAULT, config.BPR_BETA_DEFAULT, "default", n
    return alpha, beta, "fitted", n


def run() -> None:
    if not paths.READINGS_FINAL.exists():
        raise FileNotFoundError("Run impute first (no readings_final.parquet).")
    readings = pd.read_parquet(paths.READINGS_FINAL)
    stations = pd.read_parquet(paths.STATIONS)
    lanes_by_station = dict(
        zip(stations["station_id"].astype(int), stations["lanes"].astype(int))
    )

    rows = []
    for sid, grp in readings.groupby("station_id", sort=True):
        sid = int(sid)
        lanes = lanes_by_station.get(sid, 1)
        valid = grp[grp["valid"]]
        n_days = valid["timestamp"].dt.date.nunique()

        ffs, ffs_method, ffs_n = _ff_speed(grp)
        rates = _sustained_rates(grp)
        cap, cap_method, cap_n = _capacity(rates, lanes)
        thin = n_days < config.MIN_CALIBRATION_DAYS
        if thin:
            # Too little data to trust station-specific estimates at all.
            ffs, ffs_method = config.FF_SPEED_DEFAULT_MPH, "default"
            cap, cap_method = config.CAPACITY_DEFAULT_VPHPL, "default"
            alpha, beta, fit_method, fit_n = (
                config.BPR_ALPHA_DEFAULT, config.BPR_BETA_DEFAULT, "default", 0,
            )
        else:
            alpha, beta, fit_method, fit_n = _bpr_fit(rates, ffs, cap, lanes)

        hourly = valid["flow_veh_5min"].dropna() * 12.0
        weekday = valid[valid["timestamp"].dt.dayofweek < 5]
        am = weekday[weekday["timestamp"].dt.hour.isin((7, 8))]
        pm = weekday[weekday["timestamp"].dt.hour.isin((16, 17))]
        rows.append(
            {
                "station_id": sid,
                "lanes": lanes,
                "n_days": int(n_days),
                "coverage": float(len(valid)) / max(len(grp), 1),
                "thin_station": bool(thin),
                "ffs_mph": ffs, "ffs_method": ffs_method, "ffs_n_obs": ffs_n,
                "capacity_vphpl": cap, "capacity_method": cap_method,
                "capacity_n_windows": cap_n,
                "bpr_alpha": alpha, "bpr_beta": beta,
                "bpr_method": fit_method, "bpr_n_points": fit_n,
                "flow_vph_p5": float(np.percentile(hourly, 5)) if len(hourly) else np.nan,
                "flow_vph_p50": float(np.percentile(hourly, 50)) if len(hourly) else np.nan,
                "flow_vph_p95": float(np.percentile(hourly, 95)) if len(hourly) else np.nan,
                "flow_vph_am_peak": float(am["flow_veh_5min"].mean() * 12.0) if len(am) else np.nan,
                "flow_vph_pm_peak": float(pm["flow_veh_5min"].mean() * 12.0) if len(pm) else np.nan,
            }
        )

    out = pd.DataFrame(rows).sort_values("station_id").reset_index(drop=True)
    out.to_parquet(paths.EDGE_CALIBRATION, index=False)
    n_fit = int((out["bpr_method"] == "fitted").sum())
    n_thin = int(out["thin_station"].sum())
    print(
        f"[calibrate] {len(out)} stations calibrated; BPR fitted for "
        f"{n_fit}, defaults for {len(out) - n_fit} (thin stations: {n_thin}) "
        f"-> {paths.EDGE_CALIBRATION.name}"
    )
