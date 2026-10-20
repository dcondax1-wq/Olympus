"""Which strategy a stored run or a write-up belongs to: LIT (live since 2026-10-18) or the previous Liquidity Engine
(archived, research/archive/engine-2026-10-17/README.md). Used by both dashboards (engine/next_api.py for the PC,
tools/build_web_dashboard.py for the phone site) so the Lab shows LIT first and the old engine's research under the Archive.

  strategy_of_run(row)   'lit' | 'engine'   (a run id starting with "lit", or a run tagged "lit")
  strategy_of_doc(stem)  'lit' | 'engine'   (a write-up named lit-*, anything from research/lit/, or the archive README)
  live_baseline(lm)      the stored run the Lab compares LIT runs with ("lit_live"); the engine's stays "baseline"
"""
from __future__ import annotations

LIT_BASELINE = "lit_live"          # tools/lit_losses.py live: the live LIT settings, stored like every other run; re-stored
#                                    on every change of live_model.json lit (2026-10-20: + t_check, scale_in, be_off), the
#                                    version it replaces kept as lit_live_<date> (lit_live_2026-10-18)
ENGINE_BASELINE = "baseline"       # tools/runlib.py baseline: the Liquidity Engine lock of 2026-10-17 (evening)
ENGINE_PREV = "live_2026-10-17am"  # its morning lock
ARCHIVE_DIR = "research/archive/engine-2026-10-17"
ARCHIVE_LABEL = "Archive: previous strategy (Liquidity Engine, Oct 17)"
LIT_METHOD = ("LIT replay (engine/lit.py run_x, the same code as the live loop engine/lit_live.py): 2026 entries on 1-minute bars, "
              "2021-25 on 5-minute bars (reference); live sizing + weekly stop; costs included")
# LIT write-ups shown first in the Lab, in this order (stems; research/lit/masters.md is published as "lit-masters")
LIT_PINNED = ("lit-final", "lit-losses", "lit-experiments", "lit-strategy", "lit-masters")


def is_lit_model(lm: dict | None) -> bool:
    return (lm or {}).get("model") == "lit"


def strategy_of_run(row: dict | None) -> str:
    row = row or {}
    rid = str(row.get("id") or "").lower()
    tags = row.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return "lit" if rid.startswith("lit") or "lit" in [str(t).lower() for t in tags] else "engine"


def strategy_of_doc(stem: str, src: str = "") -> str:
    s, p = str(stem or "").lower(), str(src or "").replace("\\", "/").lower()
    if s.startswith("lit") or "/research/lit/" in "/" + p:
        return "lit"
    return "engine"


def live_baseline(lm: dict | None, run_ids) -> str | None:
    """The run the Lab treats as 'the live strategy': lit_live while live_model.json says lit (if stored), else baseline."""
    ids = set(run_ids or ())
    if is_lit_model(lm) and LIT_BASELINE in ids:
        return LIT_BASELINE
    return ENGINE_BASELINE if ENGINE_BASELINE in ids else None


def pin_rank(stem: str) -> int:
    s = str(stem or "").lower()
    return LIT_PINNED.index(s) if s in LIT_PINNED else len(LIT_PINNED)
