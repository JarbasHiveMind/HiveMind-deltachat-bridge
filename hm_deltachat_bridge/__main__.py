"""CLI entry point — asyncio main with signal-driven shutdown."""
from __future__ import annotations

import asyncio
import signal

import click
from hivemind_bus_client.identity import NodeIdentity
from ovos_utils.log import LOG

from hm_deltachat_bridge import HiveMindDeltaChatBridge

LOG.set_level("DEBUG")


async def _amain(email: str, email_password: str,
                 key: str, password: str, host: str, port: int) -> None:
    identity = NodeIdentity()
    password = password or identity.password
    key = key or identity.access_key
    host = host or identity.default_master

    if host and not host.startswith("ws://") and not host.startswith("wss://"):
        host = "ws://" + host

    if not key or not password or not host:
        raise RuntimeError(
            "NodeIdentity not set, please pass key/password/host or "
            "call 'hivemind-client set-identity'"
        )

    bridge = HiveMindDeltaChatBridge(
        email=email, email_password=email_password,
        key=key, host=host, port=port, password=password,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler; let KeyboardInterrupt fall through.
            pass

    await bridge.start()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await bridge.stop()


# TODO - allowed emails option
@click.command()
@click.option("--email", help="deltachat email", type=str)
@click.option("--email-password", help="deltachat email password", type=str)
@click.option("--key", help="HiveMind access key (default read from identity file)",
              type=str, default="")
@click.option("--password", help="HiveMind password (default read from identity file)",
              type=str, default="")
@click.option("--host", help="HiveMind host (default read from identity file)",
              type=str, default="")
@click.option("--port", help="HiveMind port number (default: 5678)", type=int, default=5678)
def launch_bot(email: str, email_password: str,
               key: str, password: str, host: str, port: int) -> None:
    asyncio.run(_amain(email, email_password, key, password, host, port))


if __name__ == "__main__":
    launch_bot()
