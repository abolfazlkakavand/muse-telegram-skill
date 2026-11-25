# Muse Telegram Skill

A small, safe skill that lets your Muse talk to Telegram through **your own bot**.

- Pairing-locked: only chats you pair with a one-time code are ever read.
- Confirmation-gated: every write needs `--confirm`, enforced in code.
- Token never visible: Muse injects it; the skill only sees a surrogate.
- Features: read messages, send text (auto-split, HTML/MarkdownV2, link buttons), photos, documents, reply, edit, delete, react, typing, download files, diagnostics (`doctor`).
- Standard library only. 23 automated tests against a simulated Telegram API.

Status: draft. Tested with a mock; not yet verified inside a live Muse runtime. See [SECURITY.md](SECURITY.md).

## Install (one paste)

1. Create a bot with `@BotFather` (`/newbot`) and keep the token ready.
2. Paste this into a chat with your Muse (pinned to a fixed version):

```
Install this connector: https://raw.githubusercontent.com/abolfazlkakavand/muse-telegram-skill/212e416f56c6234a9decb66c1e8f7363faa0739b/connectors/telegram/SKILL.md
Follow the skill's Auth section: open the secure credential form for my bot token. Never ask me to paste the token in chat.
```

3. Muse opens a secure page. Paste the token there.
4. Ask Muse: "run doctor for the Telegram skill", then "pair my Telegram". Send `/pair <code>` to your bot when asked.

## راهنمای کوتاه (فارسی)

1. در تلگرام با `@BotFather` ربات بساز و توکن را نگه دار.
2. پیام بالا را در چت Muse بفرست.
3. Muse یک صفحه امن باز می‌کند؛ توکن را فقط آنجا بچسبان.
4. به Muse بگو `doctor` را اجرا کند و بعد جفت‌سازی (`pair`) کند. کد هشترقمی را به صورت `/pair کد` به ربات بفرست.

## Develop

```bash
python3 -m unittest discover -s tests
```

Layout matches the Muse connector convention: `connectors/telegram/SKILL.md` lists every installed file in its `## Files` manifest (`SKILL.md`, `bin/telegram.py`).

## License

MIT
