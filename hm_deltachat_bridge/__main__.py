import click
from hivemind_bus_client.identity import NodeIdentity
from ovos_utils import wait_for_exit_signal
from ovos_utils.log import LOG

from hm_deltachat_bridge import HiveMindDeltaChatBridge

LOG.set_level("DEBUG")


# TODO - allowed emails option
@click.command()
@click.option("--email", help="deltachat email", type=str)
@click.option("--email-password", help="deltachat email password", type=str)
@click.option("--key", help="HiveMind access key (default read from identity file)", type=str, default="")
@click.option("--password", help="HiveMind password (default read from identity file)", type=str, default="")
@click.option("--host", help="HiveMind host (default read from identity file)", type=str, default="")
@click.option("--port", help="HiveMind port number (default: 5678)", type=int, default=5678)
def launch_bot(email: str, email_password: str,
               key: str, password: str, host: str, port: int):
    identity = NodeIdentity()
    password = password or identity.password
    key = key or identity.access_key
    host = host or identity.default_master

    if not host.startswith("ws://") and not host.startswith("wss://"):
        host = "ws://" + host

    if not key or not password or not host:
        raise RuntimeError("NodeIdentity not set, please pass key/password/host or "
                           "call 'hivemind-client set-identity'")

    node = HiveMindDeltaChatBridge(email=email, email_password=email_password,
                                   key=key, host=host, port=port, password=password)

    wait_for_exit_signal()

    node.stop()


if __name__ == "__main__":
    launch_bot()
