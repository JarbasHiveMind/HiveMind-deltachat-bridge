from jarbas_hive_mind.slave.terminal import HiveMindTerminalProtocol, HiveMindTerminal
from ovos_utils.log import LOG
from ovos_utils import create_daemon
from ovos_utils.messagebus import Message
from tempfile import gettempdir
from os.path import join
from deltachat import account_hookimpl, Account


class JarbasDeltaChatBridgeProtocol(HiveMindTerminalProtocol):

    def onOpen(self):
        super().onOpen()
        create_daemon(self.factory.run_deltachat)


class JarbasDeltaChatBridge(HiveMindTerminal):
    protocol = JarbasDeltaChatBridgeProtocol
    platform = "JarbasDeltaChatBridgeV0.1"

    def __init__(self, email=None, password=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.waiting = False
        db = join(gettempdir(), "HiveMindDeltaChatBridge_" + str(email))
        self.account = Account(db)
        self.email = email
        self.pswd = password
        self.allowed_emails = []  # if empty allow all
        if not self.account.is_configured():
            self.account.set_config("addr", self.email)
            self.account.set_config("mail_pw", self.pswd)
            self.account.set_config("mvbox_move", "0")
            self.account.set_config("mvbox_watch", "0")
            self.account.set_config("sentbox_watch", "0")
            configtracker = self.account.configure()
            configtracker.wait_finish()
        # map email addresses to deltachat objects
        self.addr2chat = {}

    # deltachat events
    @account_hookimpl
    def ac_incoming_message(self, message):
        print("process_incoming message", message)
        if message.is_system_message():
            return  # TODO send hivemind event?

        # check allowed emails
        addr = message.get_sender_contact().addr

        if not self.allowed_emails or addr in self.allowed_emails:
            # accept the chat
            message.create_chat()
        else:
            return  # TODO send hivemind event?

        self.addr2chat[addr] = message.chat
        utterance = message.text
        msg = {"data": {"utterances": [utterance],
                        "lang": "en-us"},
               "type": "recognizer_loop:utterance",
               "context": {"source": self.client.peer,
                           "destination": "hive_mind",
                           "deltachat_user": addr,
                           "platform": self.platform}}
        self.send_to_hivemind_bus(msg)

    # hivemind bridge functionality
    def speak(self, utterance, addr):
        self.addr2chat[addr].send_text(utterance)

    def run_deltachat(self):
        self.account.add_account_plugin(self)
        # start IO threads and configure if necessary
        self.account.start_io()
        print("Running deltachat bridge for: " + self.account.get_config("addr"))
        self.account.wait_shutdown()

    # parsed hivemind protocol messages
    def handle_incoming_mycroft(self, message):
        assert isinstance(message, Message)
        addr = message.context.get("deltachat_user")
        if not addr:
            return
        if message.msg_type == "speak":
            utterance = message.data["utterance"]
            self.speak(utterance, addr)
        elif message.msg_type == "hive.complete_intent_failure":
            LOG.error("complete intent failure")
            self.speak('I don\'t know how to answer that', addr)

    # hivemind websocket
    def clientConnectionLost(self, connector, reason):
        super().clientConnectionLost(connector, reason)
        # if set to auto reconnect the hivemind connection is reestablished,
        # otherwise we want to shutdown deltachat
        if not self.auto_reconnect:
            self.account.shutdown()

