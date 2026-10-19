"""Two-week eval sizing for LIT (owner order 2026-10-18: an MFFU eval must be passed within 10 sessions). Research:
tools/lit_2wk.py, research/writeups/lit-two-week-eval.md.

The code lives in engine/sizing.py since 2026-10-18 (the lit_sizing mode "two_week", lit_qty); this module is a thin import so
the study (tools/lit_2wk.py) and its test (tests/test_lit_2wk_sizing.py) keep running unchanged. See engine/sizing.py for the
config keys, the state and the trade fields.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.sizing import (TW_COMM as COMM, TW_DEFAULT as DEFAULT, TW_PV as PV, TW_SLIP as SLIP,  # noqa: E402,F401
                           TW_25K as MFFU_25K, TW_50K as MFFU_50K, _num, eval_session, eval_state, two_week_qty)
