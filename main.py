"""
main.py
-------
Day 4 update: the loop no longer hardcodes "print + save to db" for every
ball. It publishes a "new_ball" event on an EventBus, and independent
subscribers (print_ball, persist_ball) react to it. Adding a websocket
broadcaster tomorrow means adding ONE subscriber — zero changes to the
loop itself.

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
import db
from cricket_api import CricketAPIClient, CricketAPIError, NoLiveMatchError
from models import Ball, Match
from ball_detector import BallDetector
from event_bus import EventBus

logger = logging.getLogger("main")

NEW_BALL_EVENT = "new_ball"
INNINGS_RESUMED_EVENT = "innings_resumed"


# --------------------------------------------------------------------------- #
# Subscribers — each one only knows how to do ITS job. None of them know
# about each other, and none of them know about the polling loop's internals.
# --------------------------------------------------------------------------- #
def print_ball(match_id: str, ball: Ball) -> None:
    print(ball.summary())


def persist_ball(match_id: str, ball: Ball) -> None:
    db.save_ball(match_id, ball)


def build_default_bus() -> EventBus:
    """The standard set of subscribers for terminal + persistence usage."""
    bus = EventBus()
    bus.subscribe(NEW_BALL_EVENT, print_ball)
    bus.subscribe(NEW_BALL_EVENT, persist_ball)
    return bus


# --------------------------------------------------------------------------- #
def resolve_match_id(client: CricketAPIClient) -> str:
    if config.MATCH_ID:
        return config.MATCH_ID
    logger.info("No MATCH_ID configured — searching for a live %s match...", config.LEAGUE_FILTER)
    return client.find_live_match_id()


def run_loop(client: CricketAPIClient, bus: EventBus) -> None:
    db.init_db()
    detector = BallDetector()
    match_id: Optional[str] = None
    previous_state: Optional[Match] = None

    print("=" * 60)
    print(" IPL LIVE SCORE - TERMINAL BACKEND (Day 4)")
    print(f" Active subscribers on '{NEW_BALL_EVENT}': {bus.subscriber_count(NEW_BALL_EVENT)}")
    print("=" * 60)

    while True:
        try:
            if match_id is None:
                match_id = resolve_match_id(client)
                db.ensure_match(match_id)

                previous_state = db.get_last_match_state(match_id)
                if previous_state:
                    print(f"Resuming match {match_id} from saved state:")
                    for inn in previous_state.innings.values():
                        print(f"  {inn.team}: {inn.runs}/{inn.wickets} in {inn.overs} overs")
                else:
                    print(f"Tracking new match id: {match_id}")
                print()

            payload = client.get_match_info(match_id)
            current_state = Match.from_payload(match_id, payload)

            events = detector.detect(previous_state, current_state)
            for ball in events:
                bus.publish(NEW_BALL_EVENT, match_id, ball)

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

    bus = build_default_bus()
    run_loop(client, bus)


if __name__ == "__main__":
    main()
