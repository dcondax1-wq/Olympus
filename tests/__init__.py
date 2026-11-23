# Browser suites are hermetic by default: ntfy.sh (the PC's public status topic) answers "{}" in every Playwright context (tests/net_stub.py).
from . import net_stub as _net_stub

_net_stub.auto()

# night-hermetic 2026-11-23: every `python -m tests.<suite>` (and its children, through the env) keeps the bot's trade memory in a temp
# db, never the live data/memory.db (a replayed / routed test trade landed there). Set only when the caller did not choose one.
import os as _os
import tempfile as _tempfile

if not _os.environ.get("LE_MEMORY_DB"):
    _os.environ["LE_MEMORY_DB"] = _os.path.join(_tempfile.mkdtemp(prefix="le_mem_"), "memory.db")
