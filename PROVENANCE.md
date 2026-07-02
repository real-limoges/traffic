# Provenance

The point: re-running the pipeline a year from now, after the upstream
source has updated, should not silently change results without a deliberate
version bump.

> **STATUS: DATA NOT YET PULLED.** The two sources below are pinned as to
> *access path and expected form*, but the actual pull has not happened:
> this repository was built in an environment with no PeMS account
> credentials and a network policy that blocks all Caltrans hosts. The
> fields marked `PENDING` must be filled in by whoever performs the manual
> download described in `data/raw/README.md`. Until then,
> `artifacts/network_graph.json` does not exist and `make artifacts` will
> stop with an explanatory error rather than fabricate output.

## Data sources

### PeMS station 5-minute data + station metadata, District 4 (Bay Area)
- **Version/release/pull identifier:** PENDING — directory name
  `data/raw/pems-d04-<start>-<end>/` plus the metadata file's own date stamp
  (e.g. `d04_text_meta_2026_05_15.txt`) together pin the pull.
- **Fetch date:** PENDING
- **URL:** https://pems.dot.ca.gov (Tools → Data Clearinghouse → District 4)
- **Access method:** Registered PeMS account, manual download from the Data
  Clearinghouse. Caltrans deliberately does not support programmatic bulk
  access; this project works within that path (a human logs in and
  downloads), not around it. No scraping automation is part of this
  pipeline.
- **Checksum:** PENDING — after download run
  `make pin-raw` (writes `data/raw/SHA256SUMS` and prints it for pasting
  here).

### Caltrans State Highway Network (SHN) Lines — network topology
- **Version/release/pull identifier:** PENDING — the portal's "Data Updated"
  date shown on the dataset page at download time.
- **Fetch date:** PENDING
- **URL:** https://gisdata-caltrans.opendata.arcgis.com — dataset "State
  Highway Network Lines", exported as GeoJSON to
  `data/raw/caltrans-network-topology/shn_lines.geojson`.
- **Access method:** Public open-data download, no account required.
- **Checksum:** PENDING (included in `data/raw/SHA256SUMS` via `make pin-raw`).

## Detector station list version

The station list used to build the graph is exactly the set of stations in
the pinned `d04_text_meta_*.txt` file after the scope filter
(`pipeline/config.py: SCOPED_ROUTES`, District 4, mainline + HOV lane
types). No stations are added from any other source.

## Regeneration

To reproduce `artifacts/` from `data/raw/` as pinned above:

```
make artifacts
```

Deterministic: no randomness anywhere in the pipeline (no sampling, no
random seeds needed); all iteration orders are explicitly sorted and JSON
output is key-sorted with fixed float precision, so byte-identical output
follows from byte-identical input.

If the upstream source has since released a newer version, that's a
deliberate decision to re-pin, not an automatic update — bump the
identifiers above and re-run explicitly.
