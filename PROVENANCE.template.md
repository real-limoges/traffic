# Provenance

Copy this into `PROVENANCE.md` for a real project. The point: re-running the
pipeline a year from now, after the upstream source has updated, should not
silently change results without a deliberate version bump.

## Data sources

### [Source name]
- **Version/release/pull identifier:**
- **Fetch date:**
- **URL:**
- **Access method:** (registered account / public download / API — note any
  access restrictions the source imposes, e.g. no programmatic bulk access)
- **Checksum (if applicable):**

## Regeneration

To reproduce `artifacts/` from `data/raw/` as pinned above: `make artifacts`

If the upstream source has since released a newer version, that's a
deliberate decision to re-pin, not an automatic update — bump the version
identifier above and re-run explicitly.
