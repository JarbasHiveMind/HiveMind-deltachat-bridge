# Configuration & Credentials Reference

The bridge needs two sets of credentials: one for the bot mailbox, one for the HiveMind hub.

## DeltaChat (mailbox) credentials

| Option | Meaning |
| --- | --- |
| `--email` | The bot's email address. This is the address users message to reach the hub. |
| `--email-password` | The mailbox password (or app password where the provider requires one). |

DeltaChat configures itself from the address and password: it discovers IMAP/SMTP settings for common providers automatically. A local account database is created in the system temp directory, keyed by the address.

### Sender allowlist

The underlying bot supports an `allowed_emails` allowlist. When empty (the default) it accepts messages from any sender. There is no CLI flag for it yet. Set it programmatically on `DeltaChatBot` if you need to restrict access.

## HiveMind credentials

| Option | Meaning | Default |
| --- | --- | --- |
| `--key` | HiveMind access key, from `hivemind-core add-client`. | read from identity file |
| `--password` | HiveMind password, from `hivemind-core add-client`. | read from identity file |
| `--host` | Hub host. A `ws://` prefix is added automatically if you omit the scheme. | read from identity file |
| `--port` | Hub port. | `5678` |

### Identity file

When `--key/--password/--host` are not passed, the bridge reads them from the stored `NodeIdentity`. Set it once:

```bash
hivemind-client set-identity \
  --key "your-access-key" \
  --password "your-password" \
  --host "ws://192.168.1.100"
```

If neither the options nor a stored identity supply a key, password, and host, the bridge raises:

```
NodeIdentity not set, please pass key/password/host or call 'hivemind-client set-identity'
```

## Reply routing

Outbound utterances are tagged with the sender's address (`deltachat_addr`) in the message context. The hub echoes that context on its `speak` reply, and the bridge uses it to deliver the answer to the originating chat. A `speak` reply that arrives without `deltachat_addr` is logged and dropped.

## Encryption

The HiveMind connection is authenticated and encrypted by the protocol layer (handled by `hivemind-bus-client`). DeltaChat itself provides end-to-end encryption (Autocrypt) for the email transport between users and the bot mailbox.

---
[← Accounts & chatmail](accounts-and-chatmail.md) · [Home](../readme.md) · [Examples →](examples.md)
