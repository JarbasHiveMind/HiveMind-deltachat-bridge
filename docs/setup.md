# Setup Walkthrough

From nothing to a working DeltaChat chatbot backed by a HiveMind hub.

## How the bridge fits together

The bridge is a HiveMind satellite with two connections:

- **To DeltaChat**: it logs into the bot's mailbox (IMAP/SMTP) and watches for incoming messages. Need a mailbox? See [`accounts-and-chatmail.md`](accounts-and-chatmail.md). A **chatmail** account is the quickest, bot-friendly option.
- **To the HiveMind hub**: it authenticates with a HiveMind access key and password and exchanges encrypted protocol messages.

Each inbound chat message is tagged with the sender's address and sent to the hub as a `recognizer_loop:utterance`. The hub's `speak` reply carries that address back, so the bridge routes the answer to the right chat.

```
DeltaChat (email)  ⇄  bridge  ⇄  hivemind-core hub  ⇄  OVOS pipeline / skills
```

## Step 1: Stand up a HiveMind hub

Install and run [hivemind-core](https://github.com/JarbasHiveMind/HiveMind-core):

```bash
pip install hivemind-core
hivemind-core listen
```

The hub listens on port `5678` by default.

## Step 2: Register the bridge as a client

On the hub machine:

```bash
hivemind-core add-client --name deltachat-bridge \
  --access-key "your-access-key" --password "your-password"
```

Keep the access key and password. List clients with `hivemind-core list-clients`.

## Step 3: Prepare the bot mailbox

1. Create or pick an email account for the bot (any IMAP/SMTP provider).
2. Note the address and password. Where the provider enforces app passwords (for example for IMAP access), generate one.
3. The bot's address is what users message to reach the hub.

## Step 4: Install the native DeltaChat library

The `deltachat` Python package binds to native `libdeltachat` / `deltachat-core`. Install it via your platform package manager or from the [DeltaChat core releases](https://github.com/deltachat/deltachat-core-rust) before installing the bridge.

## Step 5: Install the bridge

```bash
pip install HiveMind-deltachat-bridge
```

## Step 6: Provide the HiveMind credentials

Store an identity once:

```bash
hivemind-client set-identity \
  --key "your-access-key" \
  --password "your-password" \
  --host "ws://192.168.1.100"
```

or pass `--key/--password/--host` on each run.

## Step 7: Run

```bash
hm-deltachat-bridge \
  --email "bot@example.com" \
  --email-password "mailbox-password"
```

The bridge logs `connected to DeltaChat` and `connected to HiveMind`.

## Step 8: Talk to it

From any DeltaChat client, start a chat with `bot@example.com` and send a message. The bridge forwards it to the hub and replies with the spoken answer.

---
[Home](../readme.md) · [Accounts & chatmail →](accounts-and-chatmail.md)
