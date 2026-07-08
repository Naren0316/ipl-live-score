"""
test_db.py
----------
Unit tests for db.py. Uses a temporary SQLite file per test so nothing
touches your real ipl_scores.db.

Run with:
    python3 -m unittest test_db.py -v
"""

import os
import tempfile
import unittest

import db
from models import Ball, EventType


def make_ball(over=1.5, runs=4, wickets=0, total_runs=14, total_wickets=0) -> Ball:
    return Ball(
        innings_index=0,
        team="Mumbai Indians",
        over=over,
        runs_scored=runs,
        wickets_added=wickets,
        total_runs=total_runs,
        total_wickets=total_wickets,
        balls_covered=1,
        event_type=EventType.RUNS if wickets == 0 else EventType.WICKET,
    )


class TestDB(unittest.TestCase):

    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db.init_db(self.db_path)

    def tearDown(self) -> None:
        os.remove(self.db_path)

    def test_init_db_is_idempotent(self) -> None:
        db.init_db(self.db_path)  # calling twice should not raise
        db.init_db(self.db_path)

    def test_save_and_retrieve_ball_history(self) -> None:
        db.ensure_match("match1", self.db_path)
        db.save_ball("match1", make_ball(over=1.1, runs=1, total_runs=1), self.db_path)
        db.save_ball("match1", make_ball(over=1.2, runs=4, total_runs=5), self.db_path)

        history = db.get_ball_history("match1", self.db_path)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].total_runs, 1)
        self.assertEqual(history[1].total_runs, 5)

    def test_get_last_match_state_reconstructs_innings(self) -> None:
        db.ensure_match("match1", self.db_path)
        db.save_ball("match1", make_ball(over=1.1, runs=1, total_runs=1), self.db_path)
        db.save_ball("match1", make_ball(over=1.2, runs=4, total_runs=5, total_wickets=1, wickets=1), self.db_path)

        state = db.get_last_match_state("match1", self.db_path)

        self.assertIsNotNone(state)
        innings = state.innings[0]
        self.assertEqual(innings.runs, 5)
        self.assertEqual(innings.wickets, 1)
        self.assertEqual(innings.overs, 1.2)

    def test_get_last_match_state_returns_none_for_unknown_match(self) -> None:
        state = db.get_last_match_state("never-seen-this-id", self.db_path)
        self.assertIsNone(state)

    def test_multiple_innings_tracked_independently(self) -> None:
        db.ensure_match("match1", self.db_path)
        ball_inn0 = make_ball(over=19.6, runs=2, total_runs=180)
        ball_inn1 = Ball(
            innings_index=1, team="Chennai Super Kings", over=0.1,
            runs_scored=1, wickets_added=0, total_runs=1, total_wickets=0,
            balls_covered=1, event_type=EventType.RUNS,
        )
        db.save_ball("match1", ball_inn0, self.db_path)
        db.save_ball("match1", ball_inn1, self.db_path)

        state = db.get_last_match_state("match1", self.db_path)

        self.assertEqual(state.innings[0].team, "Mumbai Indians")
        self.assertEqual(state.innings[1].team, "Chennai Super Kings")

    def test_list_known_matches(self) -> None:
        db.ensure_match("match1", self.db_path)
        db.ensure_match("match2", self.db_path)

        matches = db.list_known_matches(self.db_path)

        self.assertIn("match1", matches)
        self.assertIn("match2", matches)


if __name__ == "__main__":
    unittest.main()
