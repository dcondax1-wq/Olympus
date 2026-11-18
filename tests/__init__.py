# Browser suites are hermetic by default: ntfy.sh (the PC's public status topic) answers "{}" in every Playwright context (tests/net_stub.py).
from . import net_stub as _net_stub

_net_stub.auto()
