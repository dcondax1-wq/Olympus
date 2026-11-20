# APPLY ON YES: ATLAS funded switches (room 40% / 2 losses -> 1 micro)

Two Decide cards, one patch, both OFF by default. Patch: `research/handoff/2026-11-20/atlasedge/account_b.patch`
(unified diff of `engine/account_b.py` against pc 83287299; `git apply --check` clean). Nothing in it acts until a switch is on.

| Card | Switch (engine/account_b.py, one line) | What it does (funded stage only) | Research (10 ticks, from today's account) |
|---|---|---|---|
| atlas-funded-room-40 | `FUNDED_ON = {"funded_room_pct": 0.4, ...}` | the funded preset's share of the room 0.6 -> 0.4 (never raises it) | $527 / $393 a month, lost 11.0 / 14.0% (today $503 / $402, 17.6 / 21.7%) |
| atlas-funded-streak-1micro | `FUNDED_ON = {..., "streak_shrink": 2}` | after 2 losing closed ATLAS trades in a row, a size of 2+ becomes 1 micro until a winner | $481 / $408, lost 12.2 / 10.9%; both: $478 / $394, 10.1 / 7.7% |

## The 2-minute apply (after the owner's YES)

1. `git apply research/handoff/2026-11-20/atlasedge/account_b.patch` (once, for either card; on an already-patched tree skip it).
2. Flip the one line for the card(s) said YES to, in `engine/account_b.py`:
   - room 40%: `FUNDED_ON = {"funded_room_pct": 0.4, "streak_shrink": None}`
   - streak:   `FUNDED_ON = {"funded_room_pct": None, "streak_shrink": 2}`
   - both:     `FUNDED_ON = {"funded_room_pct": 0.4, "streak_shrink": 2}`
   Per-account override (PC-local data/account_b.json block): the same key there wins; `null` there = off for that account.
3. Tests, then ship: `python -X utf8 -m tests.test_atlas_funded_switches` (now runs on the repo itself; it expects FUNDED_ON
   all None, so update its first check to the flipped value with a one-line reason), `python -X utf8 -m tests.test_account_b_funded --quick`,
   `python -X utf8 -m tests.test_account_b_min_room`, then `python tools/ship.py`. Close the card(s) in decisions.json (status "yes").
   It acts on the PC after the auto-update once ATLAS is flat (the spec is read at the bot's start / the account's next reload).

## Sim101 check (3 steps, before the owner arms anything; never the funded account)

1. **Read-only on the PC** after the update (no order, no arm): prints the switches, the share used and today's streak from
   ATLAS's own state file:
   `python -X utf8 -c "import json;from engine import account_b as A;import os;s=A.normalize(A.raw_cfg()) or {};f=A.state_file();b=json.load(open(f)) if os.path.exists(f) else {};print('room_pct',s.get('funded_room_pct'),'share',(A.funded_cfg(s)['funded']['pct'] if s.get('funded') else 'not funded'),'streak_shrink',s.get('streak_shrink'),'streak now',A.loss_streak(b.get('closes'),(s.get('funded') or {}).get('start')),'problem',s.get('problem'))"`
   Expect: share 0.4 (room 40% on) or 0.6 (off); the streak = ATLAS's last losing closes in a row since the funded start; problem None.
2. **One Sim day**: the dress-rehearsal sandbox (tests/test_rehearsal_blitz.py setup: LIT on Sim101, ATLAS on its Sim account,
   paper fills) or the PC's own Sim101 run with ATLAS's block pointed at a Sim account: each ATLAS entry's log line
   "ROUTED MARKET q MNQ ... size ..." must show the funded reason with the 40% share, and after 2 Sim losses in a row the
   next entry says "loss streak: 2 losing trades in a row (>= 2): 1 micro until a winner" and routes 1.
3. **Restart check**: stop / start the bot on Sim while the streak is 2+: the first entry after the restart still routes
   1 micro (the streak comes from the saved closes, tests b), then a Sim winner puts the next entry back to the normal size.
   Only then the owner arms the real funded account himself (typed phrase).

## What the tests prove (tests/test_atlas_funded_switches.py, 35/35 on a patched copy)

a. OFF by default: FUNDED_ON all None; a block without the keys sizes exactly like today (60% preset + soft daily loss) on
   192 states even at a 9-loss streak; bad values are a problem (not traded); the eval stage never uses them; the one-line
   switch turns both on and a block null turns them off for that account.
b. the streak counter: only losing closes in a row at the end, by exit time, since the funded start (the eval's losses
   never count); a winner or a $0 scratch resets it; two losses on one day count as two; **survives a restart** (a fresh
   AccountB on the saved state file reads 2 and sizes 1 micro); **only ATLAS's own closes on that account** (another Name
   never reads the file); switch off = the funded state has no new key.
c. the size: on 960 states, streak < 2 = today's size; streak >= 2 = 1 micro when today's is 2+, 1 stays 1, 0 stays 0:
   **never below 1 micro, never above today's size**; the log reason says why; a lost account stays 0.
d. **room 40% on a replay**: every ATLAS trade of the real 2026 day order and of 2021-25 (1 and 10 ticks, fresh and today's
   account; 97-225 trades a path), at the state the research engine (tools/atlas_risk PGF3, the engine behind the card's
   numbers) had at that trade, sizes exactly as the research pct 0.4 + the same soft daily loss guard: 0 mismatches; the
   card's stored research rows are the room-40% rows.
Existing suites on the same patched copy = their result on today's repo: test_account_b_funded --quick 62/62,
test_account_b_local 28/28, test_account_b_min_room 21/21, test_acctb_not_placed 44/44, test_atlas_armed PASS,
test_second_account_b (see REPORT), test_atlas_v2_shadow 33/42 on both (9 failures already on pc, not from this patch).

Note on timing: the research updates the streak at the end of each session; live it updates after each close (a second
trade the same day already sees the first's loss). That can only shrink sooner, the safe side.

## The patch

```diff
--- a/engine/account_b.py
+++ b/engine/account_b.py
@@ -99,6 +99,11 @@
 MAX_AGE_S = 45                  # a 5m open seen later than this is not probed (the research fills at the open)
 MIN_ROOM = 100.0
 ZOMBIE_ON = {"eval_min_room": 200.0, "last_bullet": 0.8}      # owner "Fix atlas" 2026-11-15 (atlas-deep.md)
+# ATLAS funded-stage switches (2026-11-20), OFF = None. The lead flips one value after the owner's YES on its Decide card:
+#   "funded_room_pct": 0.4   card atlas-funded-room-40     (risk 40% of the room a trade instead of the preset's 60%)
+#   "streak_shrink": 2       card atlas-funded-streak-1micro (after 2 losing trades in a row, 1 micro until a winner)
+# A key in the account_b block overrides this (null there = off for that account). Funded stage only.
+FUNDED_ON = {"funded_room_pct": None, "streak_shrink": None}
 CLOSE_RETRY_S = 10              # an unconfirmed close of B's position is re-sent at most this often (pre-launch audit A4)
 TICK, PV, COMM = 0.25, 2.0, 1.90
 ADAPTER_FACTORY = None          # tests: (spec, adapter cfg) -> adapter; None = engine/live.ADAPTERS
@@ -280,6 +285,21 @@
             out["problem"] = out["problem"] or f"last_bullet {ab.get('last_bullet')!r} must be a share of the room in (0, 1]"
         else:
             out["last_bullet"] = float(lb)
+    # funded-stage switches (2026-11-20, research/writeups/atlas-edge-2026-11-20.md / atlas-risk-real-fills-2026-11-20.md):
+    # FUNDED_ON (repo default, None = OFF) unless the block has the key; OFF = today's behaviour, unchanged
+    sw = {k: (ab.get(k) if k in ab else FUNDED_ON.get(k)) for k in FUNDED_ON}
+    if sw["funded_room_pct"] is not None:                  # "room 40%": share of the room a funded trade may risk
+        fp = _num(sw["funded_room_pct"])
+        if fp is None or not 0.1 <= fp <= 0.6:
+            out["problem"] = out["problem"] or f"funded_room_pct {sw['funded_room_pct']!r} must be a share of the room in [0.1, 0.6]"
+        else:
+            out["funded_room_pct"] = float(fp)
+    if sw["streak_shrink"] is not None:                    # after N losing closed trades in a row: 1 micro until a winner
+        ss = _num(sw["streak_shrink"])
+        if ss is None or int(ss) != ss or not 1 <= int(ss) <= 10:
+            out["problem"] = out["problem"] or f"streak_shrink {sw['streak_shrink']!r} must be a whole number of losses (1-10)"
+        else:
+            out["streak_shrink"] = int(ss)
     out["keys"] = [k for k in keys if isinstance(S.get(k), dict) and S[k].get("on", True) and not S[k].get("cloud_only")]
     # the stage (2026-10-26): "eval" (absent = the eval, exactly as before) or "funded" (python -m engine.account_b --to-funded)
     stage = str(ab.get("stage") or "eval").strip().lower()
@@ -457,9 +477,35 @@
     s = MA.normalize({"id": "acctb", "preset": spec["preset"], "mode": "funded", "adapter": "paper"})
     c = MA.sizing_cfg(base, s)
     c["mode"] = "funded"
+    if spec.get("funded_room_pct") is not None:            # OFF by default: the preset's own share (25K: 0.6)
+        c["funded"] = {**(c.get("funded") or {}), "pct": min(float((c.get("funded") or {}).get("pct", 0.6)), float(spec["funded_room_pct"]))}
     return c
 
 
+def loss_streak(closes, start: str | None = None) -> int:
+    """Losing closed trades in a row at the end of account B's own closes ([day, exit_t, pnl, entry_t], this account
+    only: _load drops another account's file), since the funded start; a close with pnl >= 0 ends the streak."""
+    n = 0
+    rows = sorted((c for c in closes or [] if len(c) >= 3 and (not start or str(c[0]) >= str(start))), key=lambda c: int(c[1]))
+    for c in reversed(rows):
+        if float(c[2]) < 0:
+            n += 1
+        else:
+            break
+    return n
+
+
+def streak_cap(r: dict, spec: dict, state: dict) -> dict:
+    """streak_shrink (OFF by default): after N losing trades in a row, 1 micro until the next winner. Only lowers a size of
+    2+ to 1: never below 1 micro, never above the size it was given."""
+    n = spec.get("streak_shrink")
+    q = int(r.get("qty") or 0)
+    ls = int((state or {}).get("loss_streak") or 0)
+    if not n or q <= 1 or ls < int(n):
+        return r
+    return {**r, "qty": 1, "reasons": list(r.get("reasons") or []) + [f"loss streak: {ls} losing trades in a row (>= {int(n)}): 1 micro until a winner"]}
+
+
 def funded_qty(spec: dict, trade: dict, state: dict | None, base: dict | None = None, key: str | None = None) -> dict:
     """Micros for one account B entry in the FUNDED stage: engine/sizing.funded_qty on the plan's funded preset (the same
     rule as a funded extra account, engine/multi_account), never above the plan's max micros, then the learned cost reserve
@@ -487,6 +533,7 @@
     r = _weighted(r, weight(spec, key))
     if int(r.get("qty") or 0) > q0:
         r = {**r, "qty": q0, "reasons": list(r.get("reasons") or []) + [f"member weight: never above the funded caps -> {q0}"]}
+    r = streak_cap(r, spec, state)
     return dll_guard(r, float(risk), R, state)
 
 
@@ -741,6 +788,8 @@
                 st["room"] = round(float(st["balance"]) + float(st["cum"]) - lock, 2)
                 st["locked"] = True
         st["n_today"] = self.entries_today(today)
+        if self.spec.get("streak_shrink"):
+            st["loss_streak"] = loss_streak(self.closes, F["start"])
         return st
 
     def _state_raw(self, now=None):
```
