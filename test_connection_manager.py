"""
test_connection_manager.py
----------------------------
Tests ConnectionManager without needing a real server or real websockets —
uses a small fake WebSocket that records what it was sent.

Run with:
    python3 -m unittest test_connection_manager.py -v
"""

import unittest

from connection_manager import ConnectionManager


class FakeWebSocket:
    """Minimal stand-in for fastapi.WebSocket — just enough for our tests."""

    def __init__(self, name: str, fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.sent: list[str] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, message: str) -> None:
        if self.fail:
            raise ConnectionError(f"{self.name} connection is dead")
        self.sent.append(message)


class TestConnectionManager(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.manager = ConnectionManager()

    async def test_connect_accepts_and_tracks_client(self) -> None:
        ws = FakeWebSocket("client1")
        await self.manager.connect(ws)

        self.assertTrue(ws.accepted)
        self.assertEqual(self.manager.connection_count(), 1)

    async def test_broadcast_sends_to_all_connected_clients(self) -> None:
        ws1 = FakeWebSocket("client1")
        ws2 = FakeWebSocket("client2")
        await self.manager.connect(ws1)
        await self.manager.connect(ws2)

        await self.manager.broadcast("ball update")

        self.assertEqual(ws1.sent, ["ball update"])
        self.assertEqual(ws2.sent, ["ball update"])

    async def test_disconnect_removes_client(self) -> None:
        ws = FakeWebSocket("client1")
        await self.manager.connect(ws)
        self.manager.disconnect(ws)

        self.assertEqual(self.manager.connection_count(), 0)

    async def test_disconnect_unknown_client_does_not_raise(self) -> None:
        ws = FakeWebSocket("never connected")
        self.manager.disconnect(ws)  # should not raise

    async def test_broadcast_drops_dead_connection_but_reaches_others(self) -> None:
        alive = FakeWebSocket("alive")
        dead = FakeWebSocket("dead", fail=True)
        await self.manager.connect(alive)
        await self.manager.connect(dead)

        await self.manager.broadcast("hello")

        self.assertEqual(alive.sent, ["hello"])
        # dead client should have been automatically removed
        self.assertEqual(self.manager.connection_count(), 1)


if __name__ == "__main__":
    unittest.main()
