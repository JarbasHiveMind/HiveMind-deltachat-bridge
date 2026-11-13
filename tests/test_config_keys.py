"""DeltaChatBot sets only the optional config keys the account knows."""
import sys
from types import ModuleType
from unittest.mock import MagicMock


def _bot_class(config_keys):
    class _Account:
        def __init__(self, db):
            self.config = {}

        def get_config(self, key):
            if key == "sys.config_keys":
                return " ".join(config_keys)
            return self.config.get(key)

        def set_config(self, key, value):
            if key not in config_keys:
                raise KeyError(f"{key!r} not a valid config key")
            self.config[key] = value

        def configure(self):
            return MagicMock()

    fake = ModuleType("deltachat")
    fake.account_hookimpl = lambda f: f
    fake.Account = _Account
    sys.modules["deltachat"] = fake
    sys.modules.pop("hm_deltachat_bridge.deltabot", None)
    from hm_deltachat_bridge.deltabot import DeltaChatBot
    return DeltaChatBot


def _build(config_keys):
    saved = sys.modules.get("deltachat")
    try:
        return _bot_class(config_keys)(email="a@example.com", password="pw")
    finally:
        sys.modules.pop("hm_deltachat_bridge.deltabot", None)
        if saved is not None:
            sys.modules["deltachat"] = saved
        else:
            sys.modules.pop("deltachat", None)


def test_startup_survives_missing_sentbox_watch():
    bot = _build(["addr", "mail_pw", "mvbox_move"])
    assert bot.account.config == {
        "addr": "a@example.com", "mail_pw": "pw", "mvbox_move": "0"}


def test_optional_keys_set_when_known():
    bot = _build(["addr", "mail_pw", "mvbox_move", "sentbox_watch"])
    assert bot.account.config["sentbox_watch"] == "0"
    assert bot.account.config["mvbox_move"] == "0"
