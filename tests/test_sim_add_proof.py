"""The scale-in Sim proof (engine/ninjatrader._cli_roundtrip_add step 5, 2026-10-26): after the add, the target is moved under
the market so it fills at once; the test passes only when it fills the whole position (2), the position ends flat and the
OCO stop is cancelled. Against the offline fake NinjaTrader: a broker that resizes the bracket passes; one that ignores the
quantity CHANGE (the bracket stays at 1) fails, so a photo of the Orders tab is no longer needed.

  python -X utf8 -m tests.test_sim_add_proof          # ~2 s, temp folders only
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import ninjatrader as N  # noqa: E402

RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:300]}"), flush=True)


class _NoResize(N._FakeNT):
    """A broker that accepts the quantity CHANGE but keeps the bracket at its old size."""

    def _do(self, line):
        f = line.split(";")
        if f[0] == "CHANGE" and f[4] not in ("", "0"):
            f[4] = "0"
            line = ";".join(f)
        return super()._do(line)


def run(fake_cls):
    tmp = tempfile.mkdtemp(prefix="le_addproof_")
    try:
        folder = os.path.join(tmp, "NinjaTrader 8")
        fake = fake_cls(folder)
        fake.fill_on_change = True
        fake.move(25020.0)
        now = [1792500000.0]
        cfg = {"adapter": "ninjatrader", "sym": "NQ", "nt_account": "Sim101", "nt_folder": folder,
               "params": {"max_micros": 40, "flat_mod": 955}, "nt_state_path": os.path.join(tmp, "st.json"),
               "nt_audit_log": os.path.join(tmp, "oif.log")}
        ad = N.NinjaTraderAdapter(cfg, clock=lambda: now[0])
        ad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
        ad._gate = lambda kind: None
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24980.0, "target": 25100.0, "entry_t": int(now[0])})
        lg = ad.legs[0] if ad.legs else None
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = N._cli_roundtrip_add(ad, lg, lg["fill_px"]) if lg else 9
        pos = ad.position_for(lg["instrument"]) if lg else None
        return r, rc, out.getvalue(), pos
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    r, rc, text, pos = run(N._FakeNT)
    check("a broker that resizes the bracket: the proof passes (target filled 2, flat, OCO stop cancelled)",
          r.get("ok") and rc == 0 and "OK   5. proof" in text, text[-600:])
    check("... and prints SCALE-IN READY", "SCALE-IN READY" in text, text[-300:])
    check("... no Orders-tab photo / Enter prompt any more", "Press Enter" not in text, text[-300:])
    check("... the account ends flat", (pos or {}).get("side") in (None, "FLAT") or int((pos or {}).get("qty") or 0) == 0, pos)
    r2, rc2, text2, pos2 = run(_NoResize)
    check("a broker that keeps the bracket at 1: the proof FAILS (filled 1 of 2)", rc2 != 0 and "FAIL 5. proof" in text2
          and "filled 1" in text2, text2[-600:])
    check("... no SCALE-IN READY line", "SCALE-IN READY" not in text2)
    check("... the safety-net CLOSEPOSITION still leaves the account flat",
          (pos2 or {}).get("side") in (None, "FLAT") or int((pos2 or {}).get("qty") or 0) == 0, pos2)
    n = sum(RES)
    print(f"sim add proof: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
