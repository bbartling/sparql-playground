"""Shared constants for the beginner lesson scripts.

Edit BASE_URL to point at Render or a local `brickts serve`.
Dataset history for AHU_1 spans roughly 2026-03-16 → 2026-07-17 (UTC).
"""

# --- edit these -------------------------------------------------------------
BASE_URL = "https://sparql-playground.onrender.com"
# BASE_URL = "http://127.0.0.1:8000"

EQUIPMENT = "AHU_1"

# One month inside the loaded CSV range (unix seconds used by the timeseries API)
START_ISO = "2026-06-01T00:00:00+00:00"
END_ISO = "2026-07-01T00:00:00+00:00"
# ----------------------------------------------------------------------------

POLL_SECONDS = 300  # open-fdd FC1 sample period for this dataset (5 minutes)
