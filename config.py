"""
config.py
---------
Central configuration for the IPL Live Score backend.

Keep ALL environment-specific / secret values here (or better, pulled from
environment variables) so the rest of the codebase never hardcodes them.
"""

import os

# ---------------------------------------------------------------------------
# API credentials & endpoints
# ---------------------------------------------------------------------------
# Get a free key from https://cricketdata.org (formerly CricAPI).
# NEVER commit your real key to source control — set it as an env var:
#   export CRICKET_API_KEY="your-real-key"
API_KEY: str = os.environ.get("CRICKET_API_KEY", "PUT_YOUR_API_KEY_HERE")

BASE_URL: str = "https://api.cricapi.com/v1"

# Endpoints we use (relative to BASE_URL)
ENDPOINT_CURRENT_MATCHES = "/currentMatches"   # list of live/upcoming matches
ENDPOINT_MATCH_SCORE = "/match_scorecard"      # full scorecard for a match
ENDPOINT_MATCH_INFO = "/match_info"            # ball-by-ball / live info

# ---------------------------------------------------------------------------
# Match selection
# ---------------------------------------------------------------------------
# Leave as None to auto-pick the first live IPL match found via
# currentMatches. Or hardcode a match_id once you know it (saves an API call
# every run). You get this id from the currentMatches response.
MATCH_ID: str | None = os.environ.get("MATCH_ID", None)

# Only auto-pick matches whose series/name contains this text (case-insensitive)
LEAGUE_FILTER: str = "IPL"

# ---------------------------------------------------------------------------
# Polling behaviour
# ---------------------------------------------------------------------------
POLL_INTERVAL_SECONDS: float = 5.0   # how often we hit the API
REQUEST_TIMEOUT_SECONDS: float = 8.0
MAX_RETRIES: int = 3
RETRY_BACKOFF_SECONDS: float = 2.0   # multiplied by attempt number

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
DEBUG: bool = os.environ.get("DEBUG", "0") == "1"
