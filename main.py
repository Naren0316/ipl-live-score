"""
main.py
-------
Day 2 update: now uses models.py + ball_detector.py instead of inline
dict-diffing. The polling loop's job is now ONLY: fetch -> detect -> print.
All the "what counts as a ball" logic lives in ball_detector.py and is
independently unit-tested (see test_ball_detector.py).

Run modes:
    python main.py                -> live polling loop (default)
    python main.py --once         -> single fetch, print state, exit
    python main.py --dump-raw     -> print raw API JSON (inspect response shape)
"""

from __future__ import annotations

import sys
import time
import json
import argparse
import logging
from typing import Optional

import config
from cricket_api import CricketAPIClient, CricketAPIError, NoLiveMatchError
from models import Match
from ball_detector import BallDetector

logger = logging.getLogger("main")


def resolve_match_id(client: CricketAPIClient) -> str:
    if config.MATCH_ID:
        return config.MATCH_ID
    logger.info("No MATCH_ID configured — searching for a live %s match...", config.LEAGUE_FILTER)
    return client.find_live_match_id()


def run_loop(client: CricketAPIClient) -> None:
    detector = BallDetector()
    match_id: Optional[str] = None
    previous_state: Optional[Match] = None

    print("=" * 60)
    print(" IPL LIVE SCORE - TERMINAL BACKEND (Day 2)")
    print("=" * 60)

    while True:
        try:
            if match_id is None:
                match_id = resolve_match_id(client)
                print(f"Tracking match id: {match_id}\n")

            payload = client.get_match_info(match_id)
            current_state = Match.from_payload(match_id, payload)

            events = detector.detect(previous_state, current_state)
            for ball in events:
                print(ball.summary())

            previous_state = current_state

        except NoLiveMatchError:
            logger.info("No live match right now. Retrying in %ss...", config.POLL_INTERVAL_SECONDS)
            match_id = None
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
        state = Match.from_payload(match_id, payload)
        detector = BallDetector()
        for ball in detector.detect(None, state):
            print(ball.summary())
        return

    run_loop(client)


if __name__ == "__main__":
    main()
