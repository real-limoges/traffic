# data/raw/ — untouched source data

Nothing in this directory is ever edited. The pipeline reads it; it never
writes here. Every file placed here must be recorded in `/PROVENANCE.md`.

## What goes here, exactly

### 1. PeMS detector data → `pems-d04-<YYYYMMDD>-<YYYYMMDD>/`

Downloaded manually through your registered PeMS account at
<https://pems.dot.ca.gov> (Caltrans deliberately does not offer a public
bulk API — the Data Clearinghouse behind the login is the sanctioned path).

From **Tools → Data Clearinghouse**, select **District 4**, and download:

- **Type: `Station 5-Minute`** — one file per day for the chosen date range:
  `d04_text_station_5min_YYYY_MM_DD.txt.gz`
  (leave them gzipped; the pipeline reads `.txt.gz` directly)
- **Type: `Station Metadata`** — the metadata file whose date is closest to
  (at or before) the end of the range: `d04_text_meta_YYYY_MM_DD.txt`

Put all of them flat inside one directory named for the range, e.g.

```
data/raw/pems-d04-20260501-20260531/
  d04_text_station_5min_2026_05_01.txt.gz
  ...
  d04_text_station_5min_2026_05_31.txt.gz
  d04_text_meta_2026_05_15.txt
```

Recommended range: one full recent month (≥ 20 weekdays) with no major
holidays, e.g. May 2026. Longer is fine; the pipeline aggregates across all
days present.

### 2. Highway network topology → `caltrans-network-topology/`

The Caltrans **State Highway Network (SHN) Lines** layer, exported as
GeoJSON from the Caltrans GIS open-data portal
(<https://gisdata-caltrans.opendata.arcgis.com>, dataset "State Highway
Network Lines" — public, no account needed). Save as:

```
data/raw/caltrans-network-topology/shn_lines.geojson
```

Any export that includes route number, county, direction and geometry per
feature works; the pipeline filters to the scoped Bay Area routes itself.

## After placing files

1. Fill in the pull dates / identifiers in `/PROVENANCE.md`.
2. Run `make artifacts`.
