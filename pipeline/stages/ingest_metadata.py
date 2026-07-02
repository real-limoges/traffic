"""Stage: ingest_metadata — PeMS station metadata -> stations.parquet.

Input:  data/raw/pems-d04-*/d04_text_meta_YYYY_MM_DD.txt (tab-separated,
        with header: ID Fwy Dir District County City State_PM Abs_PM
        Latitude Longitude Length Type Lanes Name User_ID_1..4)
Output: data/processed/stations.parquet — scoped mainline stations only.

Scope filter (SCHEMA.md "Station scope"): District 4, freeway in
config.SCOPED_ROUTES, lane type in config.MAINLINE_TYPES, with usable
coordinates and absolute postmile. Stations failing the filter are counted
and reported, never silently vanished.

Duplicate handling (SCHEMA.md "Duplicate stations at one postmile"):
PeMS metadata sometimes lists multiple station IDs at the same
(freeway, direction, Abs_PM) — typically detector replacements. We keep
the one with the most lanes (the fullest cross-section), tie-broken by
lowest station ID for determinism.
"""

import pandas as pd

from .. import config, paths

REQUIRED_COLS = {
    "ID", "Fwy", "Dir", "District", "County", "State_PM", "Abs_PM",
    "Latitude", "Longitude", "Length", "Type", "Lanes", "Name",
}


def run() -> None:
    pull = paths.find_pems_pull()
    meta_path = paths.meta_file(pull)
    df = pd.read_csv(meta_path, sep="\t", dtype=str)
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"{meta_path.name} lacks expected PeMS metadata columns: "
            f"{sorted(missing)}. Got: {list(df.columns)}"
        )

    n_total = len(df)
    for col in ("ID", "Fwy", "District", "Lanes"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("Abs_PM", "Latitude", "Longitude", "Length"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    scoped = df[
        (df["District"] == config.DISTRICT)
        & df["Fwy"].isin(config.SCOPED_ROUTES)
        & df["Type"].isin(config.MAINLINE_TYPES)
    ].copy()
    n_scoped = len(scoped)

    usable = scoped.dropna(
        subset=["ID", "Abs_PM", "Latitude", "Longitude", "Lanes"]
    ).copy()
    n_unusable = n_scoped - len(usable)

    usable["ID"] = usable["ID"].astype("int64")
    usable["Fwy"] = usable["Fwy"].astype("int64")
    usable["Lanes"] = usable["Lanes"].astype("int64")

    # Deterministic duplicate resolution at identical postmile.
    usable = usable.sort_values(
        ["Fwy", "Dir", "Abs_PM", "Lanes", "ID"],
        ascending=[True, True, True, False, True],
    )
    before_dedup = len(usable)
    usable = usable.drop_duplicates(
        subset=["Fwy", "Dir", "Abs_PM"], keep="first"
    )

    out = usable.rename(
        columns={
            "ID": "station_id", "Fwy": "fwy", "Dir": "direction",
            "County": "county", "State_PM": "state_pm", "Abs_PM": "abs_pm",
            "Latitude": "lat", "Longitude": "lon", "Length": "pems_length_mi",
            "Lanes": "lanes", "Name": "name", "Type": "lane_type",
        }
    )[
        ["station_id", "fwy", "direction", "county", "state_pm", "abs_pm",
         "lat", "lon", "pems_length_mi", "lanes", "name", "lane_type"]
    ].sort_values("station_id").reset_index(drop=True)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(paths.STATIONS, index=False)
    print(
        f"[ingest_metadata] {meta_path.name}: {n_total} stations in file, "
        f"{n_scoped} in scope (D{config.DISTRICT}, routes "
        f"{config.SCOPED_ROUTES}, types {config.MAINLINE_TYPES}), "
        f"{n_unusable} dropped for missing coords/postmile/lanes, "
        f"{before_dedup - len(out)} duplicate-postmile stations collapsed, "
        f"{len(out)} written -> {paths.STATIONS.name}"
    )
