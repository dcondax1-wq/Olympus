"""START BOT waits on a fake clock: seconds the owner sits watching each step, for a tree passed as argv[1].
Scenario (a typical PC): server answers 3.2 s after start_server; stop takes 1.3 s; NinjaTrader connects 7 s after the
prompt; the chart fix lands 20 s after the prompt; the launch checklist goes green 12 s after the bot starts (the startup
reconcile). Nothing real runs: subprocess is faked."""
import sys, time, types, importlib
root = sys.argv[1]; sys.path.insert(0, root)
import engine.go as G
T = [0.0]
real_time, real_sleep = time.time, time.sleep
time.time = lambda: T[0]
time.sleep = lambda s: T.__setitem__(0, T[0] + s)
G.subprocess = types.SimpleNamespace(Popen=lambda *a, **k: None, run=lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=""))
def measure(fn):
    t0 = T[0]; r = fn(); return round(T[0] - t0, 1), r
out = {}
# server start
start_at = [0.0]
def popen(*a, **k): start_at[0] = T[0]
G.subprocess.Popen = popen
G.server_up = lambda: T[0] - start_at[0] >= 3.2
out["server start (ready at 3.2 s)"] = measure(lambda: G.start_server())[0]
# server stop
stop_at = [0.0]
G.subprocess.run = lambda *a, **k: (stop_at.__setitem__(0, T[0]), types.SimpleNamespace(returncode=0))[1]
G.server_up = lambda: T[0] - stop_at[0] < 1.3
out["server stop (down at 1.3 s)"] = measure(lambda: G.stop_server())[0]
# NinjaTrader log-in
t_nt = [None]
def conn():
    if t_nt[0] is None: t_nt[0] = T[0]
    return T[0] - t_nt[0] >= 7.0
import engine.autoresume as AR
AR.nt_connected = lambda cfg: conn()
G.nt_running = lambda: True
out["NinjaTrader log-in (connected at 7 s)"] = measure(lambda: G.ensure_ninjatrader(sleep=time.sleep))[0]
# chart fix
t_fd = [None]
def prob():
    if t_fd[0] is None: t_fd[0] = T[0]
    return None if T[0] - t_fd[0] >= 20.0 else "stale"
out["chart fix (bars back at 20 s)"] = measure(lambda: G.ensure_feed(problem=prob, sleep=time.sleep))[0]
# launch checklist
t_ck = [T[0]]
G._http = lambda path, body=None, timeout=5: {"items": [{"state": "good" if T[0] - t_ck[0] >= 12 else "wait", "label": "x", "detail": ""}]}
def ck():
    if hasattr(G, "checklist_launch"):
        return G.checklist_launch()
    lines, red = [], None                       # the old loop, copied from engine/go.py _step_arm (night-integrate)
    for _ in range(9):
        time.sleep(10)
        lines, red = G.checklist_lines()
        if red == 0:
            break
    return lines, red
t_ck[0] = T[0]
out["launch checklist (green at 12 s)"] = measure(ck)[0]
t_ck[0] = T[0] - 1000
out["launch checklist (already green)"] = measure(ck)[0]
for k, v in out.items():
    print(f"{k:42s} {v:6.1f} s")
print(f"{'TOTAL (the five waits of one START)':42s} {sum(v for k, v in out.items() if 'already' not in k):6.1f} s")
