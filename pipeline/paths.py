"""Locate raw inputs and define every intermediate file the stages share.

Raw-data discovery lives here so each stage can fail with the same clear,
actionable error when the manual PeMS pull hasn't happened yet.
"""

import re
from pathlib import Path

from . import config

PEMS_DIR_RE = re.compile(r"^pems-d04-(\d{8})-(\d{8})$")

MISSING_PULL_MSG = """\
No PeMS pull found under data/raw/.

Expected a directory like data/raw/pems-d04-20260501-20260531/ containing
d04_text_station_5min_YYYY_MM_DD.txt.gz files and one d04_text_meta_*.txt,
downloaded manually through a registered PeMS account (Caltrans offers no
public bulk API). See data/raw/README.md for the exact steps, then record
the pull in PROVENANCE.md and re-run `make artifacts`.
"""

MISSING_TOPOLOGY_MSG = """\
No topology file at data/raw/caltrans-network-topology/shn_lines.geojson.

Export the public "State Highway Network Lines" layer as GeoJSON from
https://gisdata-caltrans.opendata.arcgis.com and save it at that path.
See data/raw/README.md, then record the pull in PROVENANCE.md.
"""


def find_pems_pull(raw_dir: Path | None = None) -> Path:
    """Return the single pems-d04-* pull directory, or raise with help."""
    raw_dir = raw_dir or config.RAW_DIR
    pulls = sorted(
        p for p in raw_dir.iterdir()
        if p.is_dir() and PEMS_DIR_RE.match(p.name)
    ) if raw_dir.is_dir() else []
    if not pulls:
        raise FileNotFoundError(MISSING_PULL_MSG)
    if len(pulls) > 1:
        raise RuntimeError(
            "Multiple PeMS pull directories found under data/raw/: "
            f"{[p.name for p in pulls]}. Keep exactly one (the pinned one "
            "per PROVENANCE.md) so the artifact is unambiguous."
        )
    return pulls[0]


def meta_file(pull_dir: Path) -> Path:
    metas = sorted(pull_dir.glob("d04_text_meta_*.txt"))
    if not metas:
        raise FileNotFoundError(
            f"No d04_text_meta_*.txt in {pull_dir}. The station metadata "
            "file is required; see data/raw/README.md."
        )
    # The pinned station list is the latest metadata dated AT OR BEFORE the
    # pull range's end (data/raw/README.md). File names sort by date
    # (d04_text_meta_YYYY_MM_DD.txt), so string comparison suffices.
    m = PEMS_DIR_RE.match(pull_dir.name)
    end = m.group(2)  # YYYYMMDD
    in_range = [
        f for f in metas
        if f.stem.removeprefix("d04_text_meta_").replace("_", "") <= end
    ]
    if not in_range:
        raise FileNotFoundError(
            f"All metadata files in {pull_dir} are dated after the range "
            f"end {end}; download the metadata file at or before the end "
            "of the range (see data/raw/README.md)."
        )
    return in_range[-1]


def station_5min_files(pull_dir: Path) -> list[Path]:
    files = sorted(pull_dir.glob("d04_text_station_5min_*.txt.gz"))
    files += sorted(pull_dir.glob("d04_text_station_5min_*.txt"))
    if not files:
        raise FileNotFoundError(
            f"No d04_text_station_5min_* files in {pull_dir}. "
            "See data/raw/README.md."
        )
    return files


def topology_file(raw_dir: Path | None = None) -> Path:
    f = (raw_dir or config.RAW_DIR) / "caltrans-network-topology" / "shn_lines.geojson"
    if not f.exists():
        raise FileNotFoundError(MISSING_TOPOLOGY_MSG)
    return f


# Intermediate files (data/processed/) — the inter-stage contract.
STATIONS = config.PROCESSED_DIR / "stations.parquet"
READINGS_RAW = config.PROCESSED_DIR / "readings_raw.parquet"
READINGS_CLEAN = config.PROCESSED_DIR / "readings_clean.parquet"
QUALITY_REPORT = config.PROCESSED_DIR / "quality_report.json"
READINGS_FINAL = config.PROCESSED_DIR / "readings_final.parquet"
TOPOLOGY = config.PROCESSED_DIR / "topology.json"
GRAPH_STRUCTURE = config.PROCESSED_DIR / "graph_structure.json"
EDGE_CALIBRATION = config.PROCESSED_DIR / "edge_calibration.parquet"

NETWORK_GRAPH = config.ARTIFACTS_DIR / "network_graph.json"
