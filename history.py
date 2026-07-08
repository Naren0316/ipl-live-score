"""
history.py
-----------
Small CLI to inspect what's been persisted to the database — useful for
checking things worked, and it's a preview of the query logic the future
website/API layer will reuse.

Usage:
    python3 history.py --list                 # show all known match ids
    python3 history.py --match <match_id>      # show full ball-by-ball log
"""

from __future__ import annotations

import argparse

import db


def print_match_history(match_id: str) -> None:
    balls = db.get_ball_history(match_id)
    if not balls:
        print(f"No history found for match_id={match_id!r}")
        return

    print(f"Ball-by-ball log for {match_id} ({len(balls)} events):\n")
    for ball in balls:
        ts = ball.timestamp.strftime("%H:%M:%S")
        print(f"[{ts}] {ball.summary()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query saved IPL score history")
    parser.add_argument("--list", action="store_true", help="List all known match ids")
    parser.add_argument("--match", type=str, help="Show full history for a match id")
    args = parser.parse_args()

    db.init_db()

    if args.list:
        matches = db.list_known_matches()
        if not matches:
            print("No matches recorded yet.")
        for m in matches:
            print(m)
        return

    if args.match:
        print_match_history(args.match)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
