import threading
from os.path import join
from tempfile import gettempdir
from ovos_utils.log import LOG
from deltachat import account_hookimpl, Account


class DeltaChatBot(threading.Thread):

    def __init__(self, email=None, password=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        db = join(gettempdir(), "HiveMindDeltaChatBridge_" + str(email))
        self.account = Account(db)
        self.email = email
        self.pswd = password
        self.allowed_emails = []  # if empty allow all
        self.account.set_config("addr", self.email)
        self.account.set_config("mail_pw", self.pswd)
        self.account.set_config("mvbox_move", "0")
        self.account.set_config("sentbox_watch", "0")
        configtracker = self.account.configure()
        configtracker.wait_finish()
        # map email addresses to deltachat objects
        self.addr2chat = {}

    def handle_utterance(self, utterance, addr):
        print(addr, utterance)

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

        self.handle_utterance(message.text, addr)

    def speak(self, utterance, addr):
        self.addr2chat[addr].send_text(utterance)

    def run(self):
        self.account.add_account_plugin(self)
        # start IO threads and configure if necessary
        self.account.start_io()
        LOG.info("Running deltachat bridge for: " + self.account.get_config("addr"))
        self.account.wait_shutdown()

    def stop(self):
        self.account.shutdown()
