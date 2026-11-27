# Muse Telegram Skill

Chat with your Muse from Telegram, in real time, through your own bot. It runs on your Muse allowance only: no server, no API key, no subscription.

## What you get

- Replies in a few seconds, with a typing indicator the moment your message arrives.
- Near-zero cost while idle. A background watchman waits on Telegram for free; Muse only wakes when a message arrives, once per message.
- Text, photos and documents both ways, reply threading, link buttons, edit, delete, reactions.
- Owner commands you can type in Telegram: `/status`, `/stop`, `/help`, `/new`.
- Self-healing: an optional watchdog restarts the watchman if Muse restarts, with a restart limit so it can never burn tokens in a loop.
- Long-chat protection: after about 50 messages Muse saves a short memory and continues in a fresh chat, so each wake-up stays cheap.
- Safe by design: only the chat you pair can talk to Muse, every write needs confirmation in code, the bot token is never visible. Details in [SECURITY.md](SECURITY.md).

## How it works

```
you (Telegram) -> your bot -> watchman (background process, free) -> wakes Muse -> Muse replies through the bot
```

Muse has no inbound webhook, so something has to be listening. The watchman is a small background process in your Muse environment that long-polls Telegram. Waiting costs no model tokens; when a message arrives the process exits, which wakes Muse with the message. Each message is saved in a local inbox first and acknowledged only after the reply was sent, so nothing is lost or answered twice.

## Install

1. In Telegram open `@BotFather`, send `/newbot`, and keep the token it gives you.
2. Paste this into a chat with Muse. It is pinned to a fixed, reviewed version:

```
Install this connector: https://raw.githubusercontent.com/abolfazlkakavand/muse-telegram-skill/6c6073a81d3926e618d16386ca1454290f88740a/connectors/telegram/SKILL.md
Follow the skill's Auth section: open the secure credential form for my bot token. Never ask me to paste the token in chat.
```

3. Muse opens a secure page. Paste the token there, never in the chat.
4. Tell Muse: "Run doctor for the Telegram skill", then "Pair my Telegram". Muse gives you an 8-digit code; send `/pair <code>` to your bot within 10 minutes. The bot answers "Paired."
5. Tell Muse: **"Telegram mode on"**. Do this from a dedicated side chat so your main chat stays clean.
6. Muse will ask permission to install a small watchdog script. **Answer yes.** It is about 50 lines, runs `hook-check` every 60 seconds, and has no network access and no secrets. Muse requires your explicit approval for any executable script, so it will not install it without a yes. If you say no, everything still works, but the watchman stops whenever Muse restarts and you must say "Telegram mode on" again.
7. Send your bot a message. Send `/status` to see the watchman, the session and the watchdog.

## Using it

| You say | What happens |
| --- | --- |
| a normal message in Telegram | Muse replies in the same chat |
| `/status` in Telegram | health report from the watchman itself, no Muse wake |
| `/stop` in Telegram | stops the watchman and the watchdog; start again with "Telegram mode on" in Muse |
| `/new` in Telegram | Muse saves a short memory and continues in a fresh chat |
| `/help` in Telegram | lists the commands |
| "Telegram mode off" to Muse | same as `/stop` |

Several messages sent within about 3 seconds arrive in one wake-up. Say "send me X as a photo/file" and Muse sends it back through the bot.

## Tips

- **Tokens:** idle costs nothing. Each wake-up is one agent turn, and the longer the chat, the dearer a wake-up. Lower the rotation limit with "set the Telegram skill config rotate_after to 30" if you want cheaper chats; you can also send `/new` any time.
- **Groups:** in `@BotFather` send `/setjoingroups`, pick your bot and choose **Disable**, so nobody can add it to a group.
- **Your account:** the paired chat controls your Muse. Turn on Two-Step Verification in Telegram and lock your phone.
- **Secrets:** Telegram chats are not end-to-end encrypted. Do not send passwords or keys.
- **Updating:** say "Telegram mode off", paste the install message of the new version, then "Telegram mode on". Your pairing and state in `~/workspace/telegram-state` are kept.
- **Token leaked?** `/revoke` in `@BotFather`, then reconnect through the secure form.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| No reply | Send `/status`. If the bot does not answer, the watchman is not running: tell Muse "Telegram mode on". |
| The bot works but stops after a while | Muse restarted and killed the watchman. Install the watchdog (step 6) or say "Telegram mode on" again. |
| Muse says the watchdog install was blocked | Muse protects executable scripts with an approval check. Answer yes when it asks, then retry. Without it the skill still works, minus automatic restarts. |
| An alert says `hook-not-configured` or `hook-check-failed` | The skill folder path inside the watchdog script is wrong. Ask Muse to reinstall the watchdog with the correct path. |
| `doctor` fails with 404 | The token was not injected. Reinstall the skill and enter the token through the secure form. |
| Error 409 | A webhook or another program is reading the same bot. Ask Muse for `webhook-info`, and `webhook-delete` if a webhook is set. |
| "watchman failing, hook disabled" | The watchman crashed repeatedly. Ask Muse for `status` and `events --tail 10`, fix the cause, then say "Telegram mode on". |
| A reply came twice | Should not happen. Ask Muse for `events --tail 20` and open an issue with the output. |

## Limitations

- Muse cannot be woken from outside, so this is a listener running inside Muse. If Muse restarts, the watchman stops until the watchdog (or you) restarts it.
- Replies depend on what Muse can do in your account. Voice and video generation are not part of this skill.
- Turning Telegram mode on is standing approval to reply to the paired chat only. It does not cover other chats, files you did not name, edits, deletes or installing code.
- The code is tested against a simulated Telegram API and was live-tested in a real Muse runtime on 2026-11-27. It is a community project, not an official Meta or Telegram product.

## Develop

```bash
python3 -m unittest discover -s tests
```

CI runs the tests on Python 3.12. Layout: `connectors/telegram/SKILL.md` (instructions Muse follows and the file manifest), `bin/telegram.py` (the CLI, standard library only), `hooks/watchman-watchdog.sh` (thin wrapper; the decisions live in `hook-check` and are unit-tested).

## License

MIT
