# Muse Telegram Skill

Talk to your Muse through **your own Telegram bot**, in real time, using only your Muse account allowance. No server, no subscription.

- **Real time without polling tokens:** a background watchman long-polls Telegram for free and wakes Muse only when a message arrives.
- **Self-healing:** a watchdog hook restarts the watchman if it dies, with a restart limit (circuit breaker) so it can never burn tokens in a loop.
- **Pairing-locked:** only chats paired with a one-time code are ever read. Strangers are counted, never shown.
- **Confirm-gated writes**, enforced in code. File sending is limited to `~/workspace`.
- **Owner commands in Telegram:** `/status`, `/stop`, `/help` (answered without waking Muse) and `/new`.
- **Never loses a message:** messages are acknowledged only after the reply was sent. Leases prevent double delivery.
- **Chat rotation:** after about 50 messages Muse writes a short memory, opens a fresh chat and moves the watchman there, so each wake-up stays cheap.
- Send text (auto-split, HTML, link buttons), photos, documents; reply, edit, delete, react, download attachments.
- Standard library only. 49 automated tests against a simulated Telegram API.

Status: draft. The v1 pairing and round trip were verified in a live Muse runtime. The watchman, hook and rotation flow are tested with simulations only. See [SECURITY.md](SECURITY.md).

## Install (one paste)

1. Create a bot with `@BotFather` (`/newbot`) and keep the token ready.
2. Paste this into a chat with your Muse (pinned to a fixed version):

```
Install this connector: https://raw.githubusercontent.com/abolfazlkakavand/muse-telegram-skill/1bbef20550ae04f1f2be3b299cceea8dc49f510b/connectors/telegram/SKILL.md
Follow the skill's Auth section: open the secure credential form for my bot token. Never ask me to paste the token in chat.
```

3. Muse opens a secure page. Paste the token there.
4. Say: "run doctor for the Telegram skill", then "pair my Telegram" and send `/pair <code>` to your bot.
5. Say: **"Telegram mode on"**. Muse starts the watchman and installs the watchdog. Say **"Telegram mode off"** to stop both.

Already installed an older version? Paste the same install message again; your pairing and state in `~/workspace/telegram-state` are kept.

## Hardening checklist

- In `@BotFather`: `/setjoingroups`, pick your bot, **Disable**.
- Turn on Two-Step Verification in Telegram and lock your phone: the paired chat controls your Muse.
- If you suspect the token leaked: `/revoke` in `@BotFather`, then reconnect through the secure form.

## Commands

See [SKILL.md](connectors/telegram/SKILL.md) for the full list and the exact runbooks Muse follows (ON, WAKE, ROTATE, OFF).

## Develop

```bash
python3 -m unittest discover -s tests
```

Layout: `connectors/telegram/SKILL.md` (instructions and file manifest), `bin/telegram.py` (CLI), `hooks/watchman-watchdog.sh` (thin hook wrapper; decisions live in `hook-check`).

## License

MIT
