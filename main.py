"""
main.py
-------
Day 1 backend engine: polls the cricket API on an interval, detects when a
NEW BALL has been bowled (by diffing overs/runs/wickets against the last
seen state), and prints an updating scoreboard to the terminal.

Run modes:
    python main.py                -> live polling loop (default)
    python main.py --once         -> single fetch, print state, exit
    python main.py --dump-raw     -> print raw API JSON (use this FIRST to
                                      confirm the exact response shape your
                                      API plan returns, then adjust
                                      ScoreState.update_from_payload below)

Architecture note:
    This file owns "what a ball means" and "what to print". It knows
    NOTHING about HTTP — all of that lives in cricket_api.py. Tomorrow this
    is where we'll plug in: a event bus / callback system so the website
    (Day 5+) can subscribe to "new_ball" events instead of us just printing.
"""

from __future__ import annotations

import sys
import time
import json
import argparse
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import config
from cricket_api import CricketAPIClient, CricketAPIError, NoLiveMatchError

logger = logging.getLogger("main")


@dataclass
class InningsState:
    """Snapshot of one innings at a point in time."""
    team: str = ""
    runs: int = 0
    wickets: int = 0
    overs: float = 0.0

    def as_ball_count(self) -> int:
        """Convert overs like 12.4 -> 76 legal balls, for reliable diffing."""
        completed_overs = int(self.overs)
        balls_in_over = round((self.overs - completed_overs) * 10)
        return completed_overs * 6 + balls_in_over


@dataclass
class ScoreState:
    """Full match state we track across polls (both innings, if applicable)."""
    innings: dict[int, InningsState] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ScoreState":
        """
        Build a ScoreState from a CricAPI match_info-style payload.
        Expected shape (typical CricAPI 'score' list):
            payload["score"] = [
                {"r": 76, "w": 2, "o": 12.4, "inning": "Team A Inning 1"},
                ...
            ]
        If your actual API plan returns a different shape, this is the ONLY
        place you need to change — run with --dump-raw to inspect first.
        """
        state = cls()
        for idx, inn in enumerate(payload.get("score", [])):
            state.innings[idx] = InningsState(
                team=inn.get("inning", f"Innings {idx + 1}"),
                runs=inn.get("r", 0),
                wickets=inn.get("w", 0),
                overs=inn.get("o", 0.0),
            )
        return state


def diff_and_report(previous: Optional[ScoreState], current: ScoreState) -> None:
    """
    Compare previous vs current state. Print a line for every ball that
    has newly been bowled, plus the updated total.
    """
    for idx, curr_inn in current.innings.items():
        prev_inn = previous.innings.get(idx) if previous else None

        if prev_inn is None:
            # First time we see this innings this run
            print(f"\n=== {curr_inn.team} — innings started ===")
            print(f"Score: {curr_inn.runs}/{curr_inn.wickets} in {curr_inn.overs} overs")
            continue

        balls_now = curr_inn.as_ball_count()
        balls_before = prev_inn.as_ball_count()
        new_balls = balls_now - balls_before

        if new_balls <= 0:
            continue  # no new ball bowled since last poll

        runs_added = curr_inn.runs - prev_inn.runs
        wickets_added = curr_inn.wickets - prev_inn.wickets

        # If more than 1 "ball" worth of change came through in one poll
        # (e.g. we polled too slowly), we report it as a combined update
        # rather than guessing per-ball detail we don't have.
        over_display = curr_inn.overs
        event = f"[Ball @ over {over_display}] +{runs_added} run(s)"
        if wickets_added > 0:
            event += f" | WICKET x{wickets_added}"
        if new_balls > 1:
            event += f"  (covers {new_balls} balls since last poll — consider lowering POLL_INTERVAL_SECONDS)"

        print(event)
        print(f"    -> Score now: {curr_inn.runs}/{curr_inn.wickets} in {curr_inn.overs} overs "
              f"({curr_inn.team})")


def resolve_match_id(client: CricketAPIClient) -> str:
    if config.MATCH_ID:
        return config.MATCH_ID
    logger.info("No MATCH_ID configured — searching for a live %s match...", config.LEAGUE_FILTER)
    return client.find_live_match_id()


def run_loop(client: CricketAPIClient) -> None:
    match_id: Optional[str] = None
    previous_state: Optional[ScoreState] = None

    print("=" * 60)
    print(" IPL LIVE SCORE — TERMINAL BACKEND (Day 1)")
    print("=" * 60)

    while True:
        try:
            if match_id is None:
                match_id = resolve_match_id(client)
                print(f"Tracking match id: {match_id}\n")

            payload = client.get_match_info(match_id)
            current_state = ScoreState.from_payload(payload)
            diff_and_report(previous_state, current_state)
            previous_state = current_state

        except NoLiveMatchError:
            logger.info("No live match right now. Retrying in %ss...", config.POLL_INTERVAL_SECONDS)
            match_id = None  # force re-search next loop
        except CricketAPIError as exc:
            logger.error("API error: %s. Will retry.", exc)
        except KeyboardInterrupt:
            print("\nStopped by user. Bye!")
            sys.exit(0)

        time.sleep(config.POLL_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="IPL live score terminal backend")
    parser.add_argument("--once", action="store_true", help="Fetch once and exit")
    parser.add_argument("--dump-raw", action="store_true", help="Print raw API JSON and exit")
    args = parser.parse_args()

    client = CricketAPIClient()

    if args.dump_raw:
        match_id = resolve_match_id(client)
        payload = client.get_match_info(match_id)
        print(json.dumps(payload, indent=2))
        return

    if args.once:
        match_id = resolve_match_id(client)
        payload = client.get_match_info(match_id)
        state = ScoreState.from_payload(payload)
        diff_and_report(None, state)
        return

    run_loop(client)


if __name__ == "__main__":
    main()
