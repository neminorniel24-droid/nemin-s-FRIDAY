# OpenClaw, safely

OpenClaw is a separate, autonomous agent. It can run shell commands and change files, and it can be
reached through messaging apps. That is powerful and risky. The people who make it recommend running
it inside an isolated place (a container, a separate user account, or a virtual machine) and starting
with read-only permissions.

**NEMIII does not control OpenClaw, and does not install it for you.** I could not find a documented
way to hand it a task from another program, and giving one AI unsupervised control of another with
access to your PC would undo the safety rules NEMIII is built on (fixed actions, confirm before risky
ones, everything logged). So they stay side by side:

| | NEMIII | OpenClaw |
|---|---|---|
| Runs | on your PC, fixed action list | autonomous, free-form |
| Risky steps | always ask you | decided by its own settings |
| Good for | voice control, models, creating things | longer open-ended chores |

## Recommended way

1. Keep it away from your main account: use a Windows virtual machine, a second Windows user, or a Docker container.
2. Use Ollama as its brain so it stays offline. Install Ollama, then run the command the OpenClaw/Ollama
   docs give (`ollama launch openclaw`, which installs OpenClaw if needed). Read the security screen it shows.
3. Pick a model that fits 6 GB (for example `qwen2.5:7b`). Bigger "recommended" models in their guides need 11 GB or more.
4. Do not give it your passwords, SSH keys, browser profile or the NEMIII folder. Start read-only.
5. Check the official docs first, because this software changes quickly: https://docs.ollama.com/integrations/openclaw
