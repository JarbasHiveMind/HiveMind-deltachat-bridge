# Examples

## Run with stored identity

Store the HiveMind identity once, then run with only the mailbox login:

```bash
hivemind-client set-identity --key KEY --password PASS --host ws://192.168.1.100
hm-deltachat-bridge --email bot@example.com --email-password "mailbox-password"
```

## Run with all credentials inline

```bash
hm-deltachat-bridge \
  --email bot@example.com \
  --email-password "mailbox-password" \
  --key "your-access-key" \
  --password "your-password" \
  --host "192.168.1.100" \
  --port 5678
```

A `ws://` prefix is added to `--host` automatically when no scheme is given.

## A conversation

A user opens a chat with `bot@example.com` from any DeltaChat app:

```
user> what time is it?
bot>  It is half past three.

user> set a timer for five minutes
bot>  Timer set for five minutes.
```

Each reply is delivered to the chat the message came from.

## Embed the bridge in your own program

`HiveMindDeltaChatBridge` is an asyncio object. The hub and DeltaChat clients can be injected for testing or customization:

```python
import asyncio
from hm_deltachat_bridge import HiveMindDeltaChatBridge

async def main():
    bridge = HiveMindDeltaChatBridge(
        email="bot@example.com",
        email_password="mailbox-password",
        key="your-access-key",
        password="your-password",
        host="ws://192.168.1.100",
        port=5678,
    )
    await bridge.start()
    try:
        await asyncio.Event().wait()  # run until cancelled
    finally:
        await bridge.stop()

asyncio.run(main())
```

To restrict who may message the bot, set the allowlist on the underlying bot before `start()`:

```python
bridge.bot.allowed_emails = ["alice@example.com", "bob@example.com"]
```

---
[← Configuration](configuration.md) · [Home](../readme.md)
