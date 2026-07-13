"""
event_bus.py
------------
A minimal synchronous pub/sub event bus.

Why this matters: right now, "print the ball" and "save the ball to DB" are
two hardcoded things main.py's loop does. Tomorrow a WebSocket layer needs
to react to every ball too. Without a bus, main.py's loop keeps growing a
new hardcoded call for every new consumer — that's how loops turn to
spaghetti.

With a bus: the loop just does `bus.publish("new_ball", ball)`. It has zero
idea who's listening or how many listeners there are. Printing, DB saving,
and (Day 5-6) broadcasting over a websocket all become independent
subscribers, addable/removable without touching the loop at all.

Deliberately synchronous and dependency-free (no external event-loop
library) — for this project's size that's a benefit, not a shortcut:
callbacks run in the order they were subscribed, exceptions in one
subscriber don't get swallowed, and there's nothing extra to learn.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, DefaultDict

logger = logging.getLogger("event_bus")

Callback = Callable[..., None]


class EventBus:
    """Subscribe callbacks to named events; publish events to run them all."""

    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, list[Callback]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callback) -> None:
        """Register `callback` to be called whenever `event_name` is published."""
        self._subscribers[event_name].append(callback)
        logger.debug("Subscribed %s to '%s'", getattr(callback, "__name__", callback), event_name)

    def unsubscribe(self, event_name: str, callback: Callback) -> None:
        """Remove a previously subscribed callback. No-op if not found."""
        if callback in self._subscribers[event_name]:
            self._subscribers[event_name].remove(callback)

    def publish(self, event_name: str, *args, **kwargs) -> None:
        """
        Call every subscriber of `event_name` with the given args.

        A single subscriber raising an exception is logged and does NOT
        stop the other subscribers from running — one broken listener
        (e.g. a flaky websocket) should never block core things like DB
        persistence from happening.
        """
        for callback in list(self._subscribers.get(event_name, [])):
            try:
                callback(*args, **kwargs)
            except Exception:
                logger.exception(
                    "Subscriber %s raised while handling '%s' — continuing with other subscribers",
                    getattr(callback, "__name__", callback), event_name,
                )

    def subscriber_count(self, event_name: str) -> int:
        return len(self._subscribers.get(event_name, []))
