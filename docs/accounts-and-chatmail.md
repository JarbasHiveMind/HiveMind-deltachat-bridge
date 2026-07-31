# Accounts & chatmail: running the DeltaChat bridge

DeltaChat is end-to-end-encrypted chat that runs over **ordinary email**, so this
bridge logs into a mailbox (IMAP to receive, SMTP to send) and relays each message
to/from a HiveMind hub. As an operator you need **one email account for the bot**
plus a HiveMind hub to point it at. This page covers how to get the account
(including **chatmail**, the easiest option) and the full run/setup steps.

```
DeltaChat user  ⇄  bot's mailbox (IMAP/SMTP)  ⇄  hm-deltachat-bridge  ⇄  HiveMind hub  ⇄  OVOS skills
```

## 1. Get the bot a DeltaChat account

You have three options. For a bot, **chatmail (Option A)** is recommended.

### Option A: chatmail (recommended)

**Chatmail** servers are minimal, privacy-first mail servers purpose-built for
Delta Chat: instant signup (no name, phone, or recovery info), encryption
enforced by default, and explicitly designed for **automated / bot accounts**.
That makes them the quickest way to get a working bot address.

Ways to provision a chatmail account:

1. **Via the Delta Chat app (quickest).** Install Delta Chat (desktop or mobile),
   choose *Add Account → create a new profile / instant onboarding*. It creates an
   address on a public chatmail server automatically. Then read the **address** and
   **password** from *Settings → Your Profile → Advanced* (or export the account).
   You can also scan a chatmail invite QR or open a `DCACCOUNT:https://<server>/new`
   link.
2. **Programmatically.** A chatmail server hands out fresh accounts at
   `https://<server>/new`. The Delta Chat core can self-provision one from a
   `dcaccount:` / `DCACCOUNT:` URL on first configure.
3. **Self-host.** Run the chatmail relay server
   ([`chatmaild`](https://github.com/chatmail/relay)) on your own domain for a
   private chatmail instance you fully control.

Public chatmail servers exist for testing / light use (for example
`nine.testrun.org`). The current list is at [chatmail.at](https://chatmail.at). **For
production, self-host or use a server you trust.** The bot's mailbox can read
every message users send it.

### Option B: any IMAP/SMTP mailbox

Any standard email account works: Gmail (with IMAP enabled and an **app
password**), Mailbox.org, Posteo, a self-hosted Dovecot/Postfix, etc. You supply
the address + password and Delta Chat auto-detects the IMAP/SMTP servers for most
providers.

### Option C: self-hosted mail

Run your own mail server (Postfix + Dovecot, or `chatmaild`) for full control and
no third party in the loop.

## 2. Prerequisites

- The bot's **email address + password** (from step 1).
- A running **HiveMind hub** (`hivemind-core`) you can reach.
- The native **`libdeltachat` / `deltachat-core`** library on the host (the
  `deltachat` Python package binds to it). Install it from your distro or the
  Delta Chat releases before `pip install`.

## 3. Register the bridge on the hub

On the hub, create a client credential for this bridge:

```bash
hivemind-core add-client          # prints an ACCESS KEY and a PASSWORD
```

Note the **access key**, **password**, and the hub **host** / **port** (default
WebSocket port `5678`). The bridge connects as a HiveMind *satellite* with these.

## 4. Install and run the bridge

```bash
pip install HiveMind-deltachat-bridge      # provides the `hm-deltachat-bridge` command

hm-deltachat-bridge \
  --email          "$BOT_ADDRESS" \
  --email-password "$BOT_PASSWORD" \
  --key            "$HIVEMIND_ACCESS_KEY" \
  --password       "$HIVEMIND_PASSWORD" \
  --host           "ws://your-hub-host" \
  --port           5678
```

If you've already stored a HiveMind identity (e.g. with `hivemind-client
set-identity`), you can omit `--key/--password/--host` and the bridge reads them
from the identity file.

## 5. Talk to it

Add the bot's **address** as a contact in any Delta Chat client and send it a
message. Each incoming message becomes a `recognizer_loop:utterance` on the hub.
The hub's spoken reply goes back to the sender's chat.

## Security notes

- The **email password** and the **HiveMind password** are secrets. Pass them via
  environment variables or a secrets manager, never in shell history or a
  committed file.
- Chatmail enforces end-to-end encryption. With a generic mailbox, encryption
  relies on Autocrypt key exchange, so the very first messages may be unencrypted
  until keys are exchanged.
- Anyone who knows the bot's address can reach the hub. Restrict access at the hub
  (client ACLs / `allowed_types`) and, once available, the bridge's allowed-senders
  option.

## Testing (live e2e)

`tests/e2e/test_deltachat_live.py` runs a **real** DeltaChat round-trip when you
provide an account via environment variables. It skips cleanly when they are
absent (the mocked HiveMind-side e2e always runs):

```bash
export DELTACHAT_ADDR="bot@nine.testrun.org"
export DELTACHAT_PASSWORD="…"
# optional: a second chatmail account to message the bot from
export DELTACHAT_PEER_ADDR="…"
export DELTACHAT_PEER_PASSWORD="…"
pytest tests/e2e/test_deltachat_live.py
```

---
[← Setup Walkthrough](setup.md) · [Home](../readme.md) · [Configuration →](configuration.md)
