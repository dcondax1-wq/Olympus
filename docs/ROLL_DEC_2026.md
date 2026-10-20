# December 2026 roll: MNQ 12-26 -> MNQ 03-27

**Verdict: ready.** If you switch the NinjaTrader chart on Wednesday evening and NinjaTrader merges "back adjusted", the
bot's whole LIT window, every level (PDH/PDL, PWH/PWL, PMH/PML, the gaps) and every LIT trade come out exactly as they
would on clean data. Tested end to end on the real September roll (`python -X utf8 -m tests.test_roll`, 23/23). The March
contract trades about 1% higher (~300 pts). That one number is what the roll changes.

## What to do, day by day (times ET)

| When | You do | The bot does |
|---|---|---|
| **Any day before Wed 12-09** (once) | NinjaTrader: **Tools > Options > Market data > Merge policy = "Merge back adjusted"** (normally the default, so just check it). The LE_BarFeed chart keeps **Days to load 30**. | nothing |
| **Wed 12-09, 17:00-17:59** (the CME break; any time from 15:55 to Thu 01:55 also works) | On the LE_BarFeed chart, change the instrument to **MNQ 03-27**, then save the workspace. Leave the bot running. Then run `python tools/roll_check.py`. It should say "Chart bars are on: MNQ 03-27" and OK. | LE_BarFeed rewrites its files on March prices. On its next poll the bot moves its archive and the TradingView history onto March and logs `... back-adjusted onto NinjaTrader's contract` once. A one-off `feed revised ... bars` warning is normal. |
| **Thu 12-10, 00:00** | nothing | Orders switch to **MNQ 03-27** by themselves (8 days before the Dec 18 expiry). LIT's first entries come at 02:00, already on March. |
| **Thu 12-10, morning** | Check that the bot's log has the "back-adjusted" line and that the levels on the dashboard sit near the price (not ~300 pts below it). Run `python tools/roll_check.py` again. | trades as usual |
| **Mon 12-14, 18:00** | nothing | TradingView's NQ1! switches to March. The bot does not need it: it already shifts the old export itself. |
| **Tue 12-15 or later** (the weekend is fine) | Make a fresh TradingView export (NQ1! 5m + 1m, B-ADJ **off**, Volume on) into one folder and run `python tools/import_tv.py <folder>`. It reports **NEW roll NQZ26 -> NQH27, gap +xxx**. Run it again with `--roll`, then commit the `data/` files so the cloud gets them. | The history files move onto March for good. This is for research and the dashboards; the live bot works without it. Re-run `python tools/export_backtest.py` afterwards. |
| Fri 12-18 | nothing | The December contract expires. The bot holds nothing overnight, so nothing has to be rolled. |

The cloud monitor needs nothing from you. It gets March bars from the PC's heartbeat, moves its own store onto March,
and its LIT trades match the PC's (test scenario E).

## What goes wrong, and how you would see it

1. **The chart stays on MNQ 12-26 after Thursday 00:00.** The bot reads December prices but sends orders to March: the
   stop and target land ~300 pts off the fill. `roll_check` says **ACTION: switch the NinjaTrader chart to MNQ 03-27**.
   If you cannot switch it, stop the bot until you can (or start it with `--instrument "MNQ 12-26"` and switch both
   back together later).
2. **Merge policy "Merge non back adjusted".** NinjaTrader's own history jumps ~300 pts at its rollover, and the bot
   cannot repair that: its levels would be wrong for weeks. `roll_check` says **ACTION ... Merge back adjusted**. Fix:
   set the policy, reload the chart, delete `data\nt_bars\NQ_*.csv`, restart the bot.
3. **No shared bars** (the chart loaded only a few days and the bot was off for a while). The bot cannot measure the
   gap, so the old bars stay ~300 pts low. The log says `... bars missing ... load more days on the NinjaTrader chart`.
   Fix: Days to load 30.
4. **Switched late (after Thursday) or "Do not merge".** This is handled now (fix of 2026-10-20 in `engine/pcbars.py`):
   the real spread between the two contracts drifts with the price, and the bot used to miss it. A small step of ~5-15
   pts can remain in the older bars.

## Files

`tests/test_roll.py` (the simulation) · `tools/roll_check.py` (your check) · `tools/import_tv.py` (the export import, with
roll detection) · `engine/pcbars.py` (the back-adjustment) · `engine/ninjatrader.py` `nt_instrument` (the order contract).
