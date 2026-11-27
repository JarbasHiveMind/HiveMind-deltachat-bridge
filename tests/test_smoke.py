"""Smoke tests: import the package, check the version, and construct the bridge
with the DeltaChat account and the HiveMind bus connection mocked out so no live
DeltaChat/HiveMind connection is ever opened.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import hm_deltachat_bridge
from hm_deltachat_bridge import HiveMindDeltaChatBridge, __version__


def test_package_version():
    assert isinstance(__version__, str)
    assert __version__
    # version.py and the package re-export agree
    assert hm_deltachat_bridge.version.__version__ == __version__


def test_console_entrypoint_importable():
    # the entry point declared in pyproject.toml must resolve to a real callable
    from hm_deltachat_bridge.__main__ import launch_bot
    assert callable(launch_bot)


def _fake_client():
    """An object exposing the AsyncHiveMessageBusClient surface the bridge uses."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.emit_mycroft = AsyncMock()
    return client


def test_construct_and_start_bridge_with_mocked_bus():
    """Construct + start/stop the bridge without touching DeltaChat or a HiveMind server.

    HiveMindDeltaChatBridge composes a DeltaChatBot (live email account) and an
    AsyncHiveMessageBusClient. Both are injected as mocks so nothing reaches the
    network.
    """
    bot_instance = MagicMock()
    client = _fake_client()

    bridge = HiveMindDeltaChatBridge(bot=bot_instance, client=client)

    async def scenario():
        await bridge.start()
        # the bot was started and the bridge wired its delta handler onto it
        bot_instance.start.assert_called_once()
        assert bot_instance.handle_utterance == bridge._on_delta_utterance
        # connect() was invoked (mocked, no socket opened) and the speak
        # handler registered
        client.connect.assert_awaited_once()
        client.on_mycroft.assert_called_once_with("speak", bridge._on_speak)

        # stop() delegates to the bot and closes the HiveMind client
        await bridge.stop()
        bot_instance.stop.assert_called_once()
        client.close.assert_awaited_once()

    asyncio.run(scenario())


def test_default_construction_builds_bot_and_client():
    """Without DI the bridge builds a DeltaChatBot and an AsyncHiveMessageBusClient."""
    with patch("hm_deltachat_bridge.DeltaChatBot") as MockBot, \
            patch("hm_deltachat_bridge.AsyncHiveMessageBusClient") as MockClient:
        bot_instance = MagicMock()
        MockBot.return_value = bot_instance

        bridge = HiveMindDeltaChatBridge(
            email="bot@example.org",
            email_password="hunter2",
            key="testkey",
            host="ws://127.0.0.1",
            port=5678,
            password="testpassword",
        )

        MockBot.assert_called_once_with(email="bot@example.org",
                                        password="hunter2")
        MockClient.assert_called_once()
        kwargs = MockClient.call_args.kwargs
        assert kwargs["key"] == "testkey"
        assert kwargs["host"] == "ws://127.0.0.1"
        assert kwargs["port"] == 5678
        assert kwargs["password"] == "testpassword"
        # the bot is created but NOT started at construction time
        bot_instance.start.assert_not_called()
        assert bridge.bot is bot_instance


def test_on_delta_utterance_emits_mycroft():
    """_on_delta_utterance should emit a recognizer_loop:utterance carrying the addr."""
    client = _fake_client()
    bridge = HiveMindDeltaChatBridge(bot=MagicMock(), client=client)

    async def scenario():
        await bridge.start()
        bridge._on_delta_utterance("hello world", "user@example.org")
        # the emit is scheduled with run_coroutine_threadsafe; yield to the
        # loop until it runs
        for _ in range(50):
            if client.emit_mycroft.await_count:
                break
            await asyncio.sleep(0.01)
        client.emit_mycroft.assert_awaited_once()
        msg = client.emit_mycroft.await_args.args[0]
        assert msg.msg_type == "recognizer_loop:utterance"
        assert msg.data["utterances"] == ["hello world"]
        assert msg.context["deltachat_addr"] == "user@example.org"
        await bridge.stop()

    asyncio.run(scenario())
