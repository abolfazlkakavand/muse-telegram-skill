# Security model

This skill lets Muse talk to Telegram through your own bot. It is built so that a hostile message, a stranger who finds your bot, or a prompt-injected agent can do as little as possible. Everything marked "in code" is enforced by `bin/telegram.py` and covered by automated tests.

| Threat | Defense |
| --- | --- |
| Token leak | The CLI only handles a credential surrogate. The Muse runtime swaps in the real token, only for `api.telegram.org`. Errors, logs and output are scrubbed of token-like strings (in code). |
| A stranger finds your bot | Only chats paired with a one-time 8-digit code are read. The code expires in 10 minutes and dies after 5 wrong tries. Other chats are counted, never shown (in code). |
| Someone else in a paired group | The user who paired is the owner. Only the owner can use /status, /stop and /new (in code). Other members' messages are handled as untrusted data. |
| Prompt injection from messages | `poll` and `watch` mark all text as untrusted data, strip control and bidi characters and cap length. No command adds a chat by id (in code). The instructions tell the agent never to obey message text. |
| Agent sending without approval | Every write (`send`, media, `edit`, `delete`, `webhook-delete`) exits with code 3 and a preview unless `--confirm` is passed (in code). Turning Telegram mode on grants standing approval to reply to the paired chat only; that part is an instruction to the agent, not a code barrier. |
| Exfiltrating local files | Files must be under `~/workspace` (symlinks resolved), not hidden, not secret-looking, not the state folder. Photos max 10 MB, documents 50 MB (in code). |
| Downloading arbitrary files | `download` only accepts file ids that came from a paired chat message, max 20 MB (in code). |
| Redirect or host tricks | Only `https://api.telegram.org` is ever called. Redirects are refused (in code). |
| Lost or repeated messages | Messages are stored in a local inbox and confirmed to Telegram in one atomic write. They are acknowledged only after the reply was sent, handed to Muse once per lease, and dropped with a notice after 3 failed hand-overs (in code). |
| The watchdog script | It is executable code, so installing it needs your explicit yes in the chat (the platform enforces this too). It is about 50 lines, has no network access and no secrets, and only runs `hook-check`, whose logic is unit-tested. A misconfigured watchdog raises at most one alert per hour instead of failing silently. |
| The memory file | `memory.md` is written by Muse from your chats, so it could contain text that came from a message. It carries a header telling readers to treat it as notes, is capped in size and keeps one backup. |

## Limits you should know

- The paired chat controls your Muse. Anyone who can use your Telegram account or unlocked phone can use it. Turn on Two-Step Verification and lock your phone.
- With standing approval the agent adds `--confirm` itself, so the confirm gate protects you from mistakes and from simple tricks, not from a fully compromised agent.
- Normal Telegram chats are not end-to-end encrypted, and Muse processes what you send. Do not send passwords or keys.
- If you suspect the token leaked: `/revoke` in `@BotFather`, then reconnect through the secure form.

Report problems by opening a GitHub issue.
