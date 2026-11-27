"""LIVE DeltaChat transport test — SCAFFOLD.

Exercises the *real* DeltaChat side of the bridge: a genuine configure +
send/receive loop against a live email / chatmail account over IMAP/SMTP using
the real ``deltachat`` (libdeltachat) library. This is the half that
``test_bridge_hivemind_e2e.py`` deliberately mocks out.

It is a **scaffold**: it reads credentials from the environment and SKIPS
cleanly (never fails, never errors) when they are absent, so the default CI run
stays network-free. Provide credentials to run it for real.

Environment variables
----------------------
    DELTACHAT_ADDR        (required)  the bot account's email address
    DELTACHAT_PASSWORD    (required)  the bot account's IMAP/SMTP password
                                      (an app password / chatmail password)
    DELTACHAT_PEER_ADDR   (optional)  a second account to exchange a message
                                      with for a full send -> receive loop
    DELTACHAT_PEER_PASSWORD (optional) the second account's password

With only ADDR + PASSWORD the test verifies a real ``configure()`` succeeds
(the account can actually log in to IMAP/SMTP). With a PEER_ADDR (and ideally
PEER_PASSWORD) it additionally drives a real outbound message and, when the
peer creds are present, asserts the message is received on the other side —
the genuine DeltaChat round-trip the user will supply creds for.

Run::

    DELTACHAT_ADDR=bot@chat.example DELTACHAT_PASSWORD=... \
        pytest tests/e2e/test_deltachat_live.py -v
"""
import os
import time
from os.path import join
from tempfile import mkdtemp

import pytest

_ADDR = os.environ.get("DELTACHAT_ADDR")
_PASSWORD = os.environ.get("DELTACHAT_PASSWORD")
_PEER_ADDR = os.environ.get("DELTACHAT_PEER_ADDR")
_PEER_PASSWORD = os.environ.get("DELTACHAT_PEER_PASSWORD")

# Skip the entire module unless live credentials are supplied. This keeps the
# default (offline) CI run green while letting the user opt in with real creds.
pytestmark = pytest.mark.skipif(
    not (_ADDR and _PASSWORD),
    reason="DELTACHAT_ADDR / DELTACHAT_PASSWORD not set — live DeltaChat test "
           "skipped (set them to run the real IMAP/SMTP loop)",
)


def _configure_account(addr, password):
    """Create and configure a real deltachat Account; return it started.

    Imports deltachat lazily so import errors surface only when the test
    actually runs (it is skip-gated above), not at collection time.
    """
    from deltachat import Account

    db = join(mkdtemp(prefix="dc_live_"), "account.db")
    acc = Account(db)
    acc.set_config("addr", addr)
    acc.set_config("mail_pw", password)
    acc.set_config("mvbox_move", "0")
    acc.set_config("sentbox_watch", "0")
    tracker = acc.configure()
    tracker.wait_finish()  # raises if login (IMAP/SMTP) fails
    assert acc.is_configured(), f"deltachat could not configure {addr}"
    acc.start_io()
    return acc


def test_live_configure():
    """The bot account can really log in to its IMAP/SMTP server."""
    acc = _configure_account(_ADDR, _PASSWORD)
    try:
        assert acc.get_config("configured_addr") == _ADDR
    finally:
        acc.shutdown()


@pytest.mark.skipif(
    not _PEER_ADDR,
    reason="DELTACHAT_PEER_ADDR not set — send/receive loop skipped",
)
def test_live_send_receive():
    """Real send -> receive loop between the bot and a peer account.

    Sends an outbound message from the bot to the peer. When the peer's
    password is also supplied, configures the peer too and waits for the
    message to actually arrive over IMAP — the complete DeltaChat transport
    round-trip.
    """
    import deltachat

    bot = _configure_account(_ADDR, _PASSWORD)
    peer = None
    try:
        token = f"hm-bridge-live-{int(time.time())}"

        bot_chat = bot.create_chat(_PEER_ADDR)
        bot_chat.send_text(token)

        if not _PEER_PASSWORD:
            pytest.skip("DELTACHAT_PEER_PASSWORD not set — sent the message but "
                        "cannot verify receipt on the peer side")

        peer = _configure_account(_PEER_ADDR, _PEER_PASSWORD)

        deadline = time.time() + 120  # email delivery can be slow
        received = None
        while time.time() < deadline and received is None:
            for chat in peer.get_chats():
                for msg in chat.get_messages():
                    if msg.text == token:
                        received = msg
                        break
                if received:
                    break
            if received is None:
                time.sleep(2)

        assert received is not None, (
            f"peer {_PEER_ADDR} did not receive the message within the timeout"
        )
        assert received.text == token
    finally:
        bot.shutdown()
        if peer is not None:
            peer.shutdown()
