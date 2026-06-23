# HiveMind DeltaChat Bridge

Relay a [DeltaChat](https://delta.chat/en/) account to a [HiveMind](https://github.com/JarbasHiveMind/HiveMind-core) hub.

[DeltaChat](https://delta.chat) is an end-to-end-encrypted chat that runs over ordinary email. This bridge is a HiveMind **satellite** whose input and output are DeltaChat messages instead of a microphone. Each incoming chat message becomes an utterance sent to the hub; the hub's spoken reply is delivered back to the sender's chat. Any HiveMind hub (and the OVOS skills behind it) becomes reachable as an email-based chatbot.

```
DeltaChat (email)  ⇄  HiveMind-deltachat-bridge  ⇄  HiveMind hub (hivemind-core)  ⇄  OVOS skills
```

## Prerequisites

- A running **HiveMind hub** ([hivemind-core](https://github.com/JarbasHiveMind/HiveMind-core)) reachable over the network.
- A **HiveMind access key + password** for this bridge, issued by the hub with `hivemind-core add-client`.
- An **email account** for the bot (address + password). DeltaChat works with any IMAP/SMTP mailbox; the address is what users message to talk to the hub. The easiest option is a **chatmail** account (instant, bot-friendly) — see [`docs/accounts-and-chatmail.md`](docs/accounts-and-chatmail.md) for how to get one and the full operator walkthrough.
- The native **`libdeltachat` / `deltachat-core`** library installed on the system — the `deltachat` Python package binds to it.

## Install

```bash
pip install HiveMind-deltachat-bridge
```

Or from a checkout:

```bash
git clone https://github.com/JarbasHiveMind/HiveMind-deltachat-bridge
cd HiveMind-deltachat-bridge
pip install .
```

This installs the `hm-deltachat-bridge` console command.

## Quickstart

**1. Register the bridge on the hub** (run where `hivemind-core` is installed):

```bash
hivemind-core add-client --name deltachat-bridge \
  --access-key "your-access-key" --password "your-password"
```

**2. Store the HiveMind credentials** so they are read automatically:

```bash
hivemind-client set-identity \
  --key "your-access-key" \
  --password "your-password" \
  --host "ws://192.168.1.100"
```

(`set-identity` ships with `hivemind-bus-client`, a dependency of this bridge.) Alternatively, pass `--key/--password/--host` on every run.

**3. Run the bridge** with the bot's email login:

```bash
hm-deltachat-bridge \
  --email "bot@example.com" \
  --email-password "mailbox-password"
```

**4. Send a message.** From any DeltaChat app (or plain email), message `bot@example.com`:

```
what time is it?
```

The bridge forwards the message to the hub, waits for the `speak` reply, and answers in the same chat.

## Configuration

`hm-deltachat-bridge` options:

| Option | Description | Default |
| --- | --- | --- |
| `--email` | Bot mailbox address | — |
| `--email-password` | Bot mailbox password | — |
| `--key` | HiveMind access key | read from identity file |
| `--password` | HiveMind password | read from identity file |
| `--host` | HiveMind host (a `ws://` prefix is added if no scheme) | read from identity file |
| `--port` | HiveMind port | `5678` |

When `--key/--password/--host` are omitted they are read from the stored `NodeIdentity`. If none are available the bridge exits pointing you at `hivemind-client set-identity`.

## Troubleshooting

- **`NodeIdentity not set`** — run `hivemind-client set-identity`, or pass `--key/--password/--host`.
- **No reply to messages** — confirm the hub is reachable and the access key is authorized (`hivemind-core list-clients`), and that an OVOS pipeline produces spoken answers.
- **Mailbox login fails** — verify IMAP/SMTP is enabled for the bot mailbox and the password is an app password where the provider requires one.
- **`ImportError` on `deltachat`** — install the native `libdeltachat` / `deltachat-core` for your platform.

## Documentation

See [`docs/`](docs/) for a full setup walkthrough, a credential reference, and worked examples.
