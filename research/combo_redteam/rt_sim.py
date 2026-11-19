"""Red-team re-implementation of the Builder 50K one-account slot (Zlarior alone vs Zlarior + ATLAS, first-in).
Written from the MFFU rules file + the live engine sizing functions only; does NOT import tools/money/combo_account.py.
Inputs: research/lab/combo_account_trades.json (checked separately against research/anatomy/trades_lit.json)."""
import copy, csv, datetime as dt, json, math, os, sys, collections
import numpy as np

ROOT = '/home/user/wt-combored'
sys.path.insert(0, ROOT)
import logging
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import sizing as SZ, account_b as EAB, multi_account as MA, lit as LIT

PV, COMM, TICK = 2.0, 1.90, 0.25
RULES = json.load(open(os.path.join(ROOT, 'research/lit/mffu_rules.json')))['builder_50k']
EV = {'tgt': RULES['eval']['profit_target']['value'], 'mll': RULES['eval']['max_loss']['value']['amount'], 'lock': 100.0,
      'dll': RULES['eval']['daily_loss_limit']['value']['amount'], 'maxq': RULES['eval']['max_contracts']['value']['micros']}
SF = RULES['sim_funded']
FU = {'mll': SF['max_loss']['value']['amount'], 'lock': 100.0, 'dll': SF['daily_loss_limit']['value']['amount'],
      'buffer': SF['buffer']['value'], 'pay_min': SF['payout_min']['value'], 'pay_max': SF['payout_max']['value'],
      'split': SF['split']['value'], 'cons': SF['consistency']['value'], 'days': SF['payout_days_per_cycle']['value'],
      'max_pay': SF['max_sim_payouts']['value'], 'maxq': SF['max_contracts']['value']['micros'], 'ask': 1500.0}
PRICE = RULES['eval']['price']['value']['owner_paid']
EVAL_MIN_ROOM, FUND_MIN_ROOM = 200.0, 100.0
LEN, GAP = 126, 2
RULE = 'first'

# ---------------------------------------------------------------- live sizing configs (engine functions, live_model.json)
LS = json.load(open(os.path.join(ROOT, 'live_model.json')))['lit_sizing']
ZE = copy.deepcopy(LS)
ZE['two_week']['acct'] = {'target': EV['tgt'], 'mll': EV['mll'], 'lock': EV['lock'], 'dll': EV['dll'], 'max_micros': EV['maxq'], 'scale': 1.0}
ZF = dict(LS['funded'])
ZF_ACCT = {'mll': FU['mll'], 'lock': FU['lock'], 'dll': FU['dll'], 'max_micros': FU['maxq'], 'scale': 1.0, 'cons': FU['cons'],
           'buffer': FU['buffer'], 'pay_max': FU['pay_max']}
ASPEC = EAB.normalize({'account': 'rt', 'plan': 'builder50k', 'eval_start': '2026-01-02'}, lit_account=None)
ASPEC_F = {**ASPEC, 'stage': 'funded', 'funded': {'start': '2026-01-02', 'balance': 50000.0, 'prior': 0.0, 'payouts': {}}}
_c1, _c2 = EAB.sizing_cfg, EAB.funded_cfg
_cache = {}
EAB.sizing_cfg = lambda spec, base=None: _cache.setdefault(('e', spec.get('stage')), _c1(spec, base)) if base is None else _c1(spec, base)
EAB.funded_cfg = lambda spec, base=None: _cache.setdefault(('f', spec.get('stage')), _c2(spec, base)) if base is None else _c2(spec, base)


def sessions(a='2021-11-01', z='2026-10-16'):
    out = set()
    with open(os.path.join(ROOT, 'data', 'NQ_1d.csv')) as fh:
        for r in csv.DictReader(fh):
            d = dt.datetime.fromtimestamp(int(float(r['time'])), dt.timezone.utc).date()
            if a <= d.isoformat() <= z and d.weekday() < 5:
                out.add(d.isoformat())
    return sorted(out)


S = sessions()
IX = {d: i for i, d in enumerate(S)}


def load(path=os.path.join(ROOT, 'research/lab/combo_account_trades.json')):
    d = json.load(open(path))
    return [dict(zip(d['cols'], r)) for r in d['rows']]


TR = load()


def days_of(bots, trades=None, drop=None):
    """session -> trades of these bots, entry order, Z before A on a tie. drop = set of (bot, day) to remove."""
    trades = TR if trades is None else trades
    by = [[] for _ in S]
    for t in trades:
        if t['s'] in bots and t['day'] in IX and not (drop and (t['s'], t['day']) in drop):
            by[IX[t['day']]].append(t)
    for x in by:
        x.sort(key=lambda t: (t['et'], 0 if t['s'] == 'Z' else 1))
    return by


def span(a, z):
    ix = [i for i, d in enumerate(S) if a <= d <= z]
    return ix[0], ix[-1] + 1


SPANS = {'H1': span('2026-01-01', '2026-06-30'), 'H2': span('2026-07-01', '2026-10-16'), 'REF': span('2021-11-01', '2025-12-31'),
         'Y2022': span('2022-01-01', '2022-12-31'), 'Y2023': span('2023-01-01', '2023-12-31'),
         'Y2024': span('2024-01-01', '2024-12-31'), 'Y2025': span('2025-01-01', '2025-12-31')}


# ---------------------------------------------------------------- one account
class Acct:
    def __init__(self, stage):
        self.stage = stage
        R = EV if stage == 'eval' else FU
        self.mll, self.dll, self.maxq = R['mll'], R['dll'], R['maxq']
        self.bal = self.peak = 0.0
        self.floor = -self.mll
        self.s = self.dtr = 0
        self.pays, self.cyc, self.cyc_start, self.k, self.first_k = [], [], 0.0, 0, None
        self.log = None

    def qty(self, t, room, cum, nA):
        trade = {'risk_pts': t['risk'], 'tgt_pts': t['tgt'], 'size_mult': 1.0}
        if self.stage == 'eval':
            st = {'profit': self.bal, 'cum': cum, 'room': room, 'session': self.s, 'n_today': nA, 'wk_pnl': 0.0, 'days_traded': self.dtr}
            if t['s'] == 'Z':
                m0 = LIT.qty_for(t['risk'])
                if not m0:
                    return 0
                return min(int(SZ.lit_qty(m0, trade, ZE, room=room, state=st, learning=None, max_micros=self.maxq)['qty']), self.maxq)
            return min(int(EAB.qty(ASPEC, trade, st)['qty']), self.maxq)
        locked = self.floor >= FU['lock'] - 1e-9 or bool(self.pays)
        st = {'room': room, 'cum': cum, 'locked': locked, 'bal': self.bal, 'session': 99, 'n_today': nA,
              'cycle_start_bal': self.cyc_start, 'cycle_prev': sum(self.cyc), 'best_prev': max(self.cyc) if self.cyc else 0.0,
              'cycle_days_prev': len(self.cyc), 'payouts_n': len(self.pays),
              'cycle_target': max(0.0, FU['buffer'] + FU['pay_max'] - self.cyc_start)}
        if t['s'] == 'Z':
            tz = {**trade, 'size_mult': float(t.get('sm') or 1.0)}
            return min(int(SZ.funded_qty(tz, st, ZF, acct=ZF_ACCT)), self.maxq)
        return min(int(EAB.funded_qty(ASPEC_F, trade, st)['qty']), self.maxq)

    def day(self, ts, xtick=0.0):
        """first-in, one position: returns (cum, traded, breached)"""
        floor = max(self.floor, FU['lock']) if (self.stage == 'funded' and self.pays) else self.floor
        cum, busy, traded, nA = 0.0, -1, False, 0
        minroom = EVAL_MIN_ROOM if self.stage == 'eval' else FUND_MIN_ROOM
        cur = None                                          # (trade, q, pnl) of the open / last position
        for t in ts:
            if t['et'] < busy:
                # Zlarior priority (sensitivity): Zlarior entering OPPOSITE an open ATLAS trade closes ATLAS at market first
                if not (RULE == 'zprio' and t['s'] == 'Z' and cur and cur[0]['s'] == 'A' and cur[0]['d'] != t['d']
                        and cur[0].get('path') is not None):
                    continue                                # a position is open: skip (either side)
                a, qa, pa = cur
                pt, po, pw = a['path']
                k = int(np.searchsorted(pt, t['et']))
                if k < len(pt):
                    pts2 = float(po[k]) - TICK - 2 * xtick
                    new = pts2 * PV * qa - COMM * qa
                    if cum - pa + new <= -self.dll:
                        new = -self.dll - (cum - pa) - TICK * PV * qa
                    cum += new - pa
                    self.cuts = getattr(self, 'cuts', 0) + 1
                busy = -1
            if cum <= -self.dll:
                break
            room = self.bal + cum - floor
            if room < minroom:
                continue
            q = self.qty(t, room, cum, nA)
            if q <= 0:
                continue
            pts = t['pts'] - 2 * xtick
            w1 = min(t['w1'] - xtick, pts)
            pnl = pts * PV * q - COMM * q
            low = min(0.0, w1 * PV * q - COMM * q, pnl)
            if cum + low <= -self.dll:                       # soft daily loss: flattened at the limit (+1 tick)
                pnl = low = -self.dll - cum - TICK * PV * q
            if self.bal + cum + low <= floor:
                return floor - self.bal, True, True
            if self.log is not None:
                self.log.append((t['s'], t['day'], q, round(pnl, 2), round(room, 2)))
            cum += pnl
            traded = True
            nA += t['s'] == 'A'
            busy = t['xt']
            cur = (t, q, pnl)
        return cum, traded, False

    def eod(self):
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - self.mll), FU['lock'] if self.stage == 'funded' else EV['lock'])


class Eval(Acct):
    def __init__(self):
        super().__init__('eval')

    def step(self, ts, xtick=0.0):
        self.s += 1
        cum, traded, br = self.day(ts, xtick)
        if br:
            return 'fail'
        self.bal += cum
        self.dtr += traded
        self.eod()
        if self.bal >= EV['tgt']:
            return 'pass'
        if self.bal - self.floor < EVAL_MIN_ROOM:
            return 'stuck'
        return None


class Funded(Acct):
    def __init__(self):
        super().__init__('funded')
        self.state = 'on'

    def step(self, ts, xtick=0.0):
        k = self.k
        self.k += 1
        cum, traded, br = self.day(ts, xtick)
        if br:
            return 'lost', 0.0
        if abs(cum) > 1e-9:
            self.bal += cum
            self.cyc.append(cum)
            if self.first_k is None:
                self.first_k = k
        self.eod()
        amt = 0.0
        if self.first_k is not None and k >= self.first_k + 2 and len(self.cyc) >= FU['days']:
            cp = sum(self.cyc)
            above = self.bal - FU['buffer']
            if cp > 0 and max(self.cyc) <= FU['cons'] * cp + 1e-9 and above >= max(FU['pay_min'], FU['ask']):
                amt = min(FU['pay_max'], above)
        ev, owner = None, 0.0
        if amt:
            self.pays.append(amt)
            self.bal -= amt
            self.cyc, self.cyc_start = [], self.bal
            owner = amt * FU['split']
            ev = 'paid'
            if len(self.pays) >= FU['max_pay']:
                return 'grad', owner
        fl = max(self.floor, FU['lock']) if self.pays else self.floor
        if self.bal - fl < FUND_MIN_ROOM:
            return 'stuck', owner
        return ev, owner


def slot(seq, D, xtick=0.0, stop_grad=False):
    """6-month slot: eval -> GAP sessions -> funded -> lost / stuck / graduated -> next eval. -> dict"""
    cost, owner, evals = PRICE, 0.0, 1
    e, f, wait = Eval(), None, 0
    ek, first_eval, first_pay, grads, lost = 0, None, None, 0, 0
    for k, si in enumerate(seq):
        ts = D[si]
        if e is not None:
            ek += 1
            r = e.step(ts, xtick)
            if r == 'pass':
                first_eval = first_eval or ('pass', ek)
                e, wait = None, GAP
            elif r in ('fail', 'stuck'):
                first_eval = first_eval or ('fail', ek)
                e, ek = Eval(), 0
                cost += PRICE
                evals += 1
            continue
        if f is None:
            wait -= 1
            if wait <= 0:
                f = Funded()
            continue
        ev, x = f.step(ts, xtick)
        if x:
            owner += x
            first_pay = first_pay or k + 1
        if ev in ('lost', 'stuck', 'grad'):
            grads += ev == 'grad'
            lost += ev != 'grad'
            if ev == 'grad' and stop_grad:
                break
            f, e, ek = None, Eval(), 0
            cost += PRICE
            evals += 1
    return {'net': owner - cost, 'owner': owner, 'cost': cost, 'evals': evals, 'fe': first_eval or ('open', ek),
            'first_pay': first_pay, 'grads': grads, 'lost': lost}


def run(D, paths, xtick=0.0, stop_grad=False):
    return [slot(seq, D, xtick, stop_grad) for seq in paths]


def day_paths(a, z, n, seed, length=LEN, pool=None):
    rng = np.random.default_rng(seed)
    if pool is not None:
        pool = np.asarray(pool)
        return pool[rng.integers(0, len(pool), size=(n, length))]
    return rng.integers(a, z, size=(n, length))


def week_blocks(a, z):
    """the period's sessions grouped into calendar weeks (Mon-Fri) -> list of lists of session indexes"""
    wk = collections.OrderedDict()
    for i in range(a, z):
        y, w, _ = dt.date.fromisoformat(S[i]).isocalendar()
        wk.setdefault((y, w), []).append(i)
    return list(wk.values())


def week_paths(blocks, n, seed, length=LEN):
    rng = np.random.default_rng(seed)
    out = np.empty((n, length), dtype=np.int64)
    for p in range(n):
        seq = []
        while len(seq) < length:
            seq += blocks[rng.integers(0, len(blocks))]
        out[p] = seq[:length]
    return out


def stats(R, months=6.0):
    net = np.array([r['net'] for r in R]) / months
    n = len(R)
    fe = [r['fe'] for r in R]
    pas = [k for o, k in fe if o == 'pass' and k <= 60]
    return {'net_m': round(float(net.mean())), 'se': round(float(net.std(ddof=1) / math.sqrt(n)), 1),
            'p10': round(float(np.percentile(net, 10))), 'p90': round(float(np.percentile(net, 90))),
            'p_neg': round(100 * float((net < 0).mean()), 1), 'evals': round(float(np.mean([r['evals'] for r in R])), 2),
            'owner_m': round(float(np.mean([r['owner'] for r in R])) / months), 'fees_m': round(float(np.mean([r['cost'] for r in R])) / months, 1),
            'p60': round(100 * len(pas) / n, 1), 'pass_med': float(np.median(pas)) if pas else None,
            'f10': round(100 * sum(1 for o, k in fe if o == 'fail' and k <= 10) / n, 1),
            'f60': round(100 * sum(1 for o, k in fe if o == 'fail' and k <= 60) / n, 1),
            'grad': round(float(np.mean([r['grads'] for r in R])), 2)}, net


def gap(a, b):
    d = a - b
    return round(float(d.mean())), round(float(d.std(ddof=1) / math.sqrt(len(d))), 1), round(100 * float((d < 0).mean()), 1)
