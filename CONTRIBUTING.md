# Contributing

Thanks for helping. The project is small on purpose, so changes are easy to review.

## Run it

```bash
bash scripts/install.sh
./run.sh --dev
```

## Check before you push

```bash
python -m pytest backend/tests -q     # backend
npx tsc --noEmit                      # types
npx next build                        # the page builds
```

## Adding an ability (the easiest contribution)

Write a plugin: copy `backend/plugins/dice.py`, change it, restart. Details are in `backend/plugins/README.md`.

Rules for every action:
1. She can only use actions from the registry. Never run text the AI invented.
2. Validate every argument. Treat all arguments as untrusted.
3. If it changes something that is hard to undo (close, delete, send, power), mark it `risky=True` so she asks first.
4. Return `Result(False, "...")` with a clear reason when it fails. She says the truth out loud.
5. Add a test in `backend/tests/` that uses a fake instead of the real PC or internet.

## Scope of security tools

The security helpers only work on this computer and private home-network addresses, never the internet.
Pull requests that widen that will not be merged.

## Never commit

`backend/.env`, `credentials.json`, `token.json`, `backend/data/`, or videos and zips.

## Style

Plain, readable code with a short comment at the top of each file saying what it is for.
Commit messages: one clear line, for example `Add reminders to the briefing`.
