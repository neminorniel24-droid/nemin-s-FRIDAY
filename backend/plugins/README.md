# Plugins

Add your own abilities without touching the core code.

1. Copy `dice.py` to a new file here, for example `my_thing.py`.
2. Write a function and put `@action("name", "info" or "pc", "one-line help for the AI")` above it.
   `"info"` = fetches facts she then says out loud. `"pc"` = does something and returns a short confirmation.
3. Return `Result(True, "message")` or `Result(False, "what went wrong")`.
4. Add `risky=True` if she should ask for a yes before running it.
5. Restart with `./stop.sh && ./run.sh`.

Rules: files starting with `_` are skipped. A broken plugin is reported in the backend log and the rest still load.
Everything a plugin does is written to the activity log like any other action.
