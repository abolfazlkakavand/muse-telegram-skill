# Security model

This skill lets Muse talk to Telegram through your own bot. It is built so a hostile message or a prompt-injected agent cannot do much.

| Threat | Defense (enforced in code) |
| --- | --- |
| Token leak | The CLI only handles a credential surrogate. The Muse runtime swaps in the real token, only for `api.telegram.org`. Errors and output are scrubbed of token-like strings. |
| Anyone messaging your bot | Only chats paired with a one-time 8-digit code are read. Other chats are counted, never shown. Code expires in 10 minutes and dies after 5 wrong tries. |
| Prompt injection from messages | `poll` marks all text as untrusted data, strips control and bidi characters and caps length. There is no command to add a chat by id. |
| Agent sending without approval | Every write (`send`, media, `edit`, `delete`, `webhook-delete`) exits with code 3 and a preview unless `--confirm` is passed. |
| Exfiltrating local files | Files must be under `~/workspace` (symlinks resolved), not hidden, not secret-looking, not the state folder. Limits: photos 10 MB, documents 50 MB. |
| Downloading arbitrary files | `download` only accepts file ids that came from a paired chat message, max 20 MB. |
| Redirect or host tricks | Only `https://api.telegram.org` is ever called. Redirects are refused. |

Limits: the confirmation flag is a speed bump for an agent, not a barrier against a determined user who controls the shell. Report issues by opening a GitHub issue.
