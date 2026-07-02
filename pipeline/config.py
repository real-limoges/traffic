"""Single home for every scope constant and calibration threshold.

Every number here is a judgment call, and SCHEMA.md points back at the
specific constant whenever it documents one. Change the constant, re-run
`make artifacts`, and the artifact reflects the new call — that is the
whole point of centralizing them.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

# ---------------------------------------------------------------- scope ---
# Bay Area freeway network, PeMS District 4. PeMS freeway numbers.
SCOPED_ROUTES = (80, 101, 280, 580, 880)
DISTRICT = 4

# Lane types (PeMS "Type" in station metadata) that form the mainline
# graph. HOV excluded deliberately: HOV lanes are access-restricted
# parallel facilities; folding their flow into mainline capacity would
# distort the volume-delay calibration. Ramp/connector detectors (OR, FR,
# FF) are not graph edges; connectors get default VDFs (see build_graph).
MAINLINE_TYPES = ("ML",)

# ------------------------------------------------- data-quality filters ---
# PeMS marks how much of each 5-min value was actually observed vs filled
# by its own imputation. Below this, the value is PeMS's model, not a
# measurement, and is excluded from calibration.
MIN_PCT_OBSERVED = 75

# Physical plausibility bounds; violations are marked invalid.
MAX_SPEED_MPH = 100.0
MIN_SPEED_MPH = 3.0
MAX_FLOW_PER_LANE_5MIN = 250       # = 3000 veh/hr/lane, above any observed
MAX_OCCUPANCY = 1.0

# A station-day keeps its data only if at least this fraction of its 288
# intervals is valid; otherwise the whole day is dropped for that station
# (a mostly-dead day says the detector, not the traffic, was the problem).
MIN_VALID_FRACTION_PER_DAY = 0.5

# A station participates in calibration only with at least this many
# retained days; otherwise its edge falls back to default VDF parameters.
MIN_CALIBRATION_DAYS = 10

# ------------------------------------------------------------ imputation ---
# Gaps of at most this many consecutive 5-min intervals are linearly
# interpolated (short dropouts); longer gaps stay missing — inventing an
# hour of traffic is not imputation, it's fiction.
MAX_IMPUTE_GAP_INTERVALS = 3

# ------------------------------------------------------------ free flow ---
# Free-flow speed = median speed during low-occupancy night hours.
FF_HOURS = (22, 23, 0, 1, 2, 3, 4)   # local hours treated as free-flow
FF_OCC_MAX = 0.08
FF_MIN_OBS = 100                     # fewer usable obs -> fallback + flag
FF_SPEED_CLAMP_MPH = (50.0, 75.0)
FF_SPEED_DEFAULT_MPH = 65.0

# -------------------------------------------------------------- capacity ---
# Practical capacity per lane = high percentile of sustained 15-minute
# flow rates (HCM-style), clamped to physically sane freeway bounds.
CAPACITY_PERCENTILE = 99.0
CAPACITY_CLAMP_VPHPL = (1400.0, 2400.0)
CAPACITY_DEFAULT_VPHPL = 1900.0
ROLLING_INTERVALS = 3                # 3 x 5min = 15-min sustained rate
ROLLING_MIN_VALID = 2                # of the 3, how many must be real

# ---------------------------------------------------------------- BPR fit ---
# t/t0 = 1 + alpha * (v/c)^beta, fit in log space on congested points.
BPR_FIT_MIN_RATIO = 1.05             # only points with real delay
BPR_FIT_MIN_VC = 0.2
BPR_FIT_MIN_POINTS = 200
BPR_ALPHA_BOUNDS = (0.01, 1.5)
BPR_BETA_BOUNDS = (1.0, 10.0)
BPR_ALPHA_DEFAULT = 0.15             # canonical BPR defaults
BPR_BETA_DEFAULT = 4.0

# ------------------------------------------------------- graph geometry ---
# Consecutive detectors farther apart than this get a routable edge but a
# `long_gap` flag (detector desert; calibration there is extrapolation).
MAX_SEGMENT_GAP_MI = 5.0
# A freeway-freeway crossing is an interchange if the routes' geometries
# pass within this distance (degrees would be wrong; we buffer in miles
# via a local approximation inside the stage).
INTERCHANGE_SNAP_MI = 1.0
# The nearest-station anchor for a crossing may be up to
# INTERCHANGE_SNAP_MI * SNAP_SLACK away (detector spacing exceeds the
# snap radius in places); beyond that the crossing goes unanchored and is
# reported in diagnostics.
SNAP_SLACK = 3.0
# Representative intersection points closer than this collapse into one
# crossing (parallel carriageways and concurrencies produce point sprays).
CROSSING_CLUSTER_MI = 2.0
# Default VDF for freeway-to-freeway connector edges (no detector data):
CONNECTOR_SPEED_MPH = 40.0
CONNECTOR_LENGTH_MI = 0.5
CONNECTOR_LANES = 1
CONNECTOR_CAPACITY_VPHPL = 1600.0

# ------------------------------------------------------------- artifact ---
ARTIFACT_FLOAT_DP = 4                # rounding for deterministic output
ARTIFACT_COORD_DP = 6
