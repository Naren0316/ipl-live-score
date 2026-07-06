"""
cricket_api.py
---------------
Thin, defensive wrapper around the CricketData.org (CricAPI) REST API.

Design goals:
- Isolate ALL network/API details in one place. If we ever switch providers
  (Cricbuzz via RapidAPI, Roanuz, EntitySport, etc.) only this file changes —
  main.py / score_tracker.py never touch requests/HTTP directly.
- Fail loudly but predictably: custom exceptions instead of letting random
  requests exceptions or KeyErrors bubble up from deep in the app.
- Built-in retry with backoff, since free-tier APIs are sometimes flaky.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

import requests

import config

logger = logging.getLogger("cricket_api")
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class CricketAPIError(Exception):
    """Raised for any failure talking to the cricket API (network, HTTP, or API-level error)."""


class NoLiveMatchError(CricketAPIError):
    """Raised when we expected a live match but none was found."""


class CricketAPIClient:
    """Handles all communication with the cricket data provider."""

    def __init__(
        self,
        api_key: str = config.API_KEY,
        base_url: str = config.BASE_URL,
        timeout: float = config.REQUEST_TIMEOUT_SECONDS,
        max_retries: int = config.MAX_RETRIES,
    ) -> None:
        if not api_key or api_key == "PUT_YOUR_API_KEY_HERE":
            logger.warning(
                "No real API key configured. Set CRICKET_API_KEY env var "
                "before running against the live API."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()

    # ------------------------------------------------------------------ #
    # Low-level request helper
    # ------------------------------------------------------------------ #
    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict[str, Any]:
        """
        GET a CricAPI endpoint with retries + backoff.
        Raises CricketAPIError on final failure.
        """
        params = dict(params or {})
        params["apikey"] = self.api_key
        url = f"{self.base_url}{endpoint}"

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("GET %s params=%s (attempt %d)", endpoint, params, attempt)
                resp = self._session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()

                # CricAPI convention: {"status": "success"/"failure", ...}
                if data.get("status") not in (None, "success"):
                    raise CricketAPIError(
                        f"API returned status={data.get('status')!r}: "
                        f"{data.get('reason', 'no reason given')}"
                    )
                return data

            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                logger.warning(
                    "Request failed (attempt %d/%d): %s",
                    attempt, self.max_retries, exc,
                )
                if attempt < self.max_retries:
                    time.sleep(config.RETRY_BACKOFF_SECONDS * attempt)

        raise CricketAPIError(f"Failed to reach {url} after {self.max_retries} attempts") from last_exc

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_current_matches(self) -> list[dict[str, Any]]:
        """Return the list of current (live/recent/upcoming) matches."""
        data = self._get(config.ENDPOINT_CURRENT_MATCHES)
        return data.get("data", [])

    def find_live_match_id(self, league_filter: str = config.LEAGUE_FILTER) -> str:
        """
        Scan current matches for a live one matching league_filter
        (e.g. "IPL") and return its match id.
        """
        matches = self.get_current_matches()
        for m in matches:
            name = f"{m.get('name', '')} {m.get('series', '') or m.get('series_id', '')}".lower()
            status = (m.get("status") or "").lower()
            is_live = m.get("matchStarted") and not m.get("matchEnded")
            if league_filter.lower() in name and is_live:
                logger.info("Found live match: %s (%s)", m.get("name"), m.get("id"))
                return m["id"]
            logger.debug("Skipping match %s status=%s", m.get("name"), status)

        raise NoLiveMatchError(f"No live match found matching {league_filter!r}")

    def get_match_info(self, match_id: str) -> dict[str, Any]:
        """
        Full live match info: score by innings, current batsmen/bowler,
        and (plan-dependent) recent ball-by-ball data.
        """
        data = self._get(config.ENDPOINT_MATCH_INFO, params={"id": match_id})
        return data.get("data", {})

    def get_match_scorecard(self, match_id: str) -> dict[str, Any]:
        """Detailed scorecard (batting/bowling breakdown) for a match."""
        data = self._get(config.ENDPOINT_MATCH_SCORE, params={"id": match_id})
        return data.get("data", {})
