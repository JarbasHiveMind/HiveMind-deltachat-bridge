from deltachat_bridge import JarbasDeltaChatBridge
from jarbas_hive_mind import HiveMindConnection
from jarbas_hive_mind.discovery import LocalDiscovery
from ovos_utils.log import LOG
from time import sleep


def connect_to_hivemind(email, password, access_key,
                        host="wss://127.0.0.1",
                        port=5678,
                        name="JarbasDeltaChatBridge",
                        crypto_key=None):
    con = HiveMindConnection(host, port)

    bridge = JarbasDeltaChatBridge(email, password, crypto_key=crypto_key,
                                   headers=con.get_headers(name, access_key))

    con.connect(bridge)


def discover_hivemind(email, password, access_key,
                      name="JarbasDeltaChatBridge", crypto_key=None):
    discovery = LocalDiscovery()
    headers = HiveMindConnection.get_headers(name, access_key)
    while True:
        print("Scanning...")
        for node_url in discovery.scan():
            LOG.info("Fetching Node data: {url}".format(url=node_url))
            node = discovery.nodes[node_url]
            node.connect(crypto_key=crypto_key,
                         node_type=JarbasDeltaChatBridge,
                         headers=headers,
                         email=email,
                         password=password
                         )
        sleep(5)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--access_key", help="hivemind access key",
                        required=True)
    parser.add_argument("--email", help="deltachat email", required=True)
    parser.add_argument("--password", help="deltachat password", required=True)
    parser.add_argument("--crypto_key", help="payload encryption key",
                        default=None)
    parser.add_argument("--name", help="human readable device name",
                        default="JarbasDeltaChatBridge")
    parser.add_argument("--host", help="HiveMind host")
    parser.add_argument("--port", help="HiveMind port number", default=5678)

    args = parser.parse_args()

    if args.host:
        # Direct Connection
        connect_to_hivemind(args.email, args.password, args.access_key,
                            args.host, args.port, args.name, args.crypto_key)

    else:
        # Auto discovery
        discover_hivemind(args.email, args.password, args.access_key,
                          args.name, args.crypto_key)


if __name__ == '__main__':
    main()
