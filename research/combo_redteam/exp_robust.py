import sys, json, time, pickle, collections
import numpy as np
sys.path.insert(0, '/tmp/claude-0/-home-user/1c5df1a3-c52b-5e3b-a05e-7ae8d672b70d/scratchpad/rt')
import rt_sim as R

OUTD = '/tmp/claude-0/-home-user/1c5df1a3-c52b-5e3b-a05e-7ae8d672b70d/scratchpad/rt/'
mode = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
DZ, DZA = R.days_of({'Z'}), R.days_of({'Z', 'A'})
out = {}


def pair(DZ_, DZA_, P, label, **kw):
    sz, nz = R.stats(R.run(DZ_, P, **kw))
    sza, nza = R.stats(R.run(DZA_, P, **kw))
    o = {'Z': sz['net_m'], 'Z+A': sza['net_m'], 'gap': R.gap(nza, nz), 'Z_f10': sz['f10'], 'ZA_f10': sza['f10'],
         'Z_pneg': sz['p_neg'], 'ZA_pneg': sza['p_neg'], 'Z_grad': sz['grad'], 'ZA_grad': sza['grad']}
    print(label, json.dumps(o), flush=True)
    return o


def aday_R(a, z):
    by = collections.defaultdict(float)
    for t in R.TR:
        if t['s'] == 'A' and t['day'] in R.IX and a <= R.IX[t['day']] < z:
            by[t['day']] += t['pts'] / t['risk']
    return sorted(by.items(), key=lambda x: -x[1])


if mode == 'week':
    for sp in ('H1', 'H2', 'REF', 'Y2022'):
        a, z = R.SPANS[sp]
        out[sp] = pair(DZ, DZA, R.week_paths(R.week_blocks(a, z), n, seed=202), f'week {sp}')

elif mode == 'years':
    for sp in ('Y2022', 'Y2023', 'Y2024', 'Y2025'):
        a, z = R.SPANS[sp]
        out[sp] = pair(DZ, DZA, R.day_paths(a, z, n, seed=303), f'day {sp}')

elif mode == 'drop':
    for sp in ('H1', 'H2'):
        a, z = R.SPANS[sp]
        best = aday_R(a, z)
        print(sp, 'ATLAS days', len(best), 'total R', round(sum(r for _, r in best), 1), 'best 5', [(d, round(r, 1)) for d, r in best[:5]],
              'R in best 5', round(sum(r for _, r in best[:5]), 1), flush=True)
        P = R.day_paths(a, z, n, seed=404)
        for k in (5, 10):
            drop = {('A', d) for d, _ in best[:k]}
            out[f'{sp}_dropA{k}'] = pair(DZ, R.days_of({'Z', 'A'}, drop=drop), P, f'{sp} ATLAS trades removed on its best {k} days')
        # remove those whole days from the pool (both bots lose them)
        pool = [i for i in range(a, z) if R.S[i] not in {d for d, _ in best[:5]}]
        out[f'{sp}_dropday5'] = pair(DZ, DZA, R.day_paths(0, 0, n, seed=404, pool=pool), f'{sp} best 5 ATLAS days removed from the pool')

elif mode == 'jack':
    sp = sys.argv[3] if len(sys.argv) > 3 else 'H2'
    a, z = R.SPANS[sp]
    W = R.week_blocks(a, z)
    res = []
    for j, w in enumerate(W):
        pool = [i for b in W[:j] + W[j + 1:] for i in b]
        o = pair(DZ, DZA, R.day_paths(0, 0, n, seed=505, pool=pool), f'{sp} without week {R.S[w[0]]}')
        res.append((R.S[w[0]], o['gap'][0]))
    out[sp] = res

elif mode == 'pool':
    sp = sys.argv[3] if len(sys.argv) > 3 else 'H2'
    B = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    a, z = R.SPANS[sp]
    W = R.week_blocks(a, z)
    rng = np.random.default_rng(606)
    gaps, zs, zas = [], [], []
    t0 = time.time()
    for b in range(B):
        pool = [i for j in rng.integers(0, len(W), size=len(W)) for i in W[j]]
        P = R.day_paths(0, 0, n, seed=1000 + b, pool=pool)
        sz, nz = R.stats(R.run(DZ, P))
        sza, nza = R.stats(R.run(DZA, P))
        gaps.append(float((nza - nz).mean()))
        zs.append(sz['net_m'])
        zas.append(sza['net_m'])
        if b % 20 == 19:
            print(sp, b + 1, round(time.time() - t0), 'gap median', round(float(np.median(gaps))), 'p5', round(float(np.percentile(gaps, 5))),
                  'p10', round(float(np.percentile(gaps, 10))), 'share<=0', round(float(np.mean(np.array(gaps) <= 0)), 3), flush=True)
    g = np.array(gaps)
    out[sp] = {'B': B, 'n': n, 'gap_mean': round(float(g.mean())), 'gap_p5': round(float(np.percentile(g, 5))),
               'gap_p10': round(float(np.percentile(g, 10))), 'gap_p50': round(float(np.median(g))), 'gap_p90': round(float(np.percentile(g, 90))),
               'share_le0': round(float((g <= 0).mean()), 3), 'Z_p10_p50_p90': [round(float(np.percentile(zs, q))) for q in (10, 50, 90)],
               'ZA_p10_p50_p90': [round(float(np.percentile(zas, q))) for q in (10, 50, 90)]}
    print(json.dumps(out[sp]))

elif mode == 'misc':
    for sp in ('H1', 'H2', 'REF'):
        a, z = R.SPANS[sp]
        P = R.day_paths(a, z, n, seed=101)
        out[f'{sp}_stopgrad'] = pair(DZ, DZA, P, f'{sp} slot ends at the 5th payout (MFFU moves to live)', stop_grad=True)
        out[f'{sp}_t1'] = pair(DZ, DZA, P, f'{sp} +1 tick each way', xtick=0.25)
        out[f'{sp}_t2'] = pair(DZ, DZA, P, f'{sp} +2 ticks each way', xtick=0.5)

elif mode == 'armed':
    W = pickle.load(open('/home/user/nq-liquidity-engine/research/runs/_cache/atlas_lit_armed.pkl', 'rb'))['windows']
    AW = collections.defaultdict(list)
    for w in W:
        if w['end'] > w['t0']:
            AW[w['day']].append((w['dir'], w['t0'], w['end']))
    blocked = set()
    cnt = collections.Counter()
    Rb = collections.defaultdict(float)
    for t in R.TR:
        if t['s'] == 'A' and any(d != t['d'] and a0 <= t['et'] < z0 for d, a0, z0 in AW.get(t['day'], ())):
            blocked.add((t['day'], t['et']))
            sp = 'H1' if '2026-01-01' <= t['day'] <= '2026-06-30' else ('H2' if t['day'] >= '2026-07-01' else 'REF')
            cnt[sp] += 1
            Rb[sp] += t['pts'] / t['risk']
    print('ATLAS entries inside an opposite LIT armed window', dict(cnt), {k: round(v, 1) for k, v in Rb.items()}, flush=True)
    TRb = [t for t in R.TR if not (t['s'] == 'A' and (t['day'], t['et']) in blocked)]
    DZAb = R.days_of({'Z', 'A'}, trades=TRb)
    for sp in ('H1', 'H2', 'REF'):
        a, z = R.SPANS[sp]
        out[sp] = pair(DZ, DZAb, R.day_paths(a, z, n, seed=101), f'{sp} ATLAS blocked by LIT opposite armed setups')

elif mode == 'zprio':
    U = pickle.load(open('/home/user/nq-liquidity-engine/research/runs/_cache/second_mix_units.pkl', 'rb'))
    key = {(u['day'], int(u['entry_t']), int(u['dir']), u['src']): u for nm in ('EMA', 'MD', 'SR') for u in U[nm]}
    miss = bad = 0
    TRp = []
    for t in R.TR:
        if t['s'] == 'A':
            u = key.get((t['day'], t['et'], t['d'], t['src']))
            if u is None:
                miss += 1
            else:
                if abs(u['pts'] - t['pts']) > 1e-3 or abs(u['risk'] - t['risk']) > 1e-3:
                    bad += 1
                t = {**t, 'path': (u['pt'], u['po'], u['pw'])}
        TRp.append(t)
    print('ATLAS units matched to the second_mix cache: missing', miss, 'pts/risk mismatch', bad, flush=True)
    R.RULE = 'zprio'
    DZAp = R.days_of({'Z', 'A'}, trades=TRp)
    for sp in ('H1', 'H2', 'REF'):
        a, z = R.SPANS[sp]
        out[sp] = pair(DZ, DZAp, R.day_paths(a, z, n, seed=101), f'{sp} Zlarior priority (closes ATLAS when it enters the other way)')

json.dump(out, open(OUTD + f'robust_{mode}_{"_".join(sys.argv[3:]) or "all"}.json', 'w'), indent=1)
