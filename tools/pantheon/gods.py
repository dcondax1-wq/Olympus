"""The eight gods of PANTHEON: one free source each, its reading today, its vote, its regime states, what it means for NQ.

A god's builder takes the source Store and the session dates and returns a Reading:
  today      value, change (and its window), 5-year percentile, sparkline, the plain-language meaning, a risk lean
  history    `vote` (risk-on +1 .. risk-off -1 per session, known before the session: stats.known_on) and `states`
             ({id: (label, bool per session)}) for research/pantheon/states.json
Votes are direction x z-score / 2 of the god's driver (stats.vote); the direction is the usual textbook reading (falling
yields, a weaker dollar, tighter credit, more liquidity = risk-on for Nasdaq), and the build checks it against NQ honestly.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from tools.pantheon import stats as S


@dataclasses.dataclass(frozen=True)
class God:
    key: str
    name: str
    glyph: str           # the god's emblem: the page draws it (trident, bolt, sword, owl, wheat, sun, moon, bow)
    title: str           # its domain, short
    why: str             # why this god rules this data
    sources: tuple       # Store source ids
    color: str
    council: bool = True  # votes in the Council of the Gods
    futures: bool = True  # False: not futures-market data (display only, never in the council)
    lag: int = 1          # business days from an observation's date until it is published


@dataclasses.dataclass
class Reading:
    ok: bool = False
    value: float | None = None
    text: str = "offline"
    change: float | None = None
    change_text: str = ""
    window: str = ""
    pct: float | None = None
    pct_years: float = 0.0
    asof: str | None = None
    meaning: str = "No data from its source right now."
    lean: str = "neutral"          # risk-on | risk-off | neutral | caution
    vote_today: float | None = None
    subs: list = dataclasses.field(default_factory=list)
    spark: list = dataclasses.field(default_factory=list)
    extra: dict = dataclasses.field(default_factory=dict)
    vote: pd.Series | None = None  # per session (not published as is)
    states: dict = dataclasses.field(default_factory=dict)   # id -> (label, bool per session, first session with data)
    flag: pd.Series | None = None  # ATHENA: event sessions


GODS: tuple = (
    God("poseidon", "POSEIDON", "trident", "Liquidity", "god of the sea: the tide of money (Fed balance sheet minus the TGA and the "
        "reverse repo) that lifts or strands every boat", ("fred:WALCL", "fred:WTREGEN", "fred:RRPONTSYD"), "#38bdf8"),
    God("zeus", "ZEUS", "bolt", "Rates and the curve", "king of the gods: the price of money rules every other price",
        ("fred:DGS10", "fred:DGS2", "fred:T10Y2Y", "fred:DFF", "treasury:curve"), "#facc15"),
    God("ares", "ARES", "sword", "Volatility", "god of war: fear, its term structure and dealer gamma",
        ("cboe:VIX", "cboe:VIX9D", "cboe:VIX3M", "cboe:VXN", "cboe:SKEW", "squeeze:dix"), "#f43f5e", lag=0),
    God("athena", "ATHENA", "owl", "The macro calendar", "goddess of wisdom and strategy: know the battle dates before you fight",
        ("local:events", "ff:week"), "#a78bfa", council=False, lag=0),
    God("demeter", "DEMETER", "wheat", "Positioning (COT)", "goddess of the harvest: who has planted which side (CFTC Traders in "
        "Financial Futures, E-mini Nasdaq-100)", ("cftc:tff_nq",), "#84cc16", lag=3),
    God("helios", "HELIOS", "sun", "The dollar", "the sun that every market orbits: the broad US dollar",
        ("fred:DTWEXBGS",), "#fb923c"),
    God("nyx", "NYX", "moon", "Credit stress", "goddess of the night: high-yield spreads widen before the dark",
        ("fred:BAMLH0A0HYM2", "fred:NFCI"), "#818cf8"),
    God("artemis", "ARTEMIS", "bow", "Crypto risk appetite", "the huntress: Bitcoin runs with the pack's risk appetite. Not "
        "futures data: display only, never in the council", ("fred:CBBTCUSD",), "#e2e8f0", council=False, futures=False),
)
BY_KEY = {g.key: g for g in GODS}


# ------------------------------------------------------------------------------------------------------------ helpers
def _lean(v: float | None) -> str:
    if v is None or not np.isfinite(v):
        return "neutral"
    return "risk-on" if v >= S.VOTE_ON else "risk-off" if v <= -S.VOTE_ON else "neutral"


def _sgn(x: float, nd: int = 2, unit: str = "") -> str:
    return f"{'+' if x >= 0 else '-'}{abs(x):,.{nd}f}{unit}"


def _last(s: pd.Series | None):
    if s is None:
        return None
    s = s.dropna()
    return None if s.empty else float(s.iloc[-1])


def _driver(r: Reading, obs_driver: pd.Series, direction: int, days, lag: int):
    """The vote: today's from the latest observation, history known before each session."""
    z = S.rolling_z(obs_driver.dropna())
    v = S.vote(z, direction)
    r.vote = S.known_on(v, days, lag)
    r.vote_today = None if v.dropna().empty else round(float(v.dropna().iloc[-1]), 3)
    r.lean = _lean(r.vote_today)
    r.extra["z_today"] = None if z.dropna().empty else round(float(z.dropna().iloc[-1]), 2)


def _state(r: Reading, sid: str, label: str, obs_flag: pd.Series, days, lag: int):
    """A regime state per session; before the source's first known value it is False and states.json says `from`."""
    k = S.known_on(obs_flag.dropna().astype(float), days, lag)
    r.states[sid] = (label, k > 0.5, k.first_valid_index())


def _base(r: Reading, s: pd.Series, n: int, window: str, pct: bool = False, years: float = 5.0):
    s = s.dropna()
    r.ok = not s.empty
    r.value = _last(s)
    r.asof = None if s.empty else str(s.index[-1].date())
    r.change = S.change(s, n, pct)
    r.window = window
    r.pct, r.pct_years = S.percentile(s, years)
    r.spark = S.spark(s)


def _daily(*series: pd.Series) -> pd.DataFrame:
    """Several series on one business-day index, carried forward (weekly series become daily step lines)."""
    idx = pd.bdate_range(min(s.index[0] for s in series), max(s.index[-1] for s in series))
    return pd.concat([s.reindex(idx.union(s.index)).ffill().reindex(idx) for s in series], axis=1)


# ------------------------------------------------------------------------------------------------------------ the gods
def poseidon(store, days) -> Reading:
    g, r = BY_KEY["poseidon"], Reading()
    walcl, tga, rrp = (store.get(s) for s in g.sources)
    if walcl is None or tga is None or rrp is None:
        return r
    d = _daily(walcl / 1e3, tga / 1e3, rrp)                   # $bn
    d.columns = ["fed", "tga", "rrp"]
    d = d.dropna()
    net = d["fed"] - d["tga"] - d["rrp"]
    _base(r, net, 20, "4 weeks")
    r.text = f"${r.value / 1e3:,.2f}T"
    r.change_text = _sgn(r.change, 0, "bn") if r.change is not None else ""
    chg20 = net.diff(20)
    _driver(r, chg20, +1, days, g.lag)
    _state(r, "poseidon.net_liquidity_rising", "Net liquidity rising (4-week change > 0)", chg20 > 0, days, g.lag)
    _state(r, "poseidon.net_liquidity_falling", "Net liquidity falling (4-week change < 0)", chg20 < 0, days, g.lag)
    _state(r, "poseidon.rrp_falling", "Reverse repo falling (4 weeks, > $10bn)", d["rrp"].diff(20) < -10, days, g.lag)
    _state(r, "poseidon.rrp_drained", "Reverse repo drained (< $50bn)", d["rrp"] < 50, days, g.lag)
    _state(r, "poseidon.tga_rising", "Treasury cash (TGA) up > $50bn in 4 weeks (drains liquidity)", d["tga"].diff(20) > 50,
           days, g.lag)
    _state(r, "poseidon.fed_qt", "Fed balance sheet shrinking (13 weeks)", d["fed"].diff(65) < 0, days, g.lag)
    r.subs = [{"label": "Fed balance sheet", "value": f"${d['fed'].iloc[-1] / 1e3:,.2f}T"},
              {"label": "Treasury cash (TGA)", "value": f"${d['tga'].iloc[-1]:,.0f}bn"},
              {"label": "Reverse repo", "value": f"${d['rrp'].iloc[-1]:,.1f}bn"}]
    way = "rising" if (r.change or 0) > 0 else "falling"
    r.meaning = (f"Net liquidity is {way} ({r.change_text} in 4 weeks). "
                 + ("More money in the system has usually been a tailwind for Nasdaq."
                    if way == "rising" else "Money is draining out of the system: dips may get bought less eagerly."))
    return r


def zeus(store, days) -> Reading:
    g, r = BY_KEY["zeus"], Reading()
    d10, d2, spread, ff, curve = (store.get(s) for s in g.sources)
    if d10 is None:
        return r
    _base(r, d10, 20, "4 weeks")
    r.text = f"{r.value:.2f}%"
    r.change_text = _sgn(100 * r.change, 0, " bp") if r.change is not None else ""
    chg20 = d10.diff(20)
    _driver(r, chg20, -1, days, g.lag)
    _state(r, "zeus.yields_rising", "10y yield up > 15 bp in 4 weeks", chg20 > 0.15, days, g.lag)
    _state(r, "zeus.yields_falling", "10y yield down > 15 bp in 4 weeks", chg20 < -0.15, days, g.lag)
    _state(r, "zeus.high_rates", "10y yield above 4.5%", d10 > 4.5, days, g.lag)
    inverted = None
    if spread is not None:
        _state(r, "zeus.curve_inverted", "Curve inverted (10y - 2y < 0)", spread < 0, days, g.lag)
        _state(r, "zeus.curve_steepening", "Curve steepening (10y - 2y up > 10 bp in 4 weeks)", spread.diff(20) > 0.10,
               days, g.lag)
        inverted = _last(spread) < 0
        r.subs.append({"label": "10y - 2y", "value": f"{_sgn(100 * _last(spread), 0)} bp"})
    if d2 is not None:
        r.subs.append({"label": "2-year", "value": f"{_last(d2):.2f}%"})
    if ff is not None:
        r.subs.append({"label": "Fed funds", "value": f"{_last(ff):.2f}%"})
    if curve is not None and not curve.empty:
        row = curve.dropna(how="all").iloc[-1]
        r.extra["curve"] = {"date": str(curve.dropna(how="all").index[-1].date()),
                            "tenors": [k for k in row.index if pd.notna(row[k])],
                            "yields": [round(float(row[k]), 2) for k in row.index if pd.notna(row[k])]}
    up = (r.change or 0) > 0
    r.meaning = (f"The 10-year yield is {r.text}, {'up' if up else 'down'} {r.change_text.lstrip('+-')} in 4 weeks. "
                 + ("Rising yields weigh on growth stocks: a headwind for NQ." if up else
                    "Falling yields help long-duration tech: a tailwind for NQ.")
                 + (" The curve is inverted." if inverted else ""))
    return r


def ares(store, days) -> Reading:
    g, r = BY_KEY["ares"], Reading()
    vix, v9, v3m, vxn, skew, sq = (store.get(s) for s in g.sources)
    if vix is None:
        return r
    _base(r, vix, 5, "1 week")
    r.text = f"{r.value:.2f}"
    r.change_text = _sgn(r.change, 2) if r.change is not None else ""
    ratio = None
    if v3m is not None:
        ratio = (vix / v3m).dropna()
        _driver(r, ratio, -1, days, g.lag)
        _state(r, "ares.backwardation", "VIX above VIX3M (term structure inverted: near-term fear)", ratio > 1, days, g.lag)
        r.subs.append({"label": "VIX / VIX3M", "value": f"{_last(ratio):.2f}"})
        r.extra["term_ratio"] = round(_last(ratio), 3)
    _state(r, "ares.vix_above_20", "VIX above 20", vix > 20, days, g.lag)
    _state(r, "ares.vix_above_30", "VIX above 30 (panic)", vix > 30, days, g.lag)
    _state(r, "ares.vix_spike", "VIX up > 20% in a week", vix.pct_change(5) > 0.20, days, g.lag)
    if v9 is not None:
        _state(r, "ares.vix9d_above_vix", "VIX9D above VIX (fear this week)", (v9 / vix).dropna() > 1, days, g.lag)
        r.subs.append({"label": "VIX9D", "value": f"{_last(v9):.2f}"})
    if vxn is not None:
        _state(r, "ares.vxn_above_25", "VXN (Nasdaq vol) above 25", vxn > 25, days, g.lag)
        r.subs.append({"label": "VXN (Nasdaq)", "value": f"{_last(vxn):.2f}"})
    if skew is not None:
        r.subs.append({"label": "SKEW", "value": f"{_last(skew):.0f}"})
    gex_neg = None
    if sq is not None:
        _state(r, "ares.gex_negative", "Dealer gamma negative (GEX < 0: moves get amplified)", sq["gex"] < 0, days, g.lag)
        gex_neg = float(sq["gex"].iloc[-1]) < 0
        r.subs.append({"label": "GEX (S&P)", "value": f"{_sgn(sq['gex'].iloc[-1] / 1e9, 2)}bn"})
        r.subs.append({"label": "DIX", "value": f"{100 * sq['dix'].iloc[-1]:.1f}%"})
        r.extra["gex_asof"] = str(sq.index[-1].date())
    back = ratio is not None and _last(ratio) > 1
    lvl = "calm" if r.value < 16 else "normal" if r.value < 20 else "elevated" if r.value < 30 else "panic-level"
    r.meaning = (f"VIX {r.text} is {lvl}"
                 + (", and the term structure is inverted (VIX above VIX3M): near-term fear, expect wide NQ ranges."
                    if back else ", with a normal upward term structure.")
                 + (" Dealer gamma is negative: moves tend to run." if gex_neg else
                    " Dealer gamma is positive: moves tend to get damped." if gex_neg is False else ""))
    return r


FOMC = ("FOMC", "Federal Funds", "Fed ")


def _events(store) -> pd.DataFrame:
    parts = [p for p in (store.get("local:events"), store.get("ff:week")) if p is not None and len(p)]
    if not parts:
        return pd.DataFrame(columns=["when", "event", "source"])
    ev = pd.concat(parts, ignore_index=True).sort_values("when")
    ev["day"] = ev["when"].dt.normalize()
    ev["hour"] = ev["when"].dt.strftime("%H:%M")
    return ev.drop_duplicates(["day", "hour"], keep="first")      # the curated calendar wins over the FF copy


def athena(store, days, now=None) -> Reading:
    g, r = BY_KEY["athena"], Reading()
    ev = _events(store)
    if ev.empty:
        return r
    now = pd.Timestamp(now or pd.Timestamp.now(tz="America/New_York").tz_localize(None))
    ev_days = pd.Series(1.0, index=pd.DatetimeIndex(ev["day"].unique()))
    flag = pd.Series(days.isin(ev_days.index), index=days)
    r.flag = flag
    first = days[days >= ev["day"].min()][0] if (days >= ev["day"].min()).any() else None
    r.states["athena.event_day"] = ("High-impact US event this session (CPI, NFP, PPI, FOMC...)", flag, first)
    r.states["athena.event_tomorrow"] = ("High-impact US event the session after",
                                         pd.Series((days + S.BDAY).isin(ev_days.index), index=days), first)
    fomc_days = pd.DatetimeIndex(ev[ev["event"].str.contains("|".join(FOMC), case=False)]["day"].unique())
    r.states["athena.fomc_day"] = ("FOMC decision / minutes day", pd.Series(days.isin(fomc_days), index=days), first)
    nxt = ev[ev["when"] >= now - pd.Timedelta(minutes=30)]
    week_end = now.normalize() + pd.Timedelta(days=7)
    r.ok, r.asof = True, str(ev["day"].max().date())
    r.change = float(((ev["when"] >= now) & (ev["when"] < week_end)).sum())
    r.change_text, r.window = f"{int(r.change)} in 7 days", "next 7 days"
    if nxt.empty:
        r.text, r.value = "No event listed", None
        r.meaning = "No high-impact US event on the calendar ahead (the calendar may not be extended yet)."
        return r
    e = nxt.iloc[0]
    dd = (e["day"] - now.normalize()).days
    r.value = float(dd)
    when = "today" if dd == 0 else "tomorrow" if dd == 1 else f"in {dd} days"
    r.text = f"{e['event'][:28]}"
    r.extra["next"] = {"event": e["event"], "when": e["when"].strftime("%a %b %d, %H:%M ET"), "days": int(dd)}
    r.extra["upcoming"] = [{"event": x["event"], "when": x["when"].strftime("%a %b %d %H:%M")} for _, x in nxt.head(5).iterrows()]
    r.subs = [{"label": "Next", "value": f"{e['when']:%a %H:%M} ET ({when})"}] + \
             [{"label": x["when"].strftime("%a %b %d"), "value": x["event"][:30]} for _, x in nxt.iloc[1:4].iterrows()]
    r.lean = "caution" if dd <= 1 else "neutral"
    r.meaning = (f"{e['event']} {when} ({e['when']:%a %H:%M} ET). "
                 + ("Event days move NQ more: the LIT bot's news rules apply; expect a wider range." if dd <= 1 else
                    "Nothing high-impact in the next session: a normal day on the calendar."))
    return r


def demeter(store, days) -> Reading:
    g, r = BY_KEY["demeter"], Reading()
    cot = store.get("cftc:tff_nq")
    if cot is None:
        return r
    am = cot["am_net_pct"]
    _base(r, am, 4, "4 weeks")
    r.text = f"{_sgn(r.value, 1)}% of OI"
    r.change_text = _sgn(r.change, 1, " pts") if r.change is not None else ""
    chg4 = am.diff(4)
    _driver(r, chg4, +1, days, g.lag)
    _state(r, "demeter.am_net_long_rising", "Asset managers adding net longs (4 reports)", chg4 > 0, days, g.lag)
    _state(r, "demeter.am_net_long_falling", "Asset managers cutting net longs (4 reports)", chg4 < 0, days, g.lag)
    _state(r, "demeter.lev_funds_net_short", "Leveraged funds (hedge funds) net short", cot["lev_net"] < 0, days, g.lag)
    _state(r, "demeter.lev_funds_covering", "Leveraged funds net position up (4 reports)", cot["lev_net"].diff(4) > 0, days, g.lag)
    last = cot.iloc[-1]
    r.subs = [{"label": "Hedge funds net", "value": f"{_sgn(last['lev_net'], 0)} ({_sgn(last['lev_net_pct'], 1)}%)"},
              {"label": "Dealers net", "value": _sgn(last["dealer_long"] - last["dealer_short"], 0)},
              {"label": "Open interest", "value": f"{last['oi']:,.0f}"},
              {"label": "Report", "value": f"positions of {cot.index[-1]:%b %d} (out Fri)"}]
    adding = (r.change or 0) > 0
    r.meaning = (f"Asset managers hold {r.text} net long, {'adding' if adding else 'cutting'} ({r.change_text} in 4 weeks); "
                 f"hedge funds are net {'short' if last['lev_net'] < 0 else 'long'}. "
                 "Positioning is slow context: it moves over weeks, not sessions.")
    return r


def helios(store, days) -> Reading:
    g, r = BY_KEY["helios"], Reading()
    usd = store.get("fred:DTWEXBGS")
    if usd is None:
        return r
    _base(r, usd, 20, "4 weeks", pct=True)
    r.text = f"{r.value:.2f}"
    r.change_text = _sgn(r.change, 2, "%") if r.change is not None else ""
    chg = usd.pct_change(20) * 100
    _driver(r, chg, -1, days, g.lag)
    _state(r, "helios.dollar_rising", "Dollar up > 1% in 4 weeks", chg > 1, days, g.lag)
    _state(r, "helios.dollar_falling", "Dollar down > 1% in 4 weeks", chg < -1, days, g.lag)
    ma = usd.rolling(200, min_periods=150).mean()
    _state(r, "helios.dollar_above_200d", "Dollar above its 200-day average", usd > ma, days, g.lag)
    r.subs = [{"label": "200-day average", "value": f"{_last(ma):.2f}"}]
    up = (r.change or 0) > 0
    r.meaning = (f"The broad dollar is {'up' if up else 'down'} {r.change_text.lstrip('+-')} in 4 weeks. "
                 + ("A rising dollar tightens global money: a mild headwind for NQ." if up else
                    "A softer dollar eases global money: a mild tailwind for NQ."))
    return r


def nyx(store, days) -> Reading:
    g, r = BY_KEY["nyx"], Reading()
    hy, nfci = store.get("fred:BAMLH0A0HYM2"), store.get("fred:NFCI")
    if hy is None:
        return r
    _base(r, hy, 20, "4 weeks")
    r.text = f"{100 * r.value:.0f} bp"
    r.change_text = _sgn(100 * r.change, 0, " bp") if r.change is not None else ""
    chg = hy.diff(20)
    _driver(r, chg, -1, days, g.lag)
    _state(r, "nyx.spreads_widening", "High-yield spreads up > 25 bp in 4 weeks", chg > 0.25, days, g.lag)
    _state(r, "nyx.spreads_tightening", "High-yield spreads down > 25 bp in 4 weeks", chg < -0.25, days, g.lag)
    _state(r, "nyx.credit_stress", "High-yield spread above 500 bp (stress)", hy > 5, days, g.lag)
    if nfci is not None:
        _state(r, "nyx.conditions_tight", "Financial conditions tighter than average (NFCI > 0)", nfci > 0, days, g.lag)
        r.subs.append({"label": "Chicago Fed NFCI", "value": f"{_last(nfci):+.3f}"})
    r.subs.append({"label": "History", "value": f"{r.pct_years:g} yrs (FRED keeps 3 yrs of ICE data)"})
    wide = (r.change or 0) > 0
    r.meaning = (f"Junk-bond spreads are {r.text}, {'wider' if wide else 'tighter'} by {r.change_text.lstrip('+-')} in 4 weeks. "
                 + ("Widening credit stress has often come before equity weakness." if wide else
                    "Calm credit: no stress signal from the bond market."))
    return r


def artemis(store, days) -> Reading:
    g, r = BY_KEY["artemis"], Reading()
    btc = store.get("fred:CBBTCUSD")
    if btc is None:
        return r
    _base(r, btc, 20, "4 weeks", pct=True)
    r.text = f"${r.value:,.0f}"
    r.change_text = _sgn(r.change, 1, "%") if r.change is not None else ""
    chg = btc.pct_change(20) * 100
    _driver(r, chg, +1, days, g.lag)
    ma = btc.rolling(50, min_periods=40).mean()
    _state(r, "artemis.btc_above_50d", "Bitcoin above its 50-day average (display only)", btc > ma, days, g.lag)
    _state(r, "artemis.btc_drawdown_20", "Bitcoin > 20% below its 1-year high (display only)",
           btc < 0.8 * btc.rolling(365, min_periods=200).max(), days, g.lag)
    r.subs = [{"label": "50-day average", "value": f"${_last(ma):,.0f}"}, {"label": "Data", "value": "Coinbase via FRED, NOT futures"}]
    up = (r.change or 0) > 0
    r.meaning = (f"Bitcoin is {'up' if up else 'down'} {r.change_text.lstrip('+-')} in 4 weeks: risk appetite is "
                 f"{'hungry' if up else 'cooling'}. Display only (not futures data), never used in the council.")
    return r


BUILDERS = {"poseidon": poseidon, "zeus": zeus, "ares": ares, "athena": athena, "demeter": demeter, "helios": helios,
            "nyx": nyx, "artemis": artemis}
