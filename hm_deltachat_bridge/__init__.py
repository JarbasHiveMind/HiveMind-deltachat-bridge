from hivemind_bus_client.client import HiveMessageBusClient
from ovos_utils.log import LOG
from ovos_utils.messagebus import FakeBus
from ovos_utils.messagebus import Message

from hm_deltachat_bridge.deltabot import DeltaChatBot


class HiveMindDeltaChatBridge(HiveMessageBusClient):
    platform = "HiveMindDeltaChatBridgeV0.1"

    def __init__(self, email, email_password, *args, **kwargs):
        self.bot = DeltaChatBot(email, email_password)
        self.bot.handle_utterance = self.handle_delta_utterance
        self.bot.start()
        LOG.info("== connected to DeltaChat")
        super().__init__(*args, **kwargs)
        self.connect(FakeBus(), site_id="deltachat")
        self.on_mycroft("speak", self.handle_incoming_mycroft)
        LOG.info("== connected to HiveMind")

    def stop(self):
        self.bot.stop()

    def handle_delta_utterance(self, utterance, addr):
        LOG.debug(f"asking hivemind: {utterance}")
        # TODO - lang detect here
        self.emit_mycroft(
            Message("recognizer_loop:utterance",
                    {"utterances": [utterance]},
                    {"deltachat_addr": addr})
        )

    def handle_incoming_mycroft(self, message):
        utterance = message.data["utterance"]
        addr = message.context.get("deltachat_addr")
        if not addr:
            LOG.error("got speak message without deltachat_addr")
        else:
            LOG.info(f"HiveMind {addr} : {utterance}")
            self.bot.speak(utterance, addr)
