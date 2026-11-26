"""Red team 2026-11-26 (big-execution): engine/live.ADAPTERS["ninjatrader"] = nt_socket.make_adapter never gives a LIVE account the
socket transport, even with nt_transport "socket" / LE_NT_TRANSPORT=socket and PAPER_ONLY flipped; an account-lookup error = the
file bridge. No adapter is built for real here (the two classes are replaced by markers).
    python -X utf8 -m tests.test_nt_transport_rt
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import nt_socket as S        # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def main():
    keep = (S.NtSocketAdapter, S.NinjaTraderAdapter, S.PAPER_ONLY, S.nt.resolve_account, S.is_sim, os.environ.get(S.TRANSPORT_ENV))
    S.NtSocketAdapter = lambda c, **k: "socket"
    S.NinjaTraderAdapter = lambda c, **k: "file"
    try:
        S.is_sim = lambda a: str(a).lower().startswith("sim")
        for paper_only in (True, False):
            S.PAPER_ONLY = paper_only
            S.nt.resolve_account = lambda c: "MFFUEVAL123"
            check(f"live account + nt_transport socket (PAPER_ONLY {paper_only}): the file bridge",
                  S.make_adapter({"nt_transport": "socket"}) == "file")
            os.environ[S.TRANSPORT_ENV] = "socket"
            check(f"live account + LE_NT_TRANSPORT=socket (PAPER_ONLY {paper_only}): the file bridge", S.make_adapter({}) == "file")
            os.environ.pop(S.TRANSPORT_ENV, None)
        S.nt.resolve_account = lambda c: "Sim101"
        check("Sim account + socket: the socket transport", S.make_adapter({"nt_transport": "socket"}) == "socket")
        check("Sim account, no switch: the file bridge (default OFF)", S.make_adapter({}) == "file")
        S.nt.resolve_account = lambda c: (_ for _ in ()).throw(RuntimeError("lookup"))
        check("account lookup error + socket: the file bridge (never a crash in the factory)",
              S.make_adapter({"nt_transport": "socket"}) == "file")
    finally:
        S.NtSocketAdapter, S.NinjaTraderAdapter, S.PAPER_ONLY, S.nt.resolve_account, S.is_sim = keep[:5]
        if keep[5] is None:
            os.environ.pop(S.TRANSPORT_ENV, None)
        else:
            os.environ[S.TRANSPORT_ENV] = keep[5]
    print(f"\nnt transport red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
