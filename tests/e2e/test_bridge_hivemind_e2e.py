"""REAL HiveMind-side end-to-end test for the DeltaChat bridge.

This exercises the bridge's **real** HiveMind code path against a **real**
hivemind-core hub:

    inbound DeltaChat message
        -> DeltaChatBot.ac_incoming_message  (real bridge bot logic)
        -> bridge.handle_delta_utterance     (real bridge method)
        -> emit_mycroft(recognizer_loop:utterance)  -> real WebSocket
        -> hivemind-core hub  -> agent bus
        -> responding agent emits `speak` back to the originating peer
        -> real WebSocket -> bridge.internal_bus
        -> bridge.handle_incoming_mycroft     (real bridge method)
        -> bot.speak(utterance, addr)         -> chat.send_text  (captured)

Everything between ``emit_mycroft`` and ``handle_incoming_mycroft`` is the
genuine production HiveMessageBusClient + hivemind-core stack over a localhost
WebSocket (hivescope's loopback hub). Only the DeltaChat *transport* is mocked:
the ``deltachat`` library is never imported and no email/chatmail account is
needed. The mock captures the bridge's outbound ``chat.send_text`` so the
round-trip can be asserted end to end.

A real DeltaChat IMAP/SMTP loop (configure + send/receive against a live
account) is a separate test — see ``test_deltachat_live.py``.

Reference (HiveMind harness):
    hivemind-test-harness/tests/test_hivemind_bus_client_e2e.py
        add_master("M0", use_loopback=True);
        register_satellite(key, password=..., allowed_types=[...])
    hivemind-test-harness/tests/test_cascade.py
        responder on master.agent_protocol.bus.on("recognizer_loop:utterance")
"""
import sys
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest
from ovos_bus_client.message import Message

from hivescope.topology import TopologyBuilder


# ---------------------------------------------------------------------------
# Mock the `deltachat` library BEFORE importing the bridge package.
#
# We do NOT importorskip — the deltachat lib drives native libdeltachat and
# needs a live email account, which has no place in a HiveMind-side e2e. We
# install an explicit stand-in module so `import deltachat` resolves to a fake
# that still lets the bridge's REAL DeltaChatBot logic run (the @account_hookimpl
# decorator and Account class are stubbed; the bot's incoming-message handling
# and `speak` routing are the bridge's own real code).
# ---------------------------------------------------------------------------

def _install_fake_deltachat():
    """Register a fake `deltachat` module on sys.modules.

    Provides just enough surface for `hm_deltachat_bridge.deltabot` to import
    and for DeltaChatBot to construct without a live account:
      - account_hookimpl: a no-op pass-through decorator
      - Account: a MagicMock factory whose configure().wait_finish() is a no-op
    """
    fake = ModuleType("deltachat")

    def account_hookimpl(func=None, **kwargs):
        # deltachat uses pluggy-style markers; as a decorator it must return the
        # function unchanged so the bound method stays callable.
        if func is None:
            def _wrap(f):
                return f
            return _wrap
        return func

    class _FakeAccount:
        def __init__(self, db):
            self.db = db
            self._config = {}

        def set_config(self, k, v):
            self._config[k] = v

        def get_config(self, k):
            return self._config.get(k)

        def configure(self):
            tracker = MagicMock()
            tracker.wait_finish.return_value = None
            return tracker

        def add_account_plugin(self, plugin):
            pass

        def start_io(self):
            pass

        def wait_shutdown(self):
            pass

        def shutdown(self):
            pass

    fake.account_hookimpl = account_hookimpl
    fake.Account = _FakeAccount
    sys.modules["deltachat"] = fake
    return fake


_install_fake_deltachat()

# Import the bridge AFTER the fake deltachat is registered.
from hm_deltachat_bridge import HiveMindDeltaChatBridge  # noqa: E402
from hm_deltachat_bridge.deltabot import DeltaChatBot  # noqa: E402


# ---------------------------------------------------------------------------
# A fake inbound DeltaChat message + chat, so we can drive the bridge bot's
# REAL ac_incoming_message handler and capture the outbound send_text.
# ---------------------------------------------------------------------------

class _CapturingChat:
    """Stand-in for a deltachat Chat — captures send_text calls."""

    def __init__(self):
        self.sent = []

    def send_text(self, text):
        self.sent.append(text)


def _make_inbound_message(text, sender_addr, chat):
    """Build a fake inbound deltachat Message object.

    Mirrors the attributes the bridge's DeltaChatBot.ac_incoming_message reads:
      - is_system_message()
      - get_sender_contact().addr
      - create_chat() -> assigns .chat
      - .text
    """
    contact = SimpleNamespace(addr=sender_addr)
    msg = MagicMock()
    msg.is_system_message.return_value = False
    msg.get_sender_contact.return_value = contact
    msg.create_chat.return_value = chat
    # the real handler reads message.chat after create_chat()
    msg.chat = chat
    msg.text = text
    return msg


def _extract_host_port(url: str):
    parts = url.replace("ws://", "").replace("wss://", "").rstrip("/").split(":")
    return parts[0], int(parts[1])


def _make_bridge(url, key, password, bot):
    """Construct the REAL bridge wired to the loopback hub, reusing `bot`.

    HiveMindDeltaChatBridge.__init__ builds its own DeltaChatBot and calls
    super().__init__()/connect(). We patch DeltaChatBot construction to return
    our prepared bot instance so the inbound/outbound DeltaChat side is the
    fake transport, while the HiveMessageBusClient + connect() are 100% real.
    """
    host, port = _extract_host_port(url)
    return HiveMindDeltaChatBridge(
        email="bot@example.org",
        email_password="hunter2",
        key=key,
        password=password,
        host=f"ws://{host}",
        port=port,
        useragent="dc-bridge-e2e",
        self_signed=False,
    )


def test_deltachat_to_hivemind_roundtrip(monkeypatch):
    """Full round-trip: DeltaChat in -> HiveMind hub -> DeltaChat out.

    Proves the bridge relays a user's DeltaChat utterance to a real hub, the
    hub's agent answers, and the bridge delivers the answer back to the right
    DeltaChat chat.
    """
    inbound_text = "what is the weather?"
    reply_text = "it is sunny"
    user_addr = "alice@example.org"

    # --- build the REAL hub (loopback websocket) + a responding agent --------
    b = TopologyBuilder()
    m = b.add_master("M0", use_loopback=True)
    # whitelist-only ACL: grant the only type the bridge injects.
    m.register_satellite("dc-key", password="dc-password",
                         allowed_types=["recognizer_loop:utterance"])
    b.start_all()

    bridge = None
    try:
        # Responder on the hub's agent bus. When the bridge's utterance lands on
        # the agent bus it carries `deltachat_addr` in context and `source`/`peer`
        # set to the bridge's peer id (hivemind-core stamps these). We answer with
        # a `speak` routed back to that peer (destination=peer) and echo
        # `deltachat_addr` so the bridge can target the right chat.
        agent_bus = m.agent_protocol.bus

        def _responder(msg):
            if isinstance(msg, str):
                msg = Message.deserialize(msg)
            addr = msg.context.get("deltachat_addr")
            peer = msg.context.get("source") or msg.context.get("peer")
            agent_bus.emit(Message(
                "speak",
                {"utterance": reply_text},
                {"deltachat_addr": addr, "destination": [peer]},
            ))

        agent_bus.on("recognizer_loop:utterance", _responder)

        # --- prepare the bridge's DeltaChat bot (fake transport) -------------
        # Use the bridge's REAL DeltaChatBot class (its ac_incoming_message and
        # speak() are the genuine bridge logic); only the deltachat lib under it
        # is faked. We construct it ourselves and hand it to the bridge.
        bot = DeltaChatBot(email="bot@example.org", password="hunter2")
        monkeypatch.setattr("hm_deltachat_bridge.DeltaChatBot",
                            lambda *a, **k: bot)
        # don't spin real IO threads
        bot.start = MagicMock()

        url = m.network_protocol.url
        bridge = _make_bridge(url, "dc-key", "dc-password", bot)
        bridge.wait_for_handshake(timeout=10)
        assert bridge.handshake_event.is_set(), "bridge handshake did not complete"
        time.sleep(1)  # let the encrypted HELLO register the peer
        assert len(m.connected_peers()) == 1, \
            f"expected 1 connected peer, got {m.connected_peers()}"

        # --- inject a REAL inbound DeltaChat event ---------------------------
        # Drive the bridge bot's genuine ac_incoming_message handler with a
        # fake inbound deltachat Message. This calls handle_utterance, which the
        # bridge wired to handle_delta_utterance -> emit_mycroft. The outbound
        # reply is captured on this chat's send_text.
        chat = _CapturingChat()
        inbound = _make_inbound_message(inbound_text, user_addr, chat)
        bot.ac_incoming_message(inbound)

        # --- wait for the round-trip -----------------------------------------
        deadline = time.time() + 10
        while time.time() < deadline and not chat.sent:
            time.sleep(0.1)

        assert chat.sent, (
            "no outbound DeltaChat message captured — the round-trip did not "
            "complete (DeltaChat in -> hub agent -> DeltaChat out)"
        )
        assert chat.sent[0] == reply_text, \
            f"wrong reply delivered to DeltaChat: {chat.sent!r}"

        # The hub's agent bus actually received the utterance the user typed.
        m.agent_protocol.assert_injected("recognizer_loop:utterance", count=1)
        injected = m.agent_protocol.last_injected("recognizer_loop:utterance")
        assert injected.data["utterances"] == [inbound_text]
        assert injected.context.get("deltachat_addr") == user_addr

        # And the reply was sent to *that* user's chat, not some other.
        assert bot.addr2chat[user_addr] is chat
    finally:
        if bridge is not None:
            try:
                bridge.close()
            except Exception:
                pass
        b.stop_all()


def test_unanswered_utterance_sends_nothing(monkeypatch):
    """If the hub agent never answers, the bridge sends no DeltaChat reply.

    Guards against a false-positive where the assertion would pass on stale
    state: with no responder registered, nothing should reach the chat.
    """
    b = TopologyBuilder()
    m = b.add_master("M0", use_loopback=True)
    m.register_satellite("dc-key2", password="dc-password2",
                         allowed_types=["recognizer_loop:utterance"])
    b.start_all()

    bridge = None
    try:
        bot = DeltaChatBot(email="bot@example.org", password="hunter2")
        monkeypatch.setattr("hm_deltachat_bridge.DeltaChatBot",
                            lambda *a, **k: bot)
        bot.start = MagicMock()

        bridge = _make_bridge(m.network_protocol.url, "dc-key2", "dc-password2", bot)
        bridge.wait_for_handshake(timeout=10)
        time.sleep(1)

        chat = _CapturingChat()
        inbound = _make_inbound_message("hello?", "bob@example.org", chat)
        bot.ac_incoming_message(inbound)

        time.sleep(2)  # give any (absent) reply time to arrive
        assert chat.sent == [], \
            f"expected no DeltaChat reply with no agent, got {chat.sent!r}"
        # the utterance did still reach the real hub agent bus
        m.agent_protocol.assert_injected("recognizer_loop:utterance", count=1)
    finally:
        if bridge is not None:
            try:
                bridge.close()
            except Exception:
                pass
        b.stop_all()
