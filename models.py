"""
models.py
---------
Domain models for the cricket backend. Day 1 passed raw dicts around;
that doesn't scale and has no type safety. From here on, every part of
the app talks in terms of these classes.

Why this matters for a "strong backend":
- A `Ball` is now a real, addressable event — easy to log, persist (Day 3),
  or emit over a websocket (Day 5-6) without reshaping data each time.
- Validation lives in one place (here), not scattered across main.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class EventType(str, Enum):
    """What kind of thing happened on a ball."""
    RUNS = "runs"
    WICKET = "wicket"
    RUNS_AND_WICKET = "runs_and_wicket"  # rare: run-out on a scoring shot
    OVER_SUMMARY = "over_summary"        # fallback when we can't isolate a single ball
    INNINGS_START = "innings_start"


@dataclass(frozen=True)
class Ball:
    """
    A single detected scoring event. On the free API tier this usually
    represents "what changed since the last poll" rather than a literal
    single delivery — see `balls_covered`.
    """
    innings_index: int
    team: str
    over: float                # e.g. 12.4
    runs_scored: int           # runs added since last poll
    wickets_added: int
    total_runs: int            # running total after this event
    total_wickets: int
    balls_covered: int         # how many legal deliveries this event spans (1 = clean single-ball detection)
    event_type: EventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_clean_single_ball(self) -> bool:
        """True if this event represents exactly one delivery (ideal case)."""
        return self.balls_covered == 1

    def summary(self) -> str:
        parts = [f"+{self.runs_scored} run(s)"]
        if self.wickets_added:
            parts.append(f"WICKET x{self.wickets_added}")
        detail = " | ".join(parts)
        coverage = "" if self.is_clean_single_ball() else f" (spans {self.balls_covered} balls)"
        return f"[Over {self.over}] {detail}{coverage} -> {self.total_runs}/{self.total_wickets}"


@dataclass
class Innings:
    """Current state of one innings, used for diffing between polls."""
    index: int
    team: str
    runs: int = 0
    wickets: int = 0
    overs: float = 0.0

    def as_ball_count(self) -> int:
        """Convert overs notation (12.4) into a real legal-ball count (76)."""
        completed_overs = int(self.overs)
        balls_in_over = round((self.overs - completed_overs) * 10)
        return completed_overs * 6 + balls_in_over

    @classmethod
    def from_raw(cls, index: int, raw: dict) -> "Innings":
        """Build from a raw CricAPI score entry: {'r':.., 'w':.., 'o':.., 'inning':..}"""
        return cls(
            index=index,
            team=raw.get("inning", f"Innings {index + 1}"),
            runs=int(raw.get("r", 0) or 0),
            wickets=int(raw.get("w", 0) or 0),
            overs=float(raw.get("o", 0.0) or 0.0),
        )


@dataclass
class Match:
    """Full match state: id + all innings seen so far."""
    match_id: str
    innings: dict[int, Innings] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, match_id: str, payload: dict) -> "Match":
        match = cls(match_id=match_id)
        for idx, raw in enumerate(payload.get("score", [])):
            match.innings[idx] = Innings.from_raw(idx, raw)
        return match
