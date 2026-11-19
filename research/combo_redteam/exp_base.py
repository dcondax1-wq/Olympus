import sys, json, time
sys.path.insert(0, '/tmp/claude-0/-home-user/1c5df1a3-c52b-5e3b-a05e-7ae8d672b70d/scratchpad/rt')
import rt_sim as R
n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
spans = sys.argv[2].split(',') if len(sys.argv) > 2 else ['H1', 'H2', 'REF']
DZ, DZA = R.days_of({'Z'}), R.days_of({'Z', 'A'})
out = {}
for sp in spans:
    t0 = time.time()
    a, z = R.SPANS[sp]
    P = R.day_paths(a, z, n, seed=101)
    sz, nz = R.stats(R.run(DZ, P))
    sza, nza = R.stats(R.run(DZA, P))
    out[sp] = {'Z': sz, 'Z+A': sza, 'gap(mean,se,%paths worse)': R.gap(nza, nz), 'secs': round(time.time() - t0)}
    print(sp, json.dumps(out[sp]), flush=True)
json.dump(out, open(f'/tmp/claude-0/-home-user/1c5df1a3-c52b-5e3b-a05e-7ae8d672b70d/scratchpad/rt/base_{n}.json', 'w'), indent=1)
