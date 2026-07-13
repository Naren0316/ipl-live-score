"""
test_event_bus.py
------------------
Run with:
    python3 -m unittest test_event_bus.py -v
"""

import unittest

from event_bus import EventBus


class TestEventBus(unittest.TestCase):

    def setUp(self) -> None:
        self.bus = EventBus()

    def test_subscriber_receives_published_event(self) -> None:
        received = []
        self.bus.subscribe("new_ball", lambda ball: received.append(ball))

        self.bus.publish("new_ball", "ball-data")

        self.assertEqual(received, ["ball-data"])

    def test_multiple_subscribers_all_run(self) -> None:
        calls = []
        self.bus.subscribe("new_ball", lambda b: calls.append(("printer", b)))
        self.bus.subscribe("new_ball", lambda b: calls.append(("db", b)))
        self.bus.subscribe("new_ball", lambda b: calls.append(("websocket", b)))

        self.bus.publish("new_ball", "over_5.3")

        self.assertEqual(len(calls), 3)
        self.assertIn(("printer", "over_5.3"), calls)
        self.assertIn(("db", "over_5.3"), calls)
        self.assertIn(("websocket", "over_5.3"), calls)

    def test_subscribers_called_in_subscription_order(self) -> None:
        order = []
        self.bus.subscribe("event", lambda: order.append(1))
        self.bus.subscribe("event", lambda: order.append(2))
        self.bus.subscribe("event", lambda: order.append(3))

        self.bus.publish("event")

        self.assertEqual(order, [1, 2, 3])

    def test_publish_with_no_subscribers_does_not_raise(self) -> None:
        self.bus.publish("nobody_listening", "data")  # should just do nothing

    def test_unsubscribe_stops_further_calls(self) -> None:
        received = []

        def handler(x):
            received.append(x)

        self.bus.subscribe("new_ball", handler)
        self.bus.publish("new_ball", "first")
        self.bus.unsubscribe("new_ball", handler)
        self.bus.publish("new_ball", "second")

        self.assertEqual(received, ["first"])

    def test_one_broken_subscriber_does_not_block_others(self) -> None:
        results = []

        def broken_subscriber(x):
            raise ValueError("simulated websocket failure")

        def working_subscriber(x):
            results.append(x)

        self.bus.subscribe("new_ball", broken_subscriber)
        self.bus.subscribe("new_ball", working_subscriber)

        self.bus.publish("new_ball", "runs=4")  # must not raise out of publish()

        self.assertEqual(results, ["runs=4"])

    def test_events_are_isolated_by_name(self) -> None:
        ball_events = []
        wicket_events = []
        self.bus.subscribe("new_ball", lambda b: ball_events.append(b))
        self.bus.subscribe("wicket", lambda b: wicket_events.append(b))

        self.bus.publish("new_ball", "b1")

        self.assertEqual(ball_events, ["b1"])
        self.assertEqual(wicket_events, [])

    def test_subscriber_count(self) -> None:
        self.bus.subscribe("new_ball", lambda: None)
        self.bus.subscribe("new_ball", lambda: None)

        self.assertEqual(self.bus.subscriber_count("new_ball"), 2)
        self.assertEqual(self.bus.subscriber_count("unknown_event"), 0)


if __name__ == "__main__":
    unittest.main()
