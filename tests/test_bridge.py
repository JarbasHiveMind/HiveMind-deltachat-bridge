"""Tests for HiveMindDeltaChatBridge.

We don't stand up a real DeltaChat account or a real HiveMind hub:

- The HiveMind client is replaced with ``AsyncFakeHiveMessageBus`` from
  ``hivemind-bus-client`` so emit + on_mycroft + close behave exactly
  like the real async client without a WebSocket.
- The DeltaChat bot is replaced with ``_StubBot`` so we can directly
  fire the "incoming utterance" callback from a test, and assert that
  outbound speak messages were routed back to it.

Together these exercise the bridge's actual job: wire the two clients
together correctly, with the threading bridge (deltachat thread →
asyncio loop) intact.
"""
from __future__ import annotations

import asyncio
import threading
import unittest
from unittest.mock import MagicMock

from hivemind_bus_client.fakebus import AsyncFakeHiveMessageBus
from hivemind_bus_client.message import HiveMessage, HiveMessageType
from ovos_bus_client.message import Message

from hm_deltachat_bridge import HiveMindDeltaChatBridge


class _StubBot:
    """Stand-in for DeltaChatBot. Records ``speak`` calls; exposes a hook
    to simulate an incoming chat message from any thread."""

    def __init__(self):
        self.handle_utterance = None  # set by bridge.start()
        self.started = False
        self.stopped = False
        self.spoken: list[tuple[str, str]] = []  # (utterance, addr)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def speak(self, utterance: str, addr: str):
        self.spoken.append((utterance, addr))

    def fire_incoming(self, utterance: str, addr: str, *, from_thread: bool = False):
        """Simulate a deltachat 'message arrived' callback.

        When ``from_thread=True``, fires the callback from a separate
        thread so the bridge's ``asyncio.run_coroutine_threadsafe`` path
        is exercised exactly as in production.
        """
        cb = self.handle_utterance
        assert cb is not None, "bridge.start() not called yet"
        if from_thread:
            done = threading.Event()

            def _go():
                cb(utterance, addr)
                done.set()

            threading.Thread(target=_go, daemon=True).start()
            done.wait(timeout=2)
        else:
            cb(utterance, addr)


def _make_bridge() -> HiveMindDeltaChatBridge:
    return HiveMindDeltaChatBridge(
        client=AsyncFakeHiveMessageBus(site_id="test-deltachat"),
        bot=_StubBot(),
    )


def _run(coro):
    return asyncio.run(coro)


class TestLifecycle(unittest.TestCase):
    def test_start_idempotent(self):
        bridge = _make_bridge()

        async def scenario():
            await bridge.start()
            self.assertTrue(bridge._started)
            self.assertTrue(bridge.bot.started)
            self.assertTrue(bridge.client.connected_event.is_set())
            # second start is a no-op
            await bridge.start()
            await bridge.stop()

        _run(scenario())
        self.assertTrue(bridge.bot.stopped)
        self.assertFalse(bridge.client.connected_event.is_set())

    def test_stop_idempotent_and_before_start(self):
        bridge = _make_bridge()
        # stop before start is a no-op
        _run(bridge.stop())
        self.assertFalse(bridge.bot.stopped)


class TestDeltachatToHivemind(unittest.TestCase):
    def test_incoming_dm_is_forwarded_as_utterance(self):
        bridge = _make_bridge()

        async def scenario():
            await bridge.start()
            try:
                # callback fires from the deltachat lib thread in production —
                # use the from_thread path to match
                bridge.bot.fire_incoming(
                    "what time is it", "alice@example.com",
                    from_thread=True,
                )
                # give the loop a tick to pick up the scheduled coroutine
                await asyncio.sleep(0.05)
            finally:
                await bridge.stop()

        _run(scenario())

        emitted = bridge.client.emitted
        self.assertEqual(len(emitted), 1)
        env = emitted[0]
        self.assertEqual(env.msg_type, HiveMessageType.BUS)
        self.assertEqual(env.payload.msg_type, "recognizer_loop:utterance")
        self.assertEqual(env.payload.data["utterances"], ["what time is it"])
        self.assertEqual(env.payload.context["deltachat_addr"], "alice@example.com")

    def test_incoming_from_thread_uses_run_coroutine_threadsafe(self):
        """Exercise the real deltachat-thread -> asyncio-loop bridge path."""
        bridge = _make_bridge()

        async def scenario():
            await bridge.start()
            try:
                bridge.bot.fire_incoming(
                    "hello from another thread",
                    "bob@example.com",
                    from_thread=True,
                )
                # Give the loop a moment to pick up the scheduled coroutine.
                # asyncio.sleep(0.05) is enough — run_coroutine_threadsafe is
                # essentially loop.call_soon_threadsafe.
                await asyncio.sleep(0.05)
            finally:
                await bridge.stop()

        _run(scenario())

        emitted = bridge.client.emitted
        self.assertEqual(len(emitted), 1)
        self.assertEqual(
            emitted[0].payload.data["utterances"],
            ["hello from another thread"],
        )

    def test_callback_before_start_drops_message(self):
        bridge = _make_bridge()
        # don't call start(); manually fire the callback. It must not crash.
        bridge._on_delta_utterance("orphan", "ghost@example.com")
        self.assertEqual(bridge.client.emitted, [])


class TestHivemindToDeltachat(unittest.TestCase):
    def test_speak_is_routed_to_bot_speak(self):
        bridge = _make_bridge()

        async def scenario():
            await bridge.start()
            try:
                # Simulate a HiveMind reply: a BUS HiveMessage carrying a
                # speak payload addressed to the original deltachat sender.
                speak = Message(
                    "speak",
                    {"utterance": "it is 9am"},
                    {"deltachat_addr": "alice@example.com"},
                )
                # The bridge listens on the internal Mycroft bus via on_mycroft;
                # AsyncFakeHiveMessageBus.emit() dispatches Mycroft messages to
                # the internal bus before the hive emitter, so emitting the BUS
                # envelope drives the same code path as a real reply.
                await bridge.client.emit(speak)
            finally:
                await bridge.stop()

        _run(scenario())
        self.assertEqual(
            bridge.bot.spoken,
            [("it is 9am", "alice@example.com")],
        )

    def test_speak_without_addr_is_logged_and_dropped(self):
        bridge = _make_bridge()

        async def scenario():
            await bridge.start()
            try:
                # speak with no deltachat_addr — bridge must log + ignore
                speak = Message("speak", {"utterance": "orphan reply"})
                await bridge.client.emit(speak)
            finally:
                await bridge.stop()

        _run(scenario())
        self.assertEqual(bridge.bot.spoken, [])

    def test_bot_speak_exception_does_not_crash_handler(self):
        bridge = _make_bridge()
        bridge.bot.speak = MagicMock(side_effect=RuntimeError("boom"))

        async def scenario():
            await bridge.start()
            try:
                await bridge.client.emit(
                    Message("speak",
                            {"utterance": "boom"},
                            {"deltachat_addr": "x@y"})
                )
            finally:
                await bridge.stop()

        # must not raise
        _run(scenario())


class TestRoundTrip(unittest.TestCase):
    def test_dm_in_speak_out_flow(self):
        bridge = _make_bridge()

        async def scenario():
            await bridge.start()
            try:
                # 1. user sends a chat message (from deltachat lib thread —
                # exercise the real run_coroutine_threadsafe path)
                bridge.bot.fire_incoming(
                    "what time is it", "alice@example.com",
                    from_thread=True,
                )
                await asyncio.sleep(0.05)

                # bridge forwarded as recognizer_loop:utterance
                self.assertEqual(len(bridge.client.emitted), 1)

                # 2. HiveMind hub answers with a speak
                await bridge.client.emit(
                    Message("speak",
                            {"utterance": "it is 9am"},
                            {"deltachat_addr": "alice@example.com"})
                )

                # bridge sent it back to deltachat
                self.assertEqual(
                    bridge.bot.spoken,
                    [("it is 9am", "alice@example.com")],
                )
            finally:
                await bridge.stop()

        _run(scenario())


if __name__ == "__main__":
    unittest.main()
