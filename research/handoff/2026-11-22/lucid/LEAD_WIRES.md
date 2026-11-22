# day-nqdash3 2026-11-22: the SECOND FIRM (Lucid), LEAD_WIRES

OFF by default. Nothing arms or routes a real order. A LucidPro 50K only exists once the owner adds one. START BOT then still skips it
(held) until the owner records Lucid's written OK (`engine.accounts lucid-ok`). Only then does the owner's own typed phrase arm it,
exactly like the Rapid.

## A. ADD_ACCOUNT.bat: one menu line (a .bat is lead-only)

The phone / PC add page (engine/account_box.py) already offers "LucidPro 50K", and the CLI line works:
`python -X utf8 -m engine.accounts add --plan lucidpro50k --name "<Name>"`. If you want it in the .bat menu too, add item 6 after item 5:

```bat
echo   6  New LucidPro 50K eval     (Zlarior; the second firm: read docs\LUCID_SETUP.md first)
...
if "%c%"=="6" ( "%PY%" -X utf8 -m engine.accounts add --plan lucidpro50k --name "%NAME%" )
```

Mirror the existing items' prompt / NAME variable names; I did not touch the .bat.

## B. What changed (red-team targets)

| File | Change |
|---|---|
| research/lit/lucid_rules.json (new) | Lucid's rules as read on 2026-11-22. Every value has a support.lucidtrading.com URL and a short quote. The price, the platform and the "Trade with Integrity" page are marked UNVERIFIED / UNREAD |
| engine/multi_account.py | ONLY comments + `rules_src` on the existing `lucid_pro_50k` preset (its numbers already matched the cited rules; no value changed) |
| engine/account_cli.py | plan `lucidpro50k` (LIT only, preset lucid_pro_50k); Lucid caps (10 evals / 5 funded per household, from the rules file) that never touch MFFU's slot counts; the Lucid notes at add; `arm()` HOLDS a Lucid row until `cli.lucid_ok`; `lucid_ok()` + CLI `lucid-ok` (records only); a Lucid part in the slots line |
| engine/account_box.py | PLAN_ORDER + "lucidpro50k" (the page lists it last); tests/test_account_box now expects 5 plans |
| engine/clock7.py, tools/web_public/nq/clock7.js (v2; nq.js r32) | firm-aware limit: an id starting with "lucid" = 30 days, "Lucid last day", no MFFU keep-alive act day |
| tools/rehearse_day.py, tools/fleet_dryrun.py | `--lucid`: a LucidPro 50K lane in the fake fleet (Lucid's OK recorded inside the rig so the fake START BOT arms it there) |
| tools/lucid_dryrun.py (new) | the fleet rehearsed without and with the Lucid lane; every existing lane's trades compared row by row |
| tests/test_lucid.py (new, area pc) | 25 checks |
| docs/LUCID_SETUP.md (new) | the owner sheet |

## C. Already in the engine (checked, not changed)

- **Hedging across firms:** AccountRouter.opposite_open covers every routed account whatever the firm (test_lucid e). Lucid also
  bans correlated-asset hedges (ES vs NQ); the bots trade only NQ.
- **DLL fit:** multi_account.Account.qty_for caps every mode so a full stop-out (stop + 2 ticks + $1.90 a micro) fits the account's
  own `dll` left today. test_lucid d checks this over a 128-entry grid. The $1,200 DLL is Lucid's soft pause, and the lock-out uses the
  same number.
- **Inactivity:** the MFFU keep-alive ignores non-MFFU accounts (keepalive._plan_id). Lucid's 30 days only shows on the clock card.

## D. Not done / open

- ATLAS on a Lucid account: not wired. The corvette plan's "LIT + ATLAS $500" needs an ATLAS lane on an extra account (the Rapid has
  one). LIT only for now.
- Funded payout guard (Lucid's 40% best day of the cycle): engine/firms.py already has it as an owner switch (`payout_guard`). The
  preset's funded winner cap is $1,500, which is below 40% of the first max payout's $4,100 profit.
- The price: unverified. Use the owner's real price once he buys (CLAUDE.md).
