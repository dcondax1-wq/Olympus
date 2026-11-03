"""ATHENA library builder (tools/web_public/athena/, 2026-11-03): the owner's searchable library, built offline.

Writes tools/web_public/athena/library.json and jarvis.json. Every entry is short plain words; a term in [[double brackets]] links to
its glossary entry. The numbers that come from a file (the MFFU limits, the owner's prices) are READ from it at build time
(research/lit/mffu_rules.json); the strategy facts are checked against STRATEGY.md / CLAUDE.md, and the build FAILS when a source
sentence it relies on is gone, so the library cannot quietly drift. The rejected list is counted from the 'Tested and rejected'
section of docs/CLAUDE_REFERENCE.md. No network. Rerun after the strategy or the rules change:

    python tools/athena_build.py            (writes)
    python tools/athena_build.py --check    (exit 1 when the committed files are stale)
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "athena")


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


TAGS = [
    {"id": "strategy", "name": "Strategy", "color": "#6aa8ff", "blurb": "How the bot trades, step by step"},
    {"id": "mffu", "name": "MFFU rules", "color": "#ffcf5a", "blurb": "The prop firm's rules that matter"},
    {"id": "rejected", "name": "Rejected", "color": "#ff7a7a", "blurb": "Tested, did not work, and why"},
    {"id": "words", "name": "Words", "color": "#7ef0c4", "blurb": "Every term in plain words"},
    {"id": "playbook", "name": "When...", "color": "#d49bff", "blurb": "What to do when something happens"},
    {"id": "numbers", "name": "Numbers", "color": "#ff9f5a", "blurb": "The results and the money"},
]

# sentences the library relies on: the build fails when one of these is no longer in its source file
MUST = [
    ("STRATEGY.md", "1 tick (0.25 pt) beyond the sweep extreme"),
    ("STRATEGY.md", "banked at 8R"),
    ("STRATEGY.md", "$800 risk up to a 20-point stop"),
    ("STRATEGY.md", "Flat by 15:55 ET"),
    ("STRATEGY.md", "One trade a day"),
    ("STRATEGY.md", "Stop to **breakeven at +1R**"),
    ("STRATEGY.md", "**15-minute check**"),
    ("STRATEGY.md", "limit order at the CISD level"),
    ("STRATEGY.md", "closes more than 0.3R under water"),
    ("CLAUDE.md", "PF 2.91, +$9,919"),
    ("CLAUDE.md", "PF 4.19, +$43,820"),
    ("CLAUDE.md", "Paper only"),
    ("docs/CLAUDE_REFERENCE.md", "## Tested and rejected"),
]


def limits():
    d = json.loads(rd("research", "lit", "mffu_rules.json"))
    L = d["limits"]["builder_50k"]
    L25 = d["limits"]["builder_25k"]
    p50 = d["builder_50k"]["eval"]["price"]["value"]["owner_paid"]
    p25 = d["builder_25k"]["price"]["value"]["owner_paid"]
    return L, L25, p50, p25


def rejected_count():
    t = rd("docs", "CLAUDE_REFERENCE.md")
    i = t.index("## Tested and rejected")
    j = t.index("\n## ", i + 5)
    return len(re.findall(r"^- ", t[i:j], flags=re.M))


def usd(x):
    return "${:,.0f}".format(x)


def entries():
    L, L25, p50, p25 = limits()
    floor0 = 50000 - L["mll"]
    lockbal = 50000 + L["lock"]
    first_pay = 50000 + L["buffer"] + L["pay_min"]
    nrej = rejected_count()
    P50 = "${:,.2f}".format(p50)
    E = []

    def add(id, kind, title, short, body=(), tags=(), src=(), quiz=None, ask=None):
        e = {"id": id, "kind": kind, "tags": [kind, *tags], "title": title, "short": short, "body": list(body), "src": list(src)}
        if quiz:
            e["quiz"] = quiz
        if ask:
            e["ask"] = ask
        E.append(e)

    # ---------------------------------------------------------------- strategy
    S = "STRATEGY.md"
    add("lit-in-one", "strategy", "The bot in one minute",
        "The bot waits for price to poke through an obvious high or low, trap the late traders, then turn. It buys (or sells) the turn with a stop right behind the poke.",
        ["Big groups of traders park their stops and orders at obvious highs and lows. That pile of orders is [[liquidity]].",
         "Price often runs through such a level (a [[sweep]]), traps the traders who reacted, then reverses. The bot trades that reversal.",
         "It is one fixed set of written rules, called LIT. It trades NQ futures as [[mnq]], using [[micro]] contracts, one trade a day at most, paper only.",
         "Every rule was picked on Jan to Jun 2026 and checked on Jul to Oct 2026."], ["numbers"], [S],
        quiz={"q": "What is the idea behind the bot?", "a": "Trade the turn after price pokes through an obvious high or low and traps traders",
              "wrong": ["Buy every dip in the morning", "Follow the news and trade the headline", "Trade a moving average cross"]})
    add("step-1", "strategy", "Step 1: mark the levels",
        "Before anything happens, the bot lists the obvious highs and lows: session highs and lows, yesterday, last week, last month, opening gaps, equal highs or lows.",
        ["Asia, London and New York [[session]] highs and lows count, once their box has closed.",
         "[[pdh]] and PDL (yesterday), the week and the month high and low count.",
         "The weekly and daily opening gaps count, and so do \"equal lows\": two swing lows at the same price, untouched in between.",
         "A level is marked before the [[sweep]], never after. Marking it afterwards would be cheating the test."], [], [S])
    add("step-2", "strategy", "Step 2: wait for a sweep",
        "Price makes a new 2-hour low (or high) and runs through a marked level (a [[sweep]]) by at least half an [[atr]].",
        ["A swept low sets up a long (buy). A swept high sets up a short (sell). Shorts are the mirror image of everything here.",
         "Half an ATR is the filter that stops tiny pokes from counting."], [], [S])
    add("step-3", "strategy", "Step 3: the trap (inducement)",
        "Just before the [[sweep]] a small swing low sat a little above the level. The final push ran through it, so early buyers got stopped out: that is the [[inducement]].",
        ["The small swing is at most 1 [[atr]] above the level and at most 3 hours old.",
         "Nothing may touch it until the last push into the low."], [], [S])
    add("step-4", "strategy", "Step 4: the shift (5m CISD)",
        "Price must close back above the start of the last fall. That close is the [[cisd]], proof the sellers lost control. One strong candle on the way ([[displacement]]) is required.",
        ["The CISD level is the open of the first candle of the last run of down-closing 5-minute candles.",
         "One candle body must be at least 0.8 [[atr]] (that is the displacement).",
         "The bot only looks for entries between 02:00 and 15:30 New York time."], [], [S],
        quiz={"q": "In the bot's rules, which hours can a new trade start?", "a": "02:00 to 15:30 New York time", "wrong": ["09:30 to 11:00 only", "All day and night", "18:00 to 02:00"]})
    add("step-5", "strategy", "Step 5: the entry",
        "A buy [[limit-order]] sits at the CISD level for 30 minutes. After price taps it, the bot waits for a small 1-minute [[cisd]], then buys.",
        ["Once price taps the limit, the bot gives it up to 20 one-minute candles to confirm.",
         "The setup is dropped if the [[sweep]] low breaks, the target trades first, 30 minutes pass with no tap, or it is 15:55.",
         "The bot never chases with a market order. A missed move stays missed."], [], [S])
    add("step-6", "strategy", "Step 6: the stop",
        "The [[stop]] goes 1 [[tick]] beyond the extreme of the [[sweep]], never a fixed distance. Under 8 points or over 80 points means no trade.",
        ["The sweep extreme is the high or low made before the turn. If price goes back through it, the idea was wrong, so you are out.",
         "A wide stop means fewer [[micro]] contracts (less risk). A small stop allows more. Size follows the stop."], [], [S],
        quiz={"q": "Where does the bot put its stop?", "a": "1 tick beyond the sweep extreme", "wrong": ["A fixed 20 points away", "10 ticks under the entry", "At the previous day's close"]})
    add("step-7", "strategy", "Step 7: the target",
        "The target is the 18:00 open plus (long) or minus (short) one day's expected move from the [[vix-band]]. It must be at least 1.5R away, and profit is banked at 8R.",
        ["One move = yesterday's VIX close divided by 100, divided by the square root of 252, times the 18:00 open.",
         "Closer than 1.5[[r]] means no trade. Further than 8R means take the money at 8R. No greed."], [], [S],
        quiz={"q": "Where does the bot bank profit at most?", "a": "At 8R", "wrong": ["At 2R, always", "It never takes profit early", "At 20 points"]})
    add("step-8", "strategy", "Step 8: manage the trade",
        "At +1R the stop moves to [[breakeven]] (plus 1.25 points for costs). A trade that is not working 15 minutes after the fill is closed early. Everything is flat by 15:55.",
        ["Breakeven: after +1R the stop goes to entry + 1.25 points, so a breakeven exit does not lose the costs.",
         "15-minute check: if the trade never reached +0.5R and is more than 0.3R under water, it is closed at the next 1-minute open.",
         "Flat by 15:55 New York time. MFFU needs you flat by 16:10, so there is a safety gap.",
         "Adding to a winner ([[scale-in]]) is built but OFF until a Sim test passes."], [], [S],
        quiz={"q": "When is everything flat?", "a": "15:55 New York time", "wrong": ["17:00 New York time", "Whenever the target hits", "Overnight is fine"]})
    add("step-9", "strategy", "Step 9: the size",
        "Size follows the stop: about $800 of risk up to a 20-point stop, then less as the stop gets wider. Evals use a special size so one winner can pass.",
        ["$800 risk up to a 20-point stop, then 800 x 20 / stop. A 40-point stop risks $400, an 80-point stop $200.",
         "[[micro]] count = risk / (stop x $2), rounded down, at most 40. Under 1 micro means no trade.",
         "After 2 stop-outs in a week the size is halved for the rest of that week (outside the eval sizing)."], [], [S])
    add("one-trade", "strategy", "One trade a day",
        "The bot takes one trade a day at most, and never two at once. Expect 2 to 4 trades a week.",
        ["Fewer than 2 a week is too slow for an eval. The rule is: never make a filter that pauses trading for weeks.",
         "A quiet day with no setup is normal. It is not a bug."], [], [S])
    add("eval-sizing", "strategy", "Eval size: one winner passes",
        "In an eval the bot buys enough [[micro]] contracts that one winning trade to its target reaches the +$3,000 goal, but never risks more than 80% of the room to the floor.",
        ["The target is known at entry, so the bot can work out how many micros one winner needs.",
         "A full stop-out must stay inside 80% of the room and inside the " + usd(L["dll"]) + " daily loss.",
         "The cost: about 1 eval in 5 fails within 2 weeks. The gain: most evals are decided within 2 weeks.",
         "Near the target the size shrinks by itself."], ["mffu"], [S, "research/writeups/uprisk.md"])
    add("funded-sizing", "strategy", "Funded size",
        "On a funded account the bot risks 60% of the room to the floor, at most $1,500 a trade, and a winner is capped at $2,000.",
        ["The cap on a winner is one full payout request.", "When one [[micro]] could reach the floor, the bot skips."], ["mffu"], [S])
    add("paper-only", "strategy", "Paper only, you go live",
        "The bot trades paper (simulated) money. It never arms live trading for you. Going live on the eval is your own decision and MFFU needs you present.",
        ["No real order is placed unless you switch it on yourself.", "Keys and secrets never go in the repo or in chat."], ["mffu"], ["CLAUDE.md"])

    # ---------------------------------------------------------------- numbers
    add("n-headline", "numbers", "How good is it? The headline",
        "2026 so far: [[pf]] 4.19, +$43,820 on paper with costs in. The honest number to expect is the later half: PF 2.91, +$9,919 (about $2,670 a month).",
        ["Quote the Jul to Oct check, not the best-looking number. It was not used to pick the rules.",
         "PF 2.91 means every $1 lost was matched by $2.91 won.",
         "2021 to 2025 is only a reference line. The bot is tuned and judged on 2026."], ["strategy"], ["CLAUDE.md"],
        quiz={"q": "Which result should you quote as the one to expect?", "a": "The Jul to Oct check, PF 2.91", "wrong": ["The best month ever", "The 2026 full-year PF 4.19 only", "Any single winning week"]})
    add("n-money", "numbers", "Money, not only R",
        "Every result shows net dollars and dollars a month next to [[pf]] and [[r]]. R alone hides how much real money is at stake.",
        ["Eval prices you pay: Builder 50K " + P50 + ", Builder 25K " + usd(p25) + ", one-time, $0 activation. Not the list price.",
         "On funded accounts you keep 80% of each payout."], ["mffu"], ["CLAUDE.md", "research/lit/mffu_rules.json"])
    add("n-eval-speed", "numbers", "Eval speed: 2 weeks",
        "An eval should be passed or failed within 2 weeks (10 sessions) and never take more than 3 weeks to pass.",
        ["Each run shows p10 and f10 (passed or failed within 10 sessions), the share decided in 10, and the median sessions to pass.",
         "On the Jul to Oct check, 58.6% passed and 20.9% failed within 2 weeks."], ["mffu"], ["CLAUDE.md", S])
    add("n-two-halves", "numbers", "Two halves rule",
        "A rule change is only kept if it also works on the second half of the data it was not picked on.",
        ["Pick on Jan to Jun 2026, check on Jul to Oct 2026, report both.", "This is how the bot avoids fooling itself with luck."], ["strategy"], ["CLAUDE.md"])

    # ---------------------------------------------------------------- MFFU
    R = "research/lit/mffu_rules.json"
    add("m-floor", "mffu", "The drawdown floor",
        "Your account fails if your balance, with any open trade, touches the floor. On the 50K the floor starts at " + usd(floor0) + ".",
        ["The floor only moves up, and only at the end of the day, from your best end-of-day balance (this is [[eod-trailing]]).",
         "It stops at " + usd(lockbal) + " (start + $" + str(int(L["lock"])) + ") and stays there.",
         "An open loss counts the moment it happens, not at the close.",
         "The room to the floor is what the bot sizes against."], ["words"], [R],
        quiz={"q": "On the Builder 50K, what happens if your balance touches the floor?", "a": "The account fails", "wrong": ["You are paused for the day", "Nothing, it is a warning", "You lose half the profit"]})
    add("m-dll", "mffu", "The daily loss limit",
        "On the 50K the daily loss limit is " + usd(L["dll"]) + ". It is soft: hit it and you are paused for the session, but the account stays open.",
        ["The bot keeps every full stop-out inside this number.", "The Builder 25K limit is " + usd(L25["dll"]) + "."], ["words"], [R])
    add("m-target", "mffu", "The profit target",
        "The 50K eval passes at +" + usd(L["target"]) + ". There is no [[consistency]] rule in the eval. The 25K needs +" + usd(L25["target"]) + ".",
        ["There is no time limit counting down on the eval. The 7-day inactivity rule still applies."], [], [R])
    add("m-size", "mffu", "How many contracts",
        "The 50K allows " + str(L["max_micros"]) + " micros or " + str(L["max_minis"]) + " minis, counted together: 10 micros = 1 mini. The 25K allows " + str(L25["max_micros"]) + " micros.",
        ["Over the limit, the order is rejected.", "A [[micro]] is the small contract."], [], [R])
    add("m-flat", "mffu", "Flat by 16:10",
        "Trading is intraday only. You must be flat by 16:10 New York time and no weekend holds. The bot is flat by 15:55 to be safe.",
        ["The platform closes you at 16:10. Never force orders after it."], [], [R],
        quiz={"q": "MFFU needs you flat by what time?", "a": "16:10 New York time", "wrong": ["17:00 New York time", "15:00 New York time", "Midnight"]})
    add("m-hedge", "mffu", "No long and short at once",
        "You may not hold a long and a short on the same market at the same time, also across your accounts.",
        ["That is why one strategy always has priority when two want opposite sides."], [], [R])
    add("m-bots", "mffu", "Bots are allowed",
        "Bots are allowed with your own settings and you watching. No high-frequency trading and no exploiting simulated fills.",
        ["MFFU requires you to be present for live trading."], [], [R])
    add("m-news", "mffu", "News",
        "News is allowed in the eval and on a sim-funded account. On a live account MFFU advises against trading it.", [], [], [R])
    add("m-idle", "mffu", "The 7-day rule",
        "Trade at least once every " + str(L["inactivity_days"]) + " days or the account can be closed.",
        ["The bot normally trades 2 to 4 times a week, so this only matters in a quiet or holiday week."], [], [R],
        quiz={"q": "How often must you trade so the account is not closed?", "a": "At least once every 7 days", "wrong": ["Once a month", "Every day", "Never, there is no rule"]})
    add("m-pay", "mffu", "Payouts",
        "On a funded account the first payout opens once you are " + usd(L["pay_min"]) + " above the " + usd(L["buffer"]) + " [[buffer]], so a balance of " + usd(first_pay) + ". Payouts run " + usd(L["pay_min"]) + " to " + usd(L["pay_max"]) + ", and 80% is yours.",
        ["Your best day must stay under 50% of the cycle's profit ([[consistency]]).",
         "After " + str(L["max_payouts"]) + " sim payouts the account moves to live.",
         "Check MFFU's own pages before asking for a payout. The rules were last checked on 2026-10-18."], [], [R],
        quiz={"q": "What share of each payout is yours?", "a": "80%", "wrong": ["50%", "100%", "65%"]})
    add("m-price", "mffu", "What the evals cost you",
        "You paid " + P50 + " for the Builder 50K and " + usd(p25) + " for the Builder 25K. One-time payment, no activation fee, no monthly renewal.",
        ["List prices are higher. Always use your real price when comparing."], ["numbers"], [R])

    # ---------------------------------------------------------------- rejected
    D = "docs/CLAUDE_REFERENCE.md"
    rule = "Do not redo it unless you have a genuinely new idea."
    add("x-all", "rejected", "The graveyard: " + str(nrej) + " lists of dead ends",
        "Many ideas were tested properly and dropped. Before you suggest a new strategy idea, search here first.",
        [rule, "The rule for keeping an idea: better in 2026 and better in 2021 to 2025, and still 2 or more trades a week."], [], [D])
    add("x-books", "rejected", "Famous models as taught",
        "ICT 2022, Silver Bullet, Mech/IFVG and similar models, traded exactly as taught, made 0.2 to 1.5 trades a week and a [[pf]] near 1 (break-even).",
        ["That is why the bot has its own rules, written down and tested with costs.", "IFVG is explained here: [[ifvg]]. The bot uses a simpler signal.", rule], [], [D])
    add("x-conf", "rejected", "More confluences (92 tried)",
        "92 extra confirmations, 6 ways to guess the daily bias, and sizing by trade \"grade\" were tested. None held up.",
        ["Adding conditions made trades rarer without making them better. Partials and trailing stops also failed."], [], [D])
    add("x-fixed", "rejected", "Fixed small stops",
        "Stops of a fixed 10 to 15 points got wicked out and lost money. Real structure stops are rarely that small.",
        ["Your own principle: the stop sits at the protected low or high, never a random distance."], [], [D])
    add("x-target", "rejected", "Other targets",
        "No cap, \"draw on liquidity\" and \"last real pool\" targets all did worse (profit factor 1.6 to 2.2 against 3.48).",
        ["The single VIX-band target banked at 8R stayed."], [], [D])
    add("x-streak", "rejected", "Skip after a cold streak",
        "A filter that stops trading after losers had the best profit factor, but paused trading for 14 weeks. You rejected it.",
        ["Rule: prefer a size change over skipping. Never pause for weeks."], [], [D])
    add("x-lit", "rejected", "The LIT extras (none adopted)",
        "Order blocks, higher-timeframe confluences, other hours, extra continuation trades, looser filters and other markets were tested in hundreds of variants. None held in both halves.",
        ["Two small upgrades did pass and are ON: the 15-minute check and [[breakeven]] with costs.", rule], ["strategy"], [D])
    add("x-exit", "rejected", "Fancier exits",
        "Exit on a sharp reversal, trailing behind swings, and [[breakeven]] at other points: 103 variants, none better in both halves.", [rule], [], [D])
    add("x-div", "rejected", "A second strategy alone",
        "Breakout and intraday-momentum ideas were real but too weak to pass a prop eval alone. They only work as a small add-on.",
        ["Prop rules (floor, 50% best day) punish strategies with long losing runs."], [], [D])
    add("x-struct", "rejected", "Structure-based management",
        "Targets at the next pool, half off early, stops to protected swings, trend filters: 101 variants. None beat the live rules in both halves.",
        ["One lead is being watched (a 15-minute structure trail after +1R) but it is not switched on."], [], [D])
    add("x-bholds", "rejected", "Skipping LIT to protect a second account",
        "Letting the second account (ATLAS) block LIT's opposite trade made the 2021 to 2025 result worse. LIT keeps priority.", [rule], [], [D])
    add("x-blitz", "rejected", "A scalper like a person",
        "A fast scalping strategy on its own 25K account, with many exit and filter ideas (about 2,000 variants), did not beat today's rule.", [rule], [], [D])

    # ---------------------------------------------------------------- words
    def w(id, title, short, extra=()):
        add(id, "words", title, short, extra, [], [S], ask={"q": "What does " + title.split(" (")[0] + " mean?", "a": short})

    w("liquidity", "Liquidity", "Obvious highs and lows where lots of traders have parked stops and orders. Price is pulled toward them.")
    w("sweep", "Sweep", "Price runs through a level of liquidity, takes the orders there, then often turns around.", ["The bot needs at least half an [[atr]] past the level."])
    w("inducement", "Inducement (the trap)", "A small swing that lures traders in just before the real move, so they get stopped out.")
    w("displacement", "Displacement", "One strong candle that shows real force. The bot needs a body of at least 0.8 [[atr]].")
    w("cisd", "CISD", "Change in state of delivery: price closes back above the start of the last run of falling candles, showing sellers lost control.")
    w("ifvg", "IFVG", "Inverse fair value gap: a gap that price filled, then flipped to the other side. A signal older models use; this bot uses the [[cisd]] instead.", ["See also [[fvg]]."])
    w("fvg", "FVG", "Fair value gap: a three-candle jump that leaves a hole where little trading happened.")
    w("atr", "ATR", "Average true range: how far a candle usually moves lately. The bot measures things in ATRs so they fit the day.")
    w("r", "R", "Your risk on a trade. If you risk $300 and win $600, that is 2R. Losing the stop is -1R.", ["The bot's target must be at least 1.5R and it banks at 8R."])
    w("pf", "PF (profit factor)", "Money won divided by money lost. Above 1 makes money. 2.91 means $2.91 won per $1 lost.")
    w("drawdown", "Drawdown", "How far your account falls from its best point. The max drawdown is the worst fall in a test.")
    w("eod-trailing", "EOD trailing drawdown", "A floor that follows your best end-of-day balance up and never goes down. It locks at start + $" + str(int(L["lock"])) + ".", ["See [[drawdown]] and [[floor]]."])
    w("floor", "Drawdown floor", "The balance at which the account fails. " + usd(floor0) + " at the start of a 50K eval.")
    w("dll", "Daily loss limit", "How much you may lose in one day. Soft: you are paused, not failed.")
    w("consistency", "Consistency rule", "On funded accounts your best day must be under 50% of the cycle's profit, so one lucky day cannot carry a payout.")
    w("vix-band", "VIX band", "A fair guess of one day's move from the VIX fear index. The bot's target is the 18:00 open plus or minus one such move.")
    w("breakeven", "Breakeven", "Moving the stop to your entry (plus costs) so the trade cannot lose.")
    w("stop", "Stop", "The order that closes a trade at a loss if price goes against you. It defines your risk.")
    w("limit-order", "Limit order", "An order to buy at a price or better, waiting for price to come to you.")
    w("tick", "Tick", "The smallest NQ move: 0.25 points. One MNQ tick is worth $0.50.")
    w("point", "Point", "One full NQ point (4 ticks). One MNQ is worth $2 per point.")
    w("mnq", "MNQ and NQ", "NQ is the Nasdaq-100 future ($20 a point). MNQ is the micro, a tenth of it ($2 a point).")
    w("micro", "Micro", "A micro contract: MNQ. Ten micros equal one mini (NQ).")
    w("session", "Session", "A part of the day: Asia (evening), London (early morning), New York (morning). All times here are New York time.")
    w("pdh", "PDH / PDL", "Previous day high and low: yesterday's top and bottom, a classic level traders watch.")
    w("eval", "Eval", "The test account you pay for. Hit +$3,000 without touching the floor and you pass.")
    w("funded", "Funded account", "The account you get after passing. You trade it (simulated) and request payouts.")
    w("payout", "Payout", "A withdrawal of profit from a funded account. You keep 80%.")
    w("buffer", "Buffer", "Extra profit you must hold on a funded account before the first payout. " + usd(L["buffer"]) + " on the 50K.")
    w("scale-in", "Scale-in", "Adding to a trade that is already working. Built into the bot but switched OFF for now.")
    w("paper", "Paper trading", "Practice trading with fake money, so a bug cannot cost a cent.")
    w("slippage", "Slippage", "Getting a slightly worse price than you wanted. The tests include it.")
    w("commission", "Commission", "The fee per trade. About $" + str(L["comm_rt_micro"]) + " round trip per micro.")
    w("candle", "1m and 5m candles", "One bar of price for one minute or five minutes. The bot finds setups on 5m and enters on 1m.")
    w("trades-week", "Trades a week", "How often the bot trades. Aim: 2 to 4 a week.")
    w("ninjatrader", "NinjaTrader", "The trading platform the PC bot sends orders to (Sim by default).")

    # ---------------------------------------------------------------- playbooks
    add("p-loss", "playbook", "When... I have a loss",
        "A stop-out is a normal cost of the system, not a mistake. Do nothing special: no revenge trade, no bigger size.",
        ["1. Check the stop was hit where the rules say (1 tick beyond the [[sweep]] extreme). If yes, it worked as designed.",
         "2. Do not change any rule because of one loss or one bad week. Rules change only with two-halves proof.",
         "3. After 2 stop-outs in a week the size halves by itself (outside the eval).",
         "4. If the account is near the [[floor]], look at the room left before the next trade; the bot shrinks size by itself.",
         "5. Tell the chat if something looks off. It checks the trade against the bot's twin."], ["strategy"], [S])
    add("p-two-losses", "playbook", "When... two losses in a row",
        "A short losing run is expected. The system's worst runs in testing were still inside the limits. Keep the size the bot gives you.",
        ["Never double up to win it back.", "Never skip trades by hand because you feel unsure: skipping the one winner is the real cost."], [], [S])
    add("p-idle", "playbook", "When... 7 days with no trade",
        "The account can be closed after 7 days with no trade. Watch the calendar in a quiet or holiday week.",
        ["1. Count days since the last fill. Warn yourself at day 5.", "2. Tell the chat at day 5 so it can check for a real setup or a feed problem.",
         "3. Do not force a big trade just to reset the clock. Keep size small and inside the rules.",
         "4. A \"feed stale\" message means the bot will not enter. Fix the feed rather than guessing."], ["mffu"], [R])
    add("p-fail", "playbook", "When... an eval fails",
        "A fail costs the eval fee (" + P50 + "). About 1 eval in 5 fails within 2 weeks by design: the fast size accepts that for speed.",
        ["1. Do not panic and do not change the rules. A fail is in the numbers.",
         "2. Buy the next eval (no reset price is published for one-time plans; check the MFFU dashboard).",
         "3. Tell the chat the new start date so the session count starts fresh.",
         "4. Look for a code or fill problem first, but expect it to be normal variance."], ["numbers", "mffu"], [S, R])
    add("p-pass", "playbook", "When... an eval passes",
        "You hit +" + usd(L["target"]) + ". Stop trading the eval and move the account to funded.",
        ["1. Do not keep trading the eval after the target.", "2. Tell the chat so the funded size (60% of the room, at most $1,500) is switched on.",
         "3. Funded rules differ: payouts need a buffer and a best-day check."], ["mffu"], [S])
    add("p-payout", "playbook", "When... I want a payout",
        "Check three things before you ask: balance, buffer, best day.",
        ["1. Your balance is at least " + usd(first_pay) + " for the first payout (" + usd(L["buffer"]) + " buffer + " + usd(L["pay_min"]) + ").",
         "2. Your best day is under 50% of the cycle's profit ([[consistency]]).",
         "3. Ask for between " + usd(L["pay_min"]) + " and " + usd(L["pay_max"]) + ". You get 80%.",
         "4. Re-check MFFU's own payout page that day. Rules change.",
         "5. After " + str(L["max_payouts"]) + " sim payouts the account moves to live, and you must be present to trade it."], ["mffu"], [R])
    add("p-dll", "playbook", "When... I hit the daily loss limit",
        "You are paused for the session, not failed. Stop for the day.",
        ["1. Do not try to trade it back.", "2. Check that the account is not also close to the floor.", "3. Come back next session with the normal size."], ["mffu"], [R])
    add("p-live", "playbook", "When... I want to go live",
        "Going live is only ever your decision. The bot is paper only and never arms live trading for you.",
        ["1. MFFU requires you to be present for live trading.", "2. Run the Sim test first and read the go-live checklist.", "3. Start with the smallest size."], ["strategy", "mffu"], ["CLAUDE.md"])
    add("p-new", "playbook", "When... I want to try a new idea",
        "Search the rejected list first. Then test it on both halves with costs and 2 or more trades a week.",
        ["Keep it only if it is better in 2026 and in 2021 to 2025.", "Ask the chat to run it. Do not change live rules by hand."], ["rejected"], [D])
    return E


def build():
    for f, s in MUST:
        if s not in rd(*f.split("/")):
            raise SystemExit("athena_build: source sentence missing in " + f + ": " + s)
    E = entries()
    ids = [e["id"] for e in E]
    if len(set(ids)) != len(ids):
        raise SystemExit("athena_build: duplicate ids")
    tagids = {x["id"] for x in TAGS}
    for e in E:
        for t in e["body"] + [e["short"]]:
            for m in re.findall(r"\[\[([a-z0-9-]+)\]\]", t):
                if m not in ids:
                    raise SystemExit(f"athena_build: {e['id']} links to a missing entry [[{m}]]")
        for t in e["tags"]:
            if t not in tagids:
                raise SystemExit(f"athena_build: {e['id']} has an unknown tag {t}")
        e["tags"] = list(dict.fromkeys(e["tags"]))
    lib = {"v": 1, "kind": "olympus-athena-library", "sources": sorted({s for e in E for s in e["src"]}), "tags": TAGS, "entries": E}
    n = {t["id"]: sum(1 for e in E if t["id"] in e["tags"]) for t in TAGS}
    card = {"v": 1, "name": "Athena",
            "status": {"level": "ok", "label": f"{len(E)} entries, offline"},
            "kpis": [{"label": "Entries", "value": str(len(E))}, {"label": "Words", "value": str(n["words"])}, {"label": "Playbooks", "value": str(n["playbook"])}],
            "lines": ["Your library: the strategy, the MFFU rules, what failed and what to do when.", "Search it, or tap a shelf. Quiz me gives 5 questions."],
            "t": 1793700000, "open": "#library", "theme": "#070b14", "stale_after": 2592000}
    return {"library.json": lib, "jarvis.json": card}


def dump(o):
    return json.dumps(o, indent=1, ensure_ascii=False) + "\n"


def main():
    built = build()
    stale = []
    for name, obj in built.items():
        p = os.path.join(OUT, name)
        txt = dump(obj)
        if "--check" in sys.argv:
            if not os.path.exists(p) or open(p, encoding="utf-8").read() != txt:
                stale.append(name)
        else:
            os.makedirs(OUT, exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(txt)
            print("wrote", os.path.relpath(p, ROOT))
    if stale:
        print("stale:", stale)
        sys.exit(1)
    print(len(built["library.json"]["entries"]), "entries")


if __name__ == "__main__":
    main()
