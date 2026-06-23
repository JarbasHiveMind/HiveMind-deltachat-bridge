"""Smoke tests: import the package, check the version, and construct the bridge
with the DeltaChat account and the HiveMind bus connection mocked out so no live
DeltaChat/HiveMind connection is ever opened.
"""
from unittest.mock import MagicMock, patch

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


def test_construct_bridge_with_mocked_bus():
    """Construct the bridge without touching DeltaChat or a HiveMind server.

    HiveMindDeltaChatBridge.__init__ builds a DeltaChatBot (live email account),
    starts it, then calls the HiveMessageBusClient initializer and connect(). We
    patch the bot and the bus-client side effects so nothing reaches the network.
    """
    with patch("hm_deltachat_bridge.DeltaChatBot") as MockBot, \
            patch.object(HiveMindDeltaChatBridge, "connect", return_value=None) as mock_connect, \
            patch.object(HiveMindDeltaChatBridge, "on_mycroft", return_value=None), \
            patch("hivemind_bus_client.client.HiveMessageBusClient.__init__", return_value=None):
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

        # the bot was created and started, but no live account was configured
        MockBot.assert_called_once_with("bot@example.org", "hunter2")
        bot_instance.start.assert_called_once()
        # the bridge wired its delta handler onto the bot
        assert bot_instance.handle_utterance == bridge.handle_delta_utterance
        # connect() was invoked (mocked, no socket opened)
        mock_connect.assert_called_once()

        # stop() delegates to the bot
        bridge.stop()
        bot_instance.stop.assert_called_once()


def test_handle_delta_utterance_emits_mycroft():
    """handle_delta_utterance should emit a recognizer_loop:utterance carrying the addr."""
    with patch("hm_deltachat_bridge.DeltaChatBot") as MockBot, \
            patch.object(HiveMindDeltaChatBridge, "connect", return_value=None), \
            patch.object(HiveMindDeltaChatBridge, "on_mycroft", return_value=None), \
            patch("hivemind_bus_client.client.HiveMessageBusClient.__init__", return_value=None):
        MockBot.return_value = MagicMock()
        bridge = HiveMindDeltaChatBridge(
            email="bot@example.org", email_password="hunter2",
            key="k", host="ws://127.0.0.1", port=5678, password="p",
        )
        with patch.object(bridge, "emit_mycroft") as mock_emit:
            bridge.handle_delta_utterance("hello world", "user@example.org")
            mock_emit.assert_called_once()
            msg = mock_emit.call_args.args[0]
            assert msg.msg_type == "recognizer_loop:utterance"
            assert msg.data["utterances"] == ["hello world"]
            assert msg.context["deltachat_addr"] == "user@example.org"
