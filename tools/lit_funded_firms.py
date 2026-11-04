"""LIT on 2-3 funded accounts at once (owner, 2026-10-19): after the MFFU Builder 50K eval, which other accounts should the LIT
bot run so the payouts reach ~$2,000-2,300 a month? MFFU allows 1 active sim-funded Builder 50K per person, so accounts 2-3
come from other MFFU plans (if they can be held next to the Builder) or other firms. Write-up: research/writeups/lit-funded-firms.md.

Trades: the exact live LIT trades (research/runs/_cache/lit_2wk_unit_live.json = run lit_live, 2026: 120 trades), with the
best open profit (mfe) from research/runs/_cache/lit_prop_unit.json (same 630 trades, needed for intraday trailing floors).
Costs: $1.90 a micro round trip on every firm (MFFU's; most firms charge $1.0-2.0), 1 tick of slippage in the points.

Per plan, end to end:
  eval    the plan's eval rules (target, trailing max loss EOD or intraday + lock, soft daily loss, eval best-day rule, min days)
          with an eval sizing tuned to that plan on Jan-Jun 2026 (H1) and checked on Jul-Oct (H2):
          "need": micros so the trade's target covers what is left to pass ("one winner passes", the live two_week idea);
          on a plan with an eval best-day rule c the day's win is capped so it never breaks the rule (first winner <= c x
          target, the next one passes); caps: room_f of the room to the floor, max $ risk (x plan scale), soft daily loss;
          after `until` sessions the normal LIT size (x scale) capped at room_f. No reset (the owner never resets).
  funded  the plan's funded rules (trailing type, lock, soft daily loss, payout buffer, min / max per request (by payout #),
          min cycle profit, request spacing, winning days, best-day rule at payout, split, payout count) with
          engine.sizing.funded_qty tuned per plan on H1 (pct of the room, $ max, best-day win cap), checked on H2.
  life    6 months from the purchase on one Monte Carlo path: buy the eval, pass -> activation -> funded; a failed eval or a
          lost funded account -> buy a new eval the next session. $ net = payouts to the trader - every fee.
  combo   2-3 plans on the SAME paths (same trades: the accounts win and lose together): total $/month, chance that every
          account is lost, chance the 6 months net < 0.
Samples: exact (a fresh eval on every session of the half, played on that half's sessions); MC = 5-session blocks from the half.
2021-25 = reference only (5m entries, LIT PF 1.01 there).

  python tools/lit_funded_firms.py units   # rebuild the unit caches from today's live trades first
  python tools/lit_funded_firms.py all     # grids + finals + combos -> research/lit/funded_firms.json (1 process, ~10 min)
  python tools/lit_funded_firms.py save    # rl.save the runs lit_ff_*
Paper only; nothing live changes.
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import sizing as SZ  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUT = os.path.join(ROOT, "research", "lit", "funded_firms.json")
PV, COMM, SLIP = 2.0, 1.90, 0.25
SPAN = {"2026": ("2026-01-01", "2026-12-31"), "H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"),
        "2021-25": ("2021-01-01", "2025-12-31")}
H_EVAL, H6, H3 = 60, 126, 63
SEARCHED = "2026-10-19"          # the firms' rules (unchanged); the sizing is the live 2026-10-25 preset, the trades are today's
BIG = 1e12


# ================================================================================================ the plans
def F(trail="eod", lock=100.0, dll=None, buffer=None, pay_min=250.0, pay_max=None, pay_pct=None, cyc_min=0.0, every=1,
      days=0, win_days=0, win_min=0.0, cons=None, split=0.9, split_first=None, max_payouts=None, first_wait=1):
    return dict(trail=trail, lock=lock, dll=dll, buffer=buffer, pay_min=pay_min, pay_max=pay_max, pay_pct=pay_pct,
                cyc_min=cyc_min, every=every, days=days, win_days=win_days, win_min=win_min, cons=cons, split=split,
                split_first=split_first, max_payouts=max_payouts, first_wait=first_wait)


def plans():
    P = []

    def add(pid, firm, name, target, mll, price, list_price, *, trail="eod", lock=100.0, dll=None, cons=None, min_days=1,
            micros=40, monthly=False, act=0.0, funded=None, bot="", ok=True, why="", news="", accounts="", src=(), unconf=(),
            price_note=""):
        P.append(dict(id=pid, firm=firm, plan=name, target=float(target), mll=float(mll), trail=trail, lock=lock, dll=dll,
                      cons=cons, min_days=min_days, max_micros=micros, price=price, list_price=list_price, monthly=monthly,
                      act=act, funded=funded, bot=bot, eligible=ok, why=why, news=news, accounts=accounts, sources=list(src),
                      unconfirmed=list(unconf), price_note=price_note, scale=float(mll) / 2000.0))

    S_MFFU = ["https://myfundedfutures.com/plans/rapid", "https://help.myfundedfutures.com/en/articles/14290805-builder-plan-50k-a-comprehensive-guide",
              "https://phidiaspropfirm.com/education/how-many-myfundedfutures-accounts", "https://proptradingvibes.com/blog/myfundedfutures-account-types",
              "https://propdatalab.com/myfundedfutures-payout-rules/", "https://phidiaspropfirm.com/education/myfundedfutures-rapid-plan",
              "https://www.quantvps.com/blog/my-funded-futures-com-promo-codes", "https://www.marketing91.com/my-funded-futures-discount-code/"]
    S_LUC = ["https://lucidtrading.com/product/lucidtest-50k/", "https://proptradingvibes.com/blog/lucidpro-funded-account-rules",
             "https://www.quantvps.com/blog/lucid-trading-prop-firm-payout-rules", "https://proptradingvibes.com/blog/lucid-trading-payout-caps",
             "https://www.eltraderfinanciado.com/en/news/lucid-trading/lucid-trading-optional-daily-loss-limit",
             "https://blog.pickmytrade.trade/best-prop-firms-that-allow-automated-trading-on-tradingview/",
             "https://damnpropfirms.com/futures-prop-firms/lucid-trading/discount/", "https://proptradingvibes.com/blog/lucid-trading-discount"]
    S_FN = ["https://helpfutures.fundednext.com/en/articles/17229762-fundednext-futures-rapid-daily-challenge-all-rules",
            "https://helpfutures.fundednext.com/en/articles/17230292-daily-loss-limit-and-maximum-loss-limit-at-fundednext-futures",
            "https://helpfutures.fundednext.com/en/articles/17229779-fundednext-futures-rapid-daily-fundednext-account-all-rules",
            "https://helpfutures.fundednext.com/en/articles/17229713-fundednext-futures-rapid-pro-fundednext-account-all-rules",
            "https://fundednext.com/blog/futures-rapid-pro-rapid-daily-explained", "https://fundednext.com/futures-challenge-terms",
            "https://helpfutures.fundednext.com/en/articles/14298560-is-the-usage-of-automated-trading-systems-eas-and-bots-allowed-in-fundednext-futures",
            "https://helpfutures.fundednext.com/en/articles/17225732-what-trading-platforms-does-fundednext-futures-offer",
            "https://propscope.net/en/prices/funded-next/", "https://damnpropfirms.com/futures-prop-firms/fundednext/discount/"]
    S_TFY = ["https://help.tradeify.co/en/articles/10468318-guidelines-for-traders", "https://phidiaspropfirm.com/education/tradeify-payout-rules",
             "https://www.fundedfuturesfamily.com/tradeify-consistency-rule/", "https://damnpropfirms.com/account-plans/tradeify-growth-50000/"]
    S_BUL = ["https://tradingfinder.com/props/bulenox/rules/", "https://proptradingvibes.com/blog/bulenox-rules-overview",
             "https://tradecovex.com/guides/bulenox-rules-2026", "https://crosstrade.io/prop-firms/bulenox"]
    S_TOP = ["https://h2tfunding.com/does-topstep-allow-automated-trading/", "https://tradecovex.com/guides/topstep-combine-rules-2026",
             "https://tradegreater.com/blog-tradingview-ninjatrader-prop-firm-automation"]
    BOT_MFFU = "automation allowed with active oversight (mffu_rules.json); NinjaTrader supported"
    # ---------------- MyFundedFutures
    add("mffu_builder_50k", "MyFundedFutures", "Builder 50K (the owner's eval)", 3000, 2000, 91.80, 153, dll=1000, min_days=2,
        funded=F(dll=1000, buffer=2100, pay_min=500, pay_max=2000, days=2, cons=0.5, split=0.8, max_payouts=5, first_wait=2),
        bot=BOT_MFFU, news="allowed", accounts="1 active sim-funded Builder 50K per person", src=S_MFFU,
        unconf=["min days 1 vs 2 (2 used)"], price_note="owner's price with the MFFU code (2026-10-18)")
    add("mffu_builder_25k", "MyFundedFutures", "Builder 25K", 1500, 1000, 63.0, 105, dll=600, min_days=2, micros=20,
        funded=F(dll=600, buffer=1100, pay_min=250, pay_max=1000, days=2, cons=0.5, split=0.8, max_payouts=5, first_wait=2),
        bot=BOT_MFFU, news="allowed", accounts="rules table: 2 active Builder 25K; hero text: 1 per user; next to a Builder 50K: not stated",
        src=S_MFFU, unconf=["whether a Builder 25K can be held next to the Builder 50K (sources conflict)"],
        price_note="owner's price with the MFFU code (2026-10-18)")
    add("mffu_rapid_50k", "MyFundedFutures", "Rapid 50K", 3000, 2000, 104.50, 209, cons=0.5, min_days=2, micros=50,
        funded=F(trail="intra", buffer=2100, pay_min=500, split=0.9),
        bot=BOT_MFFU, news="Tier-1 news banned once funded (sources differ on how strict): LIT trades 08:30 releases",
        accounts="up to 5 active sim-funded 25K/50K (official Rapid page); next to the Builder 50K: inferred, not stated",
        src=S_MFFU, unconf=["eval 50% best-day rule (one source: none)", "holding next to a Builder 50K", "funded news rule"],
        price_note="list $209; ~50% off with an MFFU code (MKT91 / CLUB, Sep-Oct 2026)")
    add("mffu_rapid_eod_50k", "MyFundedFutures", "Rapid EOD 50K", 3000, 2000, 104.50, 209, cons=0.3, min_days=4, micros=30,
        funded=F(buffer=2100, pay_min=500, cyc_min=500, split=0.9),
        bot=BOT_MFFU, news="check", accounts="as Rapid (5 active 25K/50K)", src=S_MFFU,
        unconf=["30% eval rule / 4 days", "funded payout cap none stated", "holding next to a Builder 50K"],
        price_note="list $209; ~50% off with a code")
    # ---------------- Lucid Trading
    add("lucid_pro_50k", "Lucid Trading", "LucidPro 50K (daily loss option on)", 3000, 2000, 115.40, 192, dll=1200,
        funded=F(dll=1200, buffer=2100, pay_min=500, pay_max=[2000, 2500], cyc_min=500, every=3, cons=0.4, split=0.9,
                 max_payouts=5),
        bot="automated systems and trade copiers allowed, no approval (Other Trading Activities page, edited 2026-08-26); "
            "HFT / microscalping banned; NinjaTrader supported", news="allowed",
        accounts="5 funded per household (FAQ per one source; another says 10)", src=S_LUC,
        unconf=["price: list $192, $115-$134 with codes (DLL option makes it cheaper)", "payout cadence every 3 days vs any day",
                "payout caps $2,000 first / $2,500 after", "40% payout rule (one source 30%)"],
        price_note="$115.40 with the daily-loss option + promo (code DGT / VIBES 30-40%)")
    # ---------------- FundedNext Futures
    add("fn_rapid_daily_50k", "FundedNext Futures", "Rapid Daily 50K", 3000, 2000, 169.99, 299.98, dll=1000,
        funded=F(dll=1000, buffer=2100, pay_min=250, pay_max=1200, cyc_min=500, split=0.9, max_payouts=5),
        bot="EAs / bots / AI allowed in Challenge and funded (Futures Challenge Terms 2026-09-25); copying own accounts only; "
            "NinjaTrader, Tradovate, TradingView", news="check",
        accounts="no futures cap found", src=S_FN,
        unconf=["price: list $299.98, $159-$170 with codes", "account concludes after 5 rewards (modelled as the end)",
                "max accounts per trader not found"], price_note="$169.99 with a 43% code (Oct 2026)")
    add("fn_rapid_pro_50k", "FundedNext Futures", "Rapid Pro 50K", 3000, 2000, 169.99, 299.98,
        funded=F(buffer=2100, pay_min=250, pay_max=1200, cyc_min=500, every=3, days=3, cons=0.4, split=0.9, max_payouts=5),
        bot="as Rapid Daily", news="check", accounts="no futures cap found", src=S_FN,
        unconf=["price (assumed = Rapid Daily)", "5 rewards then the end", "optional DLL add-on"],
        price_note="assumed = Rapid Daily with a code")
    # ---------------- reference plans (rules make them unusable for this bot today)
    add("tradeify_growth_50k", "Tradeify", "Growth 50K", 3000, 2000, 72.50, 145, dll=1250,
        funded=F(dll=1250, buffer=3000, pay_min=250, pay_max=[1500, 2000, 2500, 3000], win_days=5, win_min=150, cons=0.35, split=0.9),
        bot="own bots only with proof of sole ownership + live video; the same bot at another prop firm is AGAINST policy",
        ok=False, why="Tradeify bans running the same bot at other firms (help center 'Guidelines for Traders')", news="allowed",
        accounts="5 sim-funded (Growth + Select + Lightning)", src=S_TFY, price_note="$72.50 with a 50% code")
    add("bulenox_eod_50k", "Bulenox", "Qualification Option 2 (EOD) 50K", 3000, 2500, 175.0, 175.0, dll=1100, micros=70, monthly=True,
        act=148.0,
        funded=F(dll=1100, buffer=2600, pay_min=1000, pay_max=[1500, 1500, 1500, BIG], every=5, cons=0.4, split=1.0,
                 split_first=(10000.0, 0.9)),
        bot="automated strategies must be approved by Bulenox; copy trading across own accounts prohibited", ok=False,
        why="bot needs written approval; activation fee and max drawdown not confirmed", news="check",
        accounts="3-11 Master accounts (sources conflict)", src=S_BUL,
        unconf=["max drawdown $2,500", "activation $148 assumed", "monthly price; codes often 80-90% off"])
    add("topstep_50k", "Topstep", "Combine 50K", 3000, 2000, 49.0, 49.0, lock=0.0, cons=0.5, min_days=2, micros=50, monthly=True,
        act=149.0, funded=F(lock=0.0, buffer=0.0, pay_min=125, pay_max=5000, pay_pct=0.5, win_days=5, win_min=150, split=0.9),
        bot="API bots allowed on Combine / XFA (TopstepX), banned on Live; no VPS; NinjaTrader not offered to new sign-ups",
        ok=False, why="the bot's NinjaTrader route is not available to new Topstep accounts (TopstepX API only)", news="allowed",
        accounts="5 XFA", src=S_TOP, unconf=["50% vs 55% eval best day", "XFA payout rules"])
    # LIVE presets since 2026-10-25 (research/writeups/uprisk.md; live_model.json lit_sizing): eval two_week room_f 0.8, no weekly eval stop,
    # then safe_eval; funded 60% of the room, <= $1,500 a trade, a winner <= $2,000, skip_breach. The 25K runs the same rules at half the $
    # (the caps below are in 50K units; the plan scale 0.5 makes them <= $750 and a winner <= $1,000). Earlier versions of this file had the 2026-10-19 values (room_f 0.6; 40% / $800 / $1,500).
    LIVE_EVAL = {"base": "need", "until": 10, "room_f": 0.8, "max_usd": None, "margin": 0.95}   # live two_week -> safe_eval
    FUNDED_MODE = {"pct": 0.6, "pct_min_usd": 100, "pct_max_usd": 1500, "ref": 20, "wk": True, "room_f": None, "max_win": 2000,
                   "slip_ticks": 2, "skip_breach": True}                                    # uprisk.md, mode funded (live)
    FUNDED_25K = FUNDED_MODE        # $ caps are in 50K units: funded_qty multiplies them by the plan scale (0.5), so the 25K gets <= $750 / winner <= $1,000
    for p in P:
        if p["id"] == "mffu_builder_50k":
            p["fixed_eval"], p["fixed_funded"] = LIVE_EVAL, FUNDED_MODE
        elif p["id"] == "mffu_builder_25k":
            p["fixed_eval"], p["fixed_funded"] = LIVE_EVAL, FUNDED_25K
    for pid in ("mffu_rapid_50k", "mffu_rapid_eod_50k"):
        b = next(p for p in P if p["id"] == pid)
        P.append({**b, "id": pid + "_news", "plan": b["plan"] + " (news worst case)", "funded": {**b["funded"], "news_skip": True},
                  "news": "worst case: every trade open at 08:30 ET skipped on the funded account (the real ban covers Tier-1 days only)"})
    return P


EXCLUDED = [  # not simulated again (lit-prop-firms.md has their eval numbers); why the bot cannot run there
    {"firm": "Apex Trader Funding", "why": "automation banned on all account types (help center, Prohibited Activities, 2026)",
     "src": "https://www.quantvps.com/blog/apex-trader-funding-automated-trading-bots"},
    {"firm": "Take Profit Trader", "why": "no bots or algos; every trade manual (PRO rules / Universal Trading Policies)",
     "src": "https://blog.pickmytrade.trade/take-profit-trader-automation-rules-payouts/"},
    {"firm": "Alpha Futures", "why": "fully automated trading prohibited; NinjaTrader / Tradovate gone for new accounts since 2026-07-12",
     "src": "https://fundedtrading.com/propfirm/alpha-futures/"},
    {"firm": "Elite Trader Funding", "why": "semi-automated only (no set-and-forget), rules unsettled across sources",
     "src": "https://blog.traderspost.io/article/elite-trader-funding-review"},
]


# ================================================================================================ trades
_D = {}
_NEWS = set()


def NEWS_IDS():
    """entry_t of every trade open at 08:30 ET (+/- 2 min): the worst case of a funded Tier-1 news ban (every day counted)."""
    if not _NEWS:
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
        for t in data()["trades"]:
            e = dt.datetime.fromtimestamp(t["entry_t"], ny)
            x = dt.datetime.fromtimestamp(t["exit_t"], ny)
            k = e.replace(hour=8, minute=30, second=0, microsecond=0)
            if e <= k + dt.timedelta(minutes=2) and x >= k - dt.timedelta(minutes=2):
                _NEWS.add(t["entry_t"])
        _NEWS.add(-1)
    return _NEWS


def units():
    """Rebuild the two unit caches from TODAY's live LIT trades (tools/lit_edge.trades({}) == run lit_live: be_off 1.25 + the 15-minute check; the
    2026-10-18 caches were the older rule set). -> research/runs/_cache/lit_2wk_unit_live.json + lit_prop_unit.json (gitignored)."""
    from tools import lit_edge as E
    from tools import runlib as rl
    U = E.trades({})
    W = E.wk_mult(U)
    sess = [d[0] for d in rl.load("lit_live")["days"]]
    os.makedirs(CACHE, exist_ok=True)
    tr, pr = [], []
    for u in sorted(U, key=lambda u: u["entry_t"]):
        tr.append({"day": u["day"], "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "dir": int(u["dir"]), "risk": float(u["risk"]),
                   "tgt": float(u["tgt"]), "pts": float(u["pts"]), "w1": float(u["w1"]), "exit": u["exit"], "wk_m": float(W[u["entry_t"]]), "tf": int(u["tf"])})
        pr.append({"day": u["day"], "entry_t": int(u["entry_t"]), "mfe": float(u["mfe"]), "risk_pts": float(u["risk"])})
    json.dump({"sess": sess, "variant": "live (today's rules, rebuilt by lit_funded_firms.py units)", "trades": tr},
              open(os.path.join(CACHE, "lit_2wk_unit_live.json"), "w", encoding="utf-8"))
    json.dump({"sess": sess, "span": "all", "trades": pr}, open(os.path.join(CACHE, "lit_prop_unit.json"), "w", encoding="utf-8"))
    print("units", len(tr), "trades;", sum(1 for t in tr if t["day"] >= "2026"), "in 2026")


def data():
    if not _D:
        d = json.load(open(os.path.join(CACHE, "lit_2wk_unit_live.json"), encoding="utf-8"))
        u = json.load(open(os.path.join(CACHE, "lit_prop_unit.json"), encoding="utf-8"))
        mfe = {t["entry_t"]: max(0.0, float(t["mfe"] or 0.0)) * float(t["risk_pts"]) for t in u["trades"]}
        sess = d["sess"]
        by = collections.defaultdict(list)
        for t in d["trades"]:
            by[t["day"]].append({**t, "up": mfe.get(t["entry_t"], max(0.0, t["pts"]))})
        _D.update(sess=sess, by=[by.get(s, []) for s in sess], trades=d["trades"])
    return _D


def span_idx(span):
    a, z = SPAN[span]
    s = data()["sess"]
    ix = [i for i, d in enumerate(s) if a <= d <= z]
    return ix[0], ix[-1] + 1


_SEQ = {}


def mc_seqs(span, n, length, seed):
    key = (span, n, length, seed)
    if key not in _SEQ:
        a, z = span_idx(span)
        rng = np.random.default_rng(seed)
        out = []
        for _ in range(n):
            s = []
            while len(s) < length:
                b = int(rng.integers(a, z - 5 + 1))
                s.extend(range(b, b + 5))
            out.append(s[:length])
        _SEQ[key] = out
    return _SEQ[key]


# ================================================================================================ eval sizing
def normal_q(t, sc):
    r = 800.0 * sc if t["risk"] <= 20 else 800.0 * sc * 20.0 / t["risk"]
    return max(1, int(r / (t["risk"] * PV)))


def eval_qty(t, st, P, c):
    """c = {"base": "need" | "scaled", "until": N, "room_f", "max_usd" (x scale), "margin"}."""
    sc, risk, tgt = P["scale"], t["risk"], t["tgt"]
    bal, cum, best, k = st["bal"], st["cum"], st["best"], st["k"]
    cons = P["cons"]
    tgt_eff = max(P["target"], best / cons) if cons else P["target"]
    if bal + cum >= tgt_eff:                        # target reached, days missing: 1 micro (min-days trade)
        return 1
    win1 = tgt * PV - COMM
    if c["base"] == "scaled":                       # lit-prop-firms.md "scaled" rule (reference)
        r = 800.0 * sc if risk <= 25 else 800.0 * sc * 25.0 / risk
        q = max(1, int(r / (risk * PV)))
    elif c["base"] == "need" and k < c["until"] and win1 > 0:
        q = max(1, math.ceil((tgt_eff - bal - cum) / win1 - 1e-9))
    else:
        q = normal_q(t, sc)
    if t.get("wk_m", 1.0) < 1.0:
        q = max(1, int(q * t["wk_m"] + 1e-9))
    if cons and win1 > 0:                           # never break the eval best-day rule with this trade's winner
        m = c.get("margin", 0.95)
        pass_day = tgt_eff - bal                    # the day's profit that passes today
        ok_day = cons * bal / (1 - cons)            # the biggest day that is not over cons x (bal + day)
        day_cap = ok_day * m if pass_day <= ok_day * m else max(cons * P["target"] * m, best)
        qc = int(max(0.0, day_cap - cum) / win1)
        if qc < q:
            q = max(1, qc)
    loss1 = (risk + SLIP) * PV + COMM
    caps = []
    if c.get("max_usd"):
        caps.append(int(c["max_usd"] * sc / loss1))
    if c.get("room_f"):
        caps.append(int(c["room_f"] * max(0.0, st["room"]) / (risk * PV)))
    if P["dll"]:
        caps.append(int(max(0.0, P["dll"] + cum) / ((risk + 0.5) * PV + COMM)))
    for cp in caps:
        if cp < q:
            q = max(1, cp)
    return int(min(q, P["max_micros"]))


def run_eval(P, c, seq, by, horizon=H_EVAL):
    """-> (PASS / FAIL / OPEN, sessions)."""
    mll, dll, intra = P["mll"], P["dll"], P["trail"] == "intra"
    lockv = P["lock"] if P["lock"] is not None else BIG
    bal = peak = 0.0
    floor = -mll
    best, active = 0.0, 0
    for k, si in enumerate(seq[:horizon]):
        cum, traded = 0.0, False
        for t in by[si]:
            if dll and cum <= -dll:
                break
            q = eval_qty(t, {"bal": bal, "cum": cum, "best": best, "k": k, "room": bal + cum - floor}, P, c)
            if q <= 0:
                continue
            traded = True
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            up = t["up"] * PV * q
            if dll and cum + low <= -dll:
                pnl = low = -dll - cum - SLIP * PV * q
                up = 0.0
            if bal + cum + low <= floor:
                return "FAIL", k + 1
            if intra and up > 0:
                peak = max(peak, bal + cum + up)
                floor = min(max(floor, peak - mll), lockv)
                if bal + cum + pnl <= floor:
                    return "FAIL", k + 1
            cum += pnl
        bal += cum
        if bal <= floor:
            return "FAIL", k + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if traded:
            active += 1
            best = max(best, cum)
        if bal >= P["target"] and active >= P["min_days"] and (not P["cons"] or best <= P["cons"] * bal + 1e-9):
            return "PASS", k + 1
    return "OPEN", min(len(seq), horizon)


def eval_summary(res):
    N = len(res) or 1
    o = {"n": len(res)}
    for lab, h in (("10", 10), ("15", 15), ("20", 20), ("60", 60)):
        o[f"p{lab}"] = round(100.0 * sum(1 for r, n in res if r == "PASS" and n <= h) / N, 1)
        o[f"f{lab}"] = round(100.0 * sum(1 for r, n in res if r == "FAIL" and n <= h) / N, 1)
    pas = [n for r, n in res if r == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["slow_pass"] = round(100.0 * sum(1 for n in pas if n > 15) / len(pas), 1) if pas else None
    return o


def eval_exact(P, c, span):
    D = data()
    a, z = span_idx(span)
    return eval_summary([run_eval(P, c, list(range(i, z)), D["by"]) for i in range(a, z)])


def eval_mc(P, c, span, n=2000):
    D = data()
    return eval_summary([run_eval(P, c, s, D["by"]) for s in mc_seqs(span, n, H_EVAL, 7)])


def eval_grid():
    G = [{"base": "scaled", "until": 0, "room_f": 0.6, "max_usd": None}]
    for until, rf, mx in itertools.product((10, 999), (0.4, 0.6), (600, 1000)):
        G.append({"base": "need", "until": until, "room_f": rf, "max_usd": mx, "margin": 0.95})
    return G


def eval_score(o):
    """H1 pick: eventual pass minus eventual fail, plus half the 3-week pass (the owner: pass within 2-3 weeks)."""
    return o["p60"] - o["f60"] + 0.5 * o["p15"]


# ================================================================================================ the funded account
def facct(P):
    Fd = P["funded"]
    return {"mll": P["mll"], "lock": Fd["lock"] if Fd["lock"] is not None else BIG, "dll": (Fd["dll"] / P["scale"]) if Fd["dll"] else BIG,   # funded_qty multiplies by scale
            "max_micros": P["max_micros"], "scale": P["scale"]}


def pay_cap(Fd, n):
    pm = Fd["pay_max"]
    if isinstance(pm, list):
        return pm[min(n, len(pm) - 1)]
    return pm if pm is not None else BIG


def run_funded(P, cfg, seq, by, start=0, keep=None):
    """One funded account from seq[start:]. -> dict(paid, pay_at [(k, $)], n, first, blown (k), grad (k))."""
    Fd = P["funded"]
    A = facct(P)
    mll, dll, lockv, intra = P["mll"], Fd["dll"], A["lock"], Fd["trail"] == "intra"
    buf = Fd["buffer"] if Fd["buffer"] is not None else mll + 100
    cfgx = {**cfg, "dll_cap": bool(dll)}
    skip = NEWS_IDS() if Fd.get("news_skip") else None
    bal = peak = 0.0
    floor = -mll
    paid = gross = 0.0
    n_pay, first, last_bal, last_k, cyc = 0, None, 0.0, start - 999, []
    pay_at = []
    for k in range(start, len(seq)):
        si = seq[k]
        cum = 0.0
        traded = False
        for t in by[si]:
            if dll and cum <= -dll:
                break
            if skip and t["entry_t"] in skip:      # news rule (worst case): no trade open at 08:30 ET
                continue
            st = {"room": bal + cum - floor, "cum": cum, "locked": floor >= lockv - 1e-9}
            q = SZ.funded_qty(t, st, cfgx, acct=A)
            if q <= 0:
                continue
            traded = True
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            up = t["up"] * PV * q
            if dll and cum + low <= -dll:
                pnl = low = -dll - cum - SLIP * PV * q
                up = 0.0
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append((t, q, floor - bal - cum))
                return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": k, "grad": None}
            if intra and up > 0:
                peak = max(peak, bal + cum + up)
                floor = min(max(floor, peak - mll), lockv)
                if bal + cum + pnl <= floor:
                    if keep is not None:
                        keep.append((t, q, floor - bal - cum))
                    return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": k, "grad": None}
            cum += pnl
            if keep is not None:
                keep.append((t, q, pnl))
        bal += cum
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if traded:
            cyc.append(cum)
        # ---- payout request at the session's end
        if k - start + 1 < Fd["first_wait"] or k - last_k < Fd["every"]:
            continue
        if Fd["days"] and len(cyc) < Fd["days"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or prof < Fd["cyc_min"]:
            continue
        if Fd["win_days"] and sum(1 for x in cyc if x >= max(Fd["win_min"], 0.01)) < Fd["win_days"]:
            continue
        if Fd["cons"] is not None and cyc and max(cyc) > Fd["cons"] * prof:
            continue
        amt = bal - buf
        if Fd["pay_pct"] is not None:
            amt = min(amt, Fd["pay_pct"] * bal)
        amt = min(amt, pay_cap(Fd, n_pay))
        if amt < max(Fd["pay_min"], 1.0):
            continue
        sp = Fd["split"]
        if Fd["split_first"]:
            lim, sp2 = Fd["split_first"]
            a1 = max(0.0, min(amt, lim - gross))
            share = a1 * sp + (amt - a1) * sp2
        else:
            share = amt * sp
        paid += share
        gross += amt
        n_pay += 1
        pay_at.append((k, share))
        first = first if first is not None else k
        bal -= amt
        last_bal, last_k, cyc = bal, k, []
        if Fd["max_payouts"] and n_pay >= Fd["max_payouts"]:
            return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": k}
    return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": None}


def cost_per_funded(P, ev):
    """Fees per funded account, no reset: one eval attempt = price (monthly plans: price x months until decided)."""
    p = ev["p60"] / 100.0
    if p <= 0:
        return None
    med = ev["pass_med"] or 20
    att = P["price"] * (math.ceil(med / 21) if P["monthly"] else 1)
    return round(att / p + P["act"])


def funded_mc(P, cfg, span, n=1000, cpf=None):
    D = data()
    R = [run_funded(P, cfg, s, D["by"]) for s in mc_seqs(span, n, H6, 23)]
    o = {"paths": len(R)}
    for lab, h in (("3m", H3), ("6m", H6)):
        lost = [r for r in R if r["blown"] is not None and r["blown"] < h]
        paid = [sum(x for k, x in r["pay_at"] if k < h) for r in R]
        o[f"loss_{lab}"] = round(100.0 * len(lost) / len(R), 1)
        o[f"paid_{lab}"] = round(float(np.mean(paid)))
        o[f"paid_p10_{lab}"] = round(float(np.percentile(paid, 10)))
        o[f"any_pay_{lab}"] = round(100.0 * sum(1 for r in R if r["first"] is not None and r["first"] < h) / len(R), 1)
    o["grad_6m"] = round(100.0 * sum(1 for r in R if r["grad"] is not None) / len(R), 1)
    o["per_month"] = round(o["paid_6m"] / 6.0)
    fr = [r["first"] + 1 for r in R if r["first"] is not None]
    o["first_med"] = float(np.median(fr)) if fr else None
    o["payouts_mean"] = round(float(np.mean([r["n"] for r in R])), 2)
    if cpf:
        o["net_per_month"] = round((o["paid_6m"] - o["loss_6m"] / 100.0 * cpf) / 6.0)
    return o


def funded_grid():
    G = []
    for pct, mx, mw in itertools.product((0.25, 0.4, 0.6), (800, 1200), (None, 1000, 1500, 2500)):
        G.append({"pct": pct, "pct_min_usd": 100, "pct_max_usd": mx, "ref": 20, "wk": True, "room_f": None, "max_win": mw,
                  "slip_ticks": 2, "skip_breach": True})
    return G


# ================================================================================================ 6 months from the purchase
def life(P, ce, cf, seq, by, horizon=H6):
    """Buy the eval on session 0; a pass -> activation -> funded; a fail / lost funded -> a new eval the next session.
    -> dict(paid, fees, net, first_pay (k), evals, funded, lost, first_funded (k), pay_by_k)."""
    k, fees, paid, n_eval, n_fund, n_lost = 0, 0.0, 0.0, 0, 0, 0
    first_pay, first_fund = None, None
    pays, lost_at = [], []
    funded_alive_at_end = False
    while k < horizon:
        n_eval += 1
        fees += P["price"]
        r, n = run_eval(P, ce, seq[k:horizon], data()["by"], horizon=horizon - k)
        if P["monthly"]:
            fees += P["price"] * (math.ceil(n / 21) - 1)
        if r != "PASS":
            if r == "OPEN":
                break
            k += n
            continue
        k += n
        n_fund += 1
        fees += P["act"]
        first_fund = first_fund if first_fund is not None else k
        f = run_funded(P, cf, seq[:horizon], by, start=k)
        paid += f["paid"]
        pays.extend(f["pay_at"])
        if f["first"] is not None and first_pay is None:
            first_pay = f["first"]
        if f["blown"] is not None:
            n_lost += 1
            lost_at.append(f["blown"])
            k = f["blown"] + 1
            continue
        if f["grad"] is not None:                  # 5 payouts: MFFU moves you live / FN concludes: buy the next eval
            k = f["grad"] + 1
            continue
        funded_alive_at_end = True
        break
    return {"paid": paid, "fees": fees, "net": paid - fees, "first_pay": first_pay, "first_fund": first_fund, "evals": n_eval,
            "funded": n_fund, "lost": n_lost, "alive": funded_alive_at_end, "pays": pays, "lost_at": lost_at}


_LIFE = {}


def life_mc(P, ce, cf, span, n=1500):
    key = (P["id"], json.dumps(ce, sort_keys=True), json.dumps(cf, sort_keys=True), span, n)
    if key not in _LIFE:
        D = data()
        _LIFE[key] = [life(P, ce, cf, s, D["by"]) for s in mc_seqs(span, n, H6, 31)]
    return _LIFE[key]


def life_summary(L):
    net = np.array([x["net"] for x in L])
    paid = np.array([x["paid"] for x in L])
    fees = np.array([x["fees"] for x in L])
    fp = [x["first_pay"] + 1 for x in L if x["first_pay"] is not None]
    m4_6 = np.array([sum(v for k, v in x["pays"] if k >= 63) for x in L])
    return {"paths": len(L), "net_6m": round(float(net.mean())), "net_per_month": round(float(net.mean()) / 6),
            "net_med_6m": round(float(np.median(net))), "net_p10_6m": round(float(np.percentile(net, 10))),
            "paid_6m": round(float(paid.mean())), "fees_6m": round(float(fees.mean())),
            "neg_6m": round(100.0 * float((net < 0).mean()), 1),
            "months4_6_per_month": round(float(m4_6.mean()) / 3),
            "first_pay_med": float(np.median(fp)) if fp else None,
            "any_pay": round(100.0 * len(fp) / len(L), 1),
            "evals_mean": round(float(np.mean([x["evals"] for x in L])), 2),
            "funded_lost_mean": round(float(np.mean([x["lost"] for x in L])), 2)}


# ================================================================================================ the study
def pick_eval(P):
    rows = []
    for c in eval_grid():
        o = eval_exact(P, c, "H1")
        rows.append({"cfg": c, "H1": o, "score": round(eval_score(o), 1)})
    best = max(rows, key=lambda r: r["score"])
    return best["cfg"], rows


def pick_funded(P, cpf):
    rows = []
    for c in funded_grid():
        o = funded_mc(P, c, "H1", n=400, cpf=cpf)
        rows.append({"cfg": c, "H1": o})
    key = (lambda r: r["H1"]["net_per_month"]) if cpf else (lambda r: r["H1"]["per_month"])
    best = max(rows, key=key)
    return best["cfg"], rows


def study_plan(P, log=print):
    t0 = dt.datetime.now()
    ce, eg = pick_eval(P)
    ce = P.get("fixed_eval") or ce
    ev = {s: eval_exact(P, ce, s) for s in ("H1", "H2", "2026", "2021-25")}
    ev_mc = {s: eval_mc(P, ce, s) for s in ("H1", "H2")}
    scaled = {s: eval_exact(P, eval_grid()[0], s) for s in ("H1", "H2")}
    cpf = {s: cost_per_funded(P, ev_mc[s]) for s in ("H1", "H2")}
    cf, fg = pick_funded(P, cpf["H1"])
    cf = P.get("fixed_funded") or cf
    fu = {s: funded_mc(P, cf, s, n=1500, cpf=cpf.get(s) or cpf["H1"]) for s in ("H1", "H2", "2021-25")}
    fu_def = {s: funded_mc(P, {"pct": 0.4, "pct_min_usd": 100, "pct_max_usd": 800, "ref": 20, "wk": True, "room_f": None,
                               "max_win": 1500, "slip_ticks": 2, "skip_breach": True}, s, n=1500, cpf=cpf.get(s) or cpf["H1"])
              for s in ("H1", "H2")}
    li = {s: life_summary(life_mc(P, ce, cf, s)) for s in ("H1", "H2", "2021-25")}
    log(f"{P['id']}: eval {ce} H1 p10 {ev['H1']['p10']} p60 {ev['H1']['p60']} f60 {ev['H1']['f60']} | H2 p10 {ev['H2']['p10']} "
        f"p60 {ev['H2']['p60']} | funded {cf['pct']}/{cf['pct_max_usd']}/{cf['max_win']} H1 ${fu['H1']['per_month']}/mo loss "
        f"{fu['H1']['loss_6m']} H2 ${fu['H2']['per_month']}/mo loss {fu['H2']['loss_6m']} | life H1 ${li['H1']['net_per_month']}/mo "
        f"H2 ${li['H2']['net_per_month']}/mo ({(dt.datetime.now() - t0).seconds}s)", flush=True)
    return {"id": P["id"], "eval_cfg": ce, "eval": ev, "eval_mc": ev_mc, "eval_scaled": scaled, "eval_grid": eg,
            "cost_per_funded": cpf, "funded_cfg": cf, "funded": fu, "funded_default": fu_def,
            "funded_grid": [{"cfg": r["cfg"], "H1": {k: r["H1"][k] for k in ("per_month", "net_per_month", "loss_6m", "first_med")
                                                      if k in r["H1"]}} for r in fg], "life": li}


def combo(Ps, R, span, n=1500):
    """The plans together on the SAME paths: the accounts trade the same LIT signals, so they win and lose together."""
    per = {P["id"]: life_mc(P, R[P["id"]]["eval_cfg"], R[P["id"]]["funded_cfg"], span, n) for P in Ps}
    ids = [P["id"] for P in Ps]
    net = np.array([[per[i][j]["net"] for i in ids] for j in range(n)])
    tot = net.sum(axis=1)
    m46 = np.array([sum(sum(v for k, v in per[i][j]["pays"] if k >= 63) for i in ids) for j in range(n)]) / 3
    lost_any = np.array([[bool(per[i][j]["lost_at"]) for i in ids] for j in range(n)])
    together = 0                                   # every account lost a funded account within the same 10 sessions
    for j in range(n):
        Ls = [per[i][j]["lost_at"] for i in ids]
        if all(Ls) and any(all(any(abs(a - b) <= 10 for b in L) for L in Ls[1:]) for a in Ls[0]):
            together += 1
    cor = np.corrcoef(net.T) if len(ids) > 1 else np.array([[1.0]])
    return {"plans": ids, "span": span, "paths": n, "net_6m": round(float(tot.mean())), "net_per_month": round(float(tot.mean()) / 6),
            "net_med_6m": round(float(np.median(tot))), "net_p10_6m": round(float(np.percentile(tot, 10))),
            "net_p90_6m": round(float(np.percentile(tot, 90))), "neg_6m": round(100.0 * float((tot < 0).mean()), 1),
            "months4_6_per_month": round(float(m46.mean())), "months4_6_p10": round(float(np.percentile(m46, 10))),
            "p_months4_6_ge_2000": round(100.0 * float((m46 >= 2000).mean()), 1),
            "all_lost_one_funded": round(100.0 * float(lost_any.all(axis=1).mean()), 1),
            "lost_together_10s": round(100.0 * together / n, 1),
            "corr_net": [[round(float(x), 2) for x in row] for row in np.atleast_2d(cor)]}


def overlay_engine_eval(out=None):
    """The live eval is engine/sizing.lit_qty two_week (room 0.8, no weekly eval stop), measured by tools/uprisk.py on 1,000 Monte Carlo paths
    (research/lit/uprisk_eval.json, rf80_nowk). This study's own eval model is an approximation of it: same 2-week pass (53 / 54 vs 53 / 59) but
    fewer fails (f10 11 / 5 vs 18 / 21). For the owner's Builder 50K the engine-faithful 2-week pass / fail / median / slow-pass replace the
    study's in `eval` and `eval_mc` (H1, H2) so every page shows the same figure; the study's own are kept as `eval_study` / `eval_mc_study`.
    Funded and life stay the study's (they agree with uprisk to 2%: $907 / $914 vs $929 / $915 a month)."""
    own = out is None
    if own:
        out = json.load(open(OUT, encoding="utf-8"))
    ue = json.load(open(os.path.join(ROOT, "research", "lit", "uprisk_eval.json"), encoding="utf-8"))["eval"]["rf80_nowk"]
    for row in out["plans"]:
        if row["id"] != "mffu_builder_50k":
            continue
        R = row["results"]
        R.setdefault("eval_study", json.loads(json.dumps(R["eval"])))
        R.setdefault("eval_mc_study", json.loads(json.dumps(R["eval_mc"])))
        for k in ("eval", "eval_mc"):
            for sp in ("H1", "H2"):
                u = ue[sp]
                R[k][sp] = {**R[k][sp], "p10": u["p10"], "f10": u["f10"], "pass_med": u["pass_med"], "slow_pass": u["slow_pass"]}
        R["eval_overlay"] = "2-week pass / fail / median / slow-pass = research/lit/uprisk_eval.json rf80_nowk (the engine's two_week sizing, 1,000 MC paths)"
    if own:
        json.dump(out, open(OUT, "w", encoding="utf-8"), separators=(",", ":"), default=float)
        print("overlay written", OUT)
    return out


def add_trio_reference():
    """Add the Builder 50K + LucidPro + FundedNext trio's 2021-25 line to an existing funded_firms.json (when the top-4 of the run left it out)."""
    out = json.load(open(OUT, encoding="utf-8"))
    ids = ["mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k"]
    if any(sorted(c["plans"]) == sorted(ids) and c["span"] == "2021-25" for c in out["combos"]):
        print("trio 2021-25 already there")
        return
    PL = {P["id"]: P for P in plans()}
    R = {r["id"]: r["results"] for r in out["plans"]}
    out["combos"].append(combo([PL[i] for i in ids], {i: R[i] for i in ids}, "2021-25"))
    json.dump(out, open(OUT, "w", encoding="utf-8"), separators=(",", ":"), default=float)
    print("trio 2021-25 added:", out["combos"][-1]["net_per_month"])


def run_all():
    PL = plans()
    R = {}
    for P in PL:
        R[P["id"]] = study_plan(P)
    elig = [P for P in PL if P["eligible"]]
    base = next(P for P in PL if P["id"] == "mffu_builder_50k")
    others = [P for P in elig if P["id"] != base["id"]]
    C = []
    for k in (1, 2):
        for grp in itertools.combinations(others, k):
            ids = [g["id"] for g in grp]
            for span in ("H1", "H2"):
                C.append(combo([base, *grp], R, span))
            print("combo", [base["id"], *ids], C[-2]["net_per_month"], C[-1]["net_per_month"], flush=True)
    best = sorted({tuple(c["plans"]) for c in C}, key=lambda p: -min(c["net_per_month"] for c in C if tuple(c["plans"]) == p))[:4]
    TRIO = ("mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k")           # the trio the Plutus page and the hub publish: always carry its 2021-25 line
    if tuple(sorted(TRIO)) not in {tuple(sorted(p)) for p in best}:
        best = list(best) + [TRIO]
    for p in best:
        C.append(combo([next(P for P in PL if P["id"] == i) for i in p], R, "2021-25"))
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "lit_funded_firms", "rules_searched": SEARCHED,
           "writeup": "research/writeups/lit-funded-firms.md",
           "trades": "exact live LIT trades (run lit_live; 2026 120 trades), $1.90 a micro, 1 tick slippage",
           "method": {"eval": "exact = fresh eval on every session of the half (that half's sessions, no reset, up to 60 sessions); "
                              "mc = 2,000 evals of 60 sessions in 5-session blocks; sizing picked on H1 by p60 - f60 + 0.5 p15",
                      "funded": "1,500 paths x 126 sessions (5-session blocks); sizing (engine.sizing.funded_qty) picked on H1 by "
                                "($ paid in 6 months - P(lost) x cost per funded account) / 6",
                      "life": "1,500 paths x 126 sessions from the purchase: eval -> funded; fail / lost -> a new eval; net = payouts - fees",
                      "combo": "the plans on the same 1,500 paths as life (same trades)",
                      "cost_per_funded": "price / eventual pass (MC, 60 sessions) + activation; monthly plans x months to the median pass"},
           "excluded": EXCLUDED, "plans": [{**P, "results": R[P["id"]]} for P in PL], "combos": C}
    overlay_engine_eval(out)
    json.dump(out, open(OUT, "w", encoding="utf-8"), separators=(",", ":"), default=float)
    print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB")


def save():
    """rl.save one run per eligible plan: the back-to-back real-history path (eval -> funded -> new eval) over 2021-11..2026-10."""
    from tools import runlib as rl
    out = json.load(open(OUT, encoding="utf-8"))
    D = data()
    for row in out["plans"]:
        P = {k: v for k, v in row.items() if k != "results"}
        R = row["results"]
        T = []
        for span in ("2021-25", "H1", "H2"):
            a, z = span_idx(span)
            seq = list(range(a, z))
            k = 0
            while k < len(seq):
                e, n = run_eval(P, R["eval_cfg"], seq[k:], D["by"], horizon=len(seq) - k)
                k += n
                if e != "PASS":
                    if e == "OPEN":
                        break
                    continue
                keep = []
                f = run_funded(P, R["funded_cfg"], seq, D["by"], start=k, keep=keep)
                for t, q, pnl in keep:
                    ru = t["risk"] * PV * q
                    T.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
                              "r": round(pnl / ru, 3) if ru else 0.0, "pnl": round(pnl, 2), "low": round(min(0.0, pnl), 2),
                              "risk_pts": t["risk"], "qty": q, "risk_usd": round(ru, 2), "half": t.get("wk_m", 1.0) < 1,
                              "exit": t["exit"], "trigger": "LIT-" + ("1m" if t.get("tf") == 1 else "5m"), "mfe": None,
                              "mae": None, "bars_held": None, "regime": "", "mult": None, "tgt_pts": t["tgt"]})
                if f["blown"] is not None:
                    k = f["blown"] + 1
                elif f["grad"] is not None:
                    k = f["grad"] + 1
                else:
                    break
        if not T:
            continue
        T.sort(key=lambda t: t["entry_t"])
        S = rl.score(T, D["sess"])
        e1, e2, f1, f2, l1, l2 = (R["eval"]["H1"], R["eval"]["H2"], R["funded"]["H1"], R["funded"]["H2"], R["life"]["H1"],
                                  R["life"]["H2"])
        verdict = (f"{P['firm']} {P['plan']}: eval p10/f10 H1 {e1['p10']}/{e1['f10']} H2 {e2['p10']}/{e2['f10']}, eventual pass "
                   f"{e1['p60']} / {e2['p60']}%, pass_med {e1['pass_med']} / {e2['pass_med']}; funded MC 6 months ${f1['per_month']} / "
                   f"${f2['per_month']} a month, lost {f1['loss_6m']} / {f2['loss_6m']}%; 6 months from purchase net of fees "
                   f"${l1['net_per_month']} / ${l2['net_per_month']} a month (H1 / H2). "
                   + ("" if P["eligible"] else f"Not usable for the bot: {P['why']}."))
        rl.save("lit_ff_" + P["id"], f"LIT on {P['firm']} {P['plan']} (eval + funded)", "risk",
                "Which accounts should run LIT next to the MFFU Builder 50K, and what do they pay a month net of fees?",
                params={"plan": {k: P[k] for k in ("target", "mll", "trail", "lock", "dll", "cons", "min_days", "max_micros",
                                                   "price", "funded")}},
                sizing={"eval": R["eval_cfg"], "funded": R["funded_cfg"]}, trades=T, scored=S,
                status="adopt-candidate" if P["eligible"] else "info", verdict=verdict,
                notes="tools/lit_funded_firms.py; stored trades = back-to-back real history (eval sized by the plan's eval "
                      "sizing is not stored; only the funded trades). The run library's eval columns are not this plan's "
                      "numbers: those are in the verdict and research/lit/funded_firms.json.",
                writeup="lit-funded-firms", tags=["lit", "lit_funded_firms"])
        print("saved lit_ff_" + P["id"], flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "units":
        units()
    elif cmd == "trio2125":
        add_trio_reference()
    elif cmd == "overlay":
        overlay_engine_eval()
    elif cmd == "all":
        run_all()
    elif cmd == "save":
        save()
    elif cmd == "one":
        P = next(p for p in plans() if p["id"] == sys.argv[2])
        r = study_plan(P)
        print(json.dumps({k: r[k] for k in ("eval_cfg", "eval", "funded_cfg", "funded", "life", "cost_per_funded")}, default=float))
