"""
test_ball_detector.py
----------------------
Unit tests for BallDetector. Runs instantly, no network, no API key needed.

Run with:
    python3 -m unittest test_ball_detector.py -v
"""

import unittest

from models import Innings, Match, EventType
from ball_detector import BallDetector


def make_match(match_id: str, runs: int, wickets: int, overs: float, team: str = "Mumbai Indians") -> Match:
    m = Match(match_id=match_id)
    m.innings[0] = Innings(index=0, team=team, runs=runs, wickets=wickets, overs=overs)
    return m


class TestBallDetector(unittest.TestCase):

    def setUp(self) -> None:
        self.detector = BallDetector()

    def test_innings_start_when_no_previous_state(self) -> None:
        current = make_match("m1", runs=0, wickets=0, overs=0.0)
        events = self.detector.detect(None, current)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, EventType.INNINGS_START)

    def test_single_ball_with_runs_only(self) -> None:
        prev = make_match("m1", runs=10, wickets=0, overs=1.4)
        curr = make_match("m1", runs=14, wickets=0, overs=1.5)  # one more ball, 4 runs

        events = self.detector.detect(prev, curr)

        self.assertEqual(len(events), 1)
        ball = events[0]
        self.assertEqual(ball.runs_scored, 4)
        self.assertEqual(ball.wickets_added, 0)
        self.assertEqual(ball.balls_covered, 1)
        self.assertTrue(ball.is_clean_single_ball())
        self.assertEqual(ball.event_type, EventType.RUNS)

    def test_single_ball_with_wicket(self) -> None:
        prev = make_match("m1", runs=50, wickets=1, overs=5.2)
        curr = make_match("m1", runs=50, wickets=2, overs=5.3)  # dot ball, wicket

        events = self.detector.detect(prev, curr)

        ball = events[0]
        self.assertEqual(ball.runs_scored, 0)
        self.assertEqual(ball.wickets_added, 1)
        self.assertEqual(ball.event_type, EventType.WICKET)

    def test_no_new_ball_returns_no_event(self) -> None:
        prev = make_match("m1", runs=30, wickets=1, overs=3.2)
        curr = make_match("m1", runs=30, wickets=1, overs=3.2)  # unchanged (polled too fast)

        events = self.detector.detect(prev, curr)

        self.assertEqual(len(events), 0)

    def test_multiple_balls_covered_in_one_poll(self) -> None:
        # Simulates polling too slowly and missing more than one ball
        prev = make_match("m1", runs=20, wickets=0, overs=2.0)
        curr = make_match("m1", runs=32, wickets=0, overs=2.3)  # 3 balls passed

        events = self.detector.detect(prev, curr)

        ball = events[0]
        self.assertEqual(ball.balls_covered, 3)
        self.assertFalse(ball.is_clean_single_ball())
        self.assertEqual(ball.event_type, EventType.OVER_SUMMARY)

    def test_over_rollover_ball_count_is_correct(self) -> None:
        # 5.5 -> 6.0 is ONE ball (end of over), not a jump
        prev = make_match("m1", runs=40, wickets=0, overs=5.5)
        curr = make_match("m1", runs=41, wickets=0, overs=6.0)

        events = self.detector.detect(prev, curr)

        ball = events[0]
        self.assertEqual(ball.balls_covered, 1)
        self.assertEqual(ball.runs_scored, 1)

    def test_runs_and_wicket_together(self) -> None:
        prev = make_match("m1", runs=60, wickets=2, overs=8.1)
        curr = make_match("m1", runs=62, wickets=3, overs=8.2)  # 2 runs then run-out, e.g.

        events = self.detector.detect(prev, curr)

        ball = events[0]
        self.assertEqual(ball.event_type, EventType.RUNS_AND_WICKET)


if __name__ == "__main__":
    unittest.main()
