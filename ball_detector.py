"""
ball_detector.py
-----------------
Pure logic: given a previous Match state and a new Match state, work out
what Ball events happened in between. No I/O, no printing, no network —
which is exactly why this is easy to unit test (see test_ball_detector.py).

This used to be tangled inside main.py's diff_and_report(). Pulling it out
means:
- We can unit test scoring logic without hitting a real API.
- Tomorrow's website/event-bus layer can call `detect(prev, curr)` and get
  back structured Ball objects instead of scraping printed text.
"""

from __future__ import annotations

from models import Ball, EventType, Innings, Match


class BallDetector:
    """Stateless detector: compares two Match snapshots and returns Ball events."""

    def detect(self, previous: Match | None, current: Match) -> list[Ball]:
        events: list[Ball] = []

        for idx, curr_inn in current.innings.items():
            prev_inn = previous.innings.get(idx) if previous else None

            if prev_inn is None:
                events.append(self._innings_start_event(idx, curr_inn))
                continue

            event = self._diff_innings(idx, prev_inn, curr_inn)
            if event is not None:
                events.append(event)

        return events

    # ------------------------------------------------------------------ #
    @staticmethod
    def _innings_start_event(idx: int, inn: Innings) -> Ball:
        return Ball(
            innings_index=idx,
            team=inn.team,
            over=inn.overs,
            runs_scored=inn.runs,
            wickets_added=inn.wickets,
            total_runs=inn.runs,
            total_wickets=inn.wickets,
            balls_covered=inn.as_ball_count() or 1,
            event_type=EventType.INNINGS_START,
        )

    @staticmethod
    def _diff_innings(idx: int, prev: Innings, curr: Innings) -> Ball | None:
        balls_before = prev.as_ball_count()
        balls_now = curr.as_ball_count()
        balls_covered = balls_now - balls_before

        if balls_covered <= 0:
            return None  # nothing new since last poll

        runs_scored = curr.runs - prev.runs
        wickets_added = curr.wickets - prev.wickets

        if wickets_added > 0 and runs_scored > 0:
            event_type = EventType.RUNS_AND_WICKET
        elif wickets_added > 0:
            event_type = EventType.WICKET
        elif balls_covered > 1:
            event_type = EventType.OVER_SUMMARY
        else:
            event_type = EventType.RUNS

        return Ball(
            innings_index=idx,
            team=curr.team,
            over=curr.overs,
            runs_scored=runs_scored,
            wickets_added=wickets_added,
            total_runs=curr.runs,
            total_wickets=curr.wickets,
            balls_covered=balls_covered,
            event_type=event_type,
        )
