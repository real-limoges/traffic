"""Synthetic PeMS-format fixture generator — TEST DATA ONLY.

Writes a miniature but format-faithful data/raw/ tree into a temp dir:
two freeways (80 E/W, 880 N/S) crossing once, with 5-min station data
generated from a KNOWN ground-truth BPR curve so tests can check that
calibration recovers what was planted. Injected defects exercise every
quality rule: PeMS-imputed intervals, nulls, implausible speeds, a dead
station-day, a thin station, a 2-interval gap (imputable) and a
10-interval gap (not).

Never writes under data/ in the repo. Synthetic output must never be
mistaken for a real PeMS pull — that is why this lives in tests/.
"""

import gzip
import json
import math
from pathlib import Path

import numpy as np

# Ground truth planted in the traffic generator; tests assert recovery.
TRUTH = {"ffs_mph": 65.0, "capacity_vphpl": 2000.0, "alpha": 0.30, "beta": 3.0}
LANES = 4
N_DAYS = 12
START = (2026, 5, 4)  # a Monday

# Station layout: (station_id, fwy, dir, abs_pm, lat, lon)
# Fwy 80 runs E-W along lat 37.80; fwy 880 runs N-S along lon -122.20.
# They cross at (37.80, -122.20) == abs_pm 2.0 on 80, 11.0 on 880.
def _stations():
    rows = []
    sid = 400000
    for direction in ("E", "W"):
        for i, pm in enumerate((0.0, 1.0, 2.0, 3.0)):
            rows.append((sid, 80, direction, pm, 37.80, -122.20 - (2.0 - pm) / 54.7))
            sid += 1
    for direction in ("N", "S"):
        for i, pm in enumerate((9.5, 10.5, 11.0, 12.0)):
            rows.append((sid, 880, direction, pm, 37.80 - (11.0 - pm) / 69.0, -122.20))
            sid += 1
    return rows


STATIONS = _stations()
THIN_STATION = STATIONS[1][0]        # 80 E, pm 1.0 -> only 2 days of data
                                     # (mid-chain, so it measures an edge)
DEAD_DAY_STATION = STATIONS[4][0]    # 80 W, pm 0.0 -> day 3 all nulls
GAP_STATION = STATIONS[5][0]         # 80 W, pm 1.0 -> gaps on day 2


def _vc_profile(interval: int) -> float:
    """Demand v/c over a day: quiet nights, 1.05 peak at 8:00 and 17:00."""
    h = interval / 12.0
    am = 1.00 * math.exp(-((h - 8.0) ** 2) / 4.5)
    pm = 1.05 * math.exp(-((h - 17.0) ** 2) / 4.5)
    return 0.05 + max(am, pm)


def write_fixture(raw_dir: Path) -> None:
    rng = np.random.RandomState(42)
    pull = raw_dir / "pems-d04-20260504-20260515"
    pull.mkdir(parents=True)
    topo_dir = raw_dir / "caltrans-network-topology"
    topo_dir.mkdir(parents=True)

    # --- station metadata (tab-separated, real header) -------------------
    header = ("ID\tFwy\tDir\tDistrict\tCounty\tCity\tState_PM\tAbs_PM\t"
              "Latitude\tLongitude\tLength\tType\tLanes\tName\tUser_ID_1")
    lines = [header]
    for sid, fwy, d, pm, lat, lon in STATIONS:
        lines.append(
            f"{sid}\t{fwy}\t{d}\t4\t1\t\t{pm:.3f}\t{pm:.3f}\t{lat:.6f}"
            f"\t{lon:.6f}\t0.5\tML\t{LANES}\tFIX {fwy}{d} PM{pm}\t"
        )
    # Out-of-scope rows the filter must drop:
    lines.append("900001\t24\tE\t4\t1\t\t1.0\t1.0\t37.83\t-122.22\t0.5\tML\t3\tOFFSCOPE FWY\t")
    lines.append("900002\t80\tE\t3\t1\t\t1.0\t1.0\t38.50\t-121.50\t0.5\tML\t3\tOFFSCOPE DISTRICT\t")
    lines.append("900003\t80\tE\t4\t1\t\t1.5\t1.5\t37.80\t-122.21\t0.5\tOR\t1\tOFFSCOPE RAMP\t")
    # Duplicate postmile (fewer lanes -> must lose the dedup):
    lines.append(f"900004\t80\tE\t4\t1\t\t0.0\t0.0\t37.80\t-122.2366\t0.5\tML\t2\tDUP PM\t")
    (pull / "d04_text_meta_2026_05_15.txt").write_text("\n".join(lines) + "\n")

    # --- 5-minute files, one per day -------------------------------------
    import datetime as dt

    day0 = dt.date(*START)
    truth_cap_station = TRUTH["capacity_vphpl"] * LANES
    for dnum in range(N_DAYS):
        day = day0 + dt.timedelta(days=dnum)
        rows = []
        for s_i, (sid, fwy, d, pm, lat, lon) in enumerate(STATIONS):
            if sid == THIN_STATION and dnum >= 2:
                continue  # thin station: only 2 days present
            for k in range(288):
                ts = f"{day.month:02d}/{day.day:02d}/{day.year} {k // 12:02d}:{(k % 12) * 5:02d}:00"
                vc = _vc_profile(k) * float(rng.normal(1.0, 0.03))
                vc = max(vc, 0.01)
                flow5 = truth_cap_station * vc / 12.0
                speed = TRUTH["ffs_mph"] / (
                    1.0 + TRUTH["alpha"] * vc ** TRUTH["beta"]
                ) * float(rng.normal(1.0, 0.01))
                occ = min(0.5, 0.05 * vc + 0.0005)
                pct, samples = 100, 40
                f_s, o_s, sp_s = f"{flow5:.0f}", f"{occ:.4f}", f"{speed:.1f}"
                if sid == DEAD_DAY_STATION and dnum == 3:
                    f_s = o_s = sp_s = ""      # dead day: all null
                    samples = 0
                elif sid == GAP_STATION and dnum == 2 and 100 <= k < 102:
                    f_s = o_s = sp_s = ""      # 2-interval gap -> imputable
                elif sid == GAP_STATION and dnum == 2 and 150 <= k < 160:
                    f_s = o_s = sp_s = ""      # 10-interval gap -> stays missing
                elif s_i == 6 and k % 97 == 0:
                    pct = 30                   # PeMS-imputed interval
                elif s_i == 2 and k == 140:
                    sp_s = "150.0"             # implausible speed
                rows.append(
                    f"{ts},{sid},4,{fwy},{d},ML,0.5,{samples},{pct},"
                    f"{f_s},{o_s},{sp_s},,,,,"
                )
        name = f"d04_text_station_5min_{day.year}_{day.month:02d}_{day.day:02d}.txt.gz"
        with gzip.open(pull / name, "wt") as fh:
            fh.write("\n".join(rows) + "\n")

    # --- topology GeoJSON -------------------------------------------------
    fwy80 = {
        "type": "Feature",
        "properties": {"Route": 80},
        "geometry": {"type": "LineString",
                     "coordinates": [[-122.2366, 37.80], [-122.1817, 37.80]]},
    }
    fwy880 = {
        "type": "Feature",
        "properties": {"Route": 880},
        "geometry": {"type": "LineString",
                     "coordinates": [[-122.20, 37.7783], [-122.20, 37.8145]]},
    }
    others = [
        {"type": "Feature", "properties": {"Route": r},
         "geometry": {"type": "LineString",
                      "coordinates": [[-121.0 - i, 38.9], [-121.1 - i, 39.0]]}}
        for i, r in enumerate((101, 280, 580))
    ]
    (topo_dir / "shn_lines.geojson").write_text(
        json.dumps({"type": "FeatureCollection",
                    "features": [fwy80, fwy880] + others})
    )
