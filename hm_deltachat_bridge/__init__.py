"""HiveMind ⇄ DeltaChat bridge.

Composition design (replaces the previous inheritance-based bridge):

- :class:`hm_deltachat_bridge.deltabot.DeltaChatBot` — wraps the classic
  ``deltachat`` Python library, runs its blocking ``account.wait_shutdown()``
  on a daemon thread, fires ``handle_utterance(text, addr)`` from
  the deltachat library's internal thread when a chat message arrives.
- :class:`AsyncHiveMessageBusClient` — asyncio-native HiveMind client
  (``hivemind-bus-client[async]>=0.8.0``). Runs on the application's
  event loop.
- :class:`HiveMindDeltaChatBridge` — composes the two. The deltachat
  callback (which fires on the deltachat thread) is bridged onto the
  asyncio loop with :func:`asyncio.run_coroutine_threadsafe`; the
  HiveMind ``speak`` handler runs on the receive task and calls
  ``DeltaChatBot.speak`` directly (the deltachat client library is
  thread-safe for the calls we use).

This removes the previous architecture's *second* thread (the sync
``HiveMessageBusClient.run_in_thread``). One thread remains — the
deltachat library's own — because the classic ``deltachat`` package is
fundamentally callback-based and not asyncio-aware. Migrating to
``deltachat-rpc-client`` (async-first) is a separate, larger change
that would also drop that thread.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from hivemind_bus_client.async_client import AsyncHiveMessageBusClient
from hivemind_bus_client.identity import NodeIdentity
from ovos_bus_client.message import Message
from ovos_utils.log import LOG

from hm_deltachat_bridge.deltabot import DeltaChatBot
from hm_deltachat_bridge.version import __version__


class HiveMindDeltaChatBridge:
    """Bridge between a DeltaChat account and a HiveMind hub.

    Typical usage from an asyncio entry point::

        bridge = HiveMindDeltaChatBridge(
            email="user@example.com",
            email_password="...",
            identity=NodeIdentity(),
        )
        await bridge.start()
        try:
            await stop_event.wait()
        finally:
            await bridge.stop()

    For DI in tests, pass a pre-built ``client`` (any object matching the
    :class:`AsyncHiveMessageBusClient` surface — including
    ``hivemind_bus_client.fakebus.AsyncFakeHiveMessageBus``) and/or a
    pre-built ``bot``.
    """

    platform = "HiveMindDeltaChatBridgeV0.2"

    def __init__(self,
                 email: Optional[str] = None,
                 email_password: Optional[str] = None,
                 key: Optional[str] = None,
                 password: Optional[str] = None,
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 identity: Optional[NodeIdentity] = None,
                 *,
                 client: Optional[AsyncHiveMessageBusClient] = None,
                 bot: Optional[DeltaChatBot] = None):
        self.bot = bot or DeltaChatBot(email=email, password=email_password)
        self.client = client or AsyncHiveMessageBusClient(
            key=key,
            password=password,
            host=host,
            port=port,
            useragent=self.platform,
            identity=identity,
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._started = False

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Wire deltachat -> asyncio bridge, connect to HiveMind, start bot."""
        if self._started:
            return
        self._loop = asyncio.get_running_loop()
        self.bot.handle_utterance = self._on_delta_utterance
        self.bot.start()
        LOG.info("== connected to DeltaChat")

        await self.client.connect(site_id="deltachat")
        # speak events on the OVOS bus carry the deltachat_addr we tagged
        # on the outbound utterance; route them back to deltachat.
        self.client.on_mycroft("speak", self._on_speak)
        LOG.info("== connected to HiveMind")
        self._started = True

    async def stop(self) -> None:
        """Shutdown bot, close HiveMind connection. Idempotent."""
        if not self._started:
            return
        try:
            self.client.remove("speak", self._on_speak)
        except Exception:
            pass
        try:
            self.bot.stop()
        except Exception:
            LOG.exception("error stopping DeltaChat bot")
        try:
            await self.client.close()
        except Exception:
            LOG.exception("error closing HiveMind client")
        self._started = False

    # ------------------------------------------------------------------
    # deltachat -> HiveMind (callback runs on deltachat lib thread)
    # ------------------------------------------------------------------

    def _on_delta_utterance(self, utterance: str, addr: str) -> None:
        """Bridge the deltachat-thread callback onto the asyncio loop.

        ``asyncio.run_coroutine_threadsafe`` is the documented way to
        schedule an awaitable from a non-loop thread — it returns
        immediately; the loop runs the coroutine on its next pass.
        """
        if self._loop is None or self._loop.is_closed():
            LOG.warning("got deltachat utterance before bridge started; dropping")
            return
        LOG.debug(f"asking hivemind: {utterance}")
        # TODO - language detection here
        coro = self.client.emit_mycroft(
            Message("recognizer_loop:utterance",
                    {"utterances": [utterance]},
                    {"deltachat_addr": addr})
        )
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    # ------------------------------------------------------------------
    # HiveMind -> deltachat (handler runs on the asyncio receive task)
    # ------------------------------------------------------------------

    def _on_speak(self, message) -> None:
        """OVOS ``speak`` message arrived from HiveMind. Forward to deltachat.

        ``self.bot.speak`` is the synchronous deltachat library call to
        ``chat.send_text``. We are already on the asyncio loop here, but the
        deltachat library is thread-safe for send_text so calling it sync
        from a loop handler is fine — no need to offload to a thread pool.
        """
        utterance = message.data.get("utterance")
        addr = message.context.get("deltachat_addr")
        if not addr:
            LOG.error("got speak message without deltachat_addr")
            return
        LOG.info(f"HiveMind {addr} : {utterance}")
        try:
            self.bot.speak(utterance, addr)
        except Exception:
            LOG.exception(f"failed to forward speak to deltachat addr={addr}")
