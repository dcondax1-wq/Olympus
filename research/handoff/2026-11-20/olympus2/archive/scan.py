"""Archive-team scan (2026-11-20): open each owned app at 390x844, our code from tools/web_public, missing data files pulled
from the live site (https://dcondax1-wq.github.io/, cached), so we see what the phone shows. Prints JSON lines.
  python research/handoff/2026-11-20/olympus2/archive/scan.py [ids...] [--out FILE] [--shots DIR]"""
import http.server, json, os, re, sys, threading, urllib.request, hashlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 5, "tools", "web_public"))
CACHE = os.path.join(os.environ.get("TMPDIR", "/tmp"), "olyscan_cache")
LIVE = "https://dcondax1-wq.github.io/"
os.makedirs(CACHE, exist_ok=True)
MINE = ("agency apollo arbiter archive arena ares argo argus athena atlascity bridge chronos colosseum delphi epilogue ergasterion forum "
        "gallery harmonia hephaestus herald hermes hestia inbox kairos kratos labyrinth lyceum mind mint mintcity moirai nemesis nike "
        "observatory odeon oracle pantheon pc pheme pinakes plutus polis prometheus pythia stoa symposium tree tyche why").split()

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(s, *a): pass
    def do_GET(s):
        path = s.path.split("?")[0].lstrip("/")
        local = os.path.join(ROOT, path)
        if os.path.exists(local) or not path.endswith(".json"):
            return super().do_GET()
        key = os.path.join(CACHE, hashlib.md5(path.encode()).hexdigest())
        if not os.path.exists(key):
            try:
                with urllib.request.urlopen(LIVE + path, timeout=20) as r: body = r.read(); code = 200
            except Exception: body = b""; code = 404
            open(key, "wb").write(json.dumps({"c": code}).encode() + b"\n" + body)
        raw = open(key, "rb").read(); head, body = raw.split(b"\n", 1); code = json.loads(head)["c"]
        s.send_response(code); s.send_header("Content-Type", "application/json"); s.send_header("Content-Length", str(len(body))); s.end_headers()
        s.wfile.write(body)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    shots = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
    args = [a for a in args if a not in (out, shots)]
    ids = args or MINE
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium") if os.path.exists("/opt/pw-browsers/chromium") else p.chromium.launch()
        for i in ids:
            ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
            pg = ctx.new_page(); errs, cons, bad, size, big = [], [], [], [0], []
            pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
            pg.on("console", lambda m: m.type == "error" and cons.append(m.text[:160]))
            def resp(r):
                if r.status >= 400: bad.append(f"{r.status}:{r.url.split(str(port) + '/')[-1][:70]}")
                try: n = int(r.headers.get("content-length") or 0) or len(r.body()); size[0] += n; big.append((n, r.url.split(str(port) + '/')[-1][:60]))
                except Exception: pass
            pg.on("response", resp)
            try: pg.goto(f"http://127.0.0.1:{port}/{i}/", wait_until="load", timeout=20000)
            except Exception as e: errs.append("goto " + str(e)[:80])
            pg.wait_for_timeout(2500)
            try:
                info = pg.evaluate("""() => ({sw: document.documentElement.scrollWidth, iw: innerWidth, title: document.title,
                    text: (document.body ? document.body.innerText : '').replace(/\\s+/g,' ').slice(0, 1500),
                    banner: !!document.querySelector('[data-archived]')})""")
            except Exception as e: info = {"sw": 0, "iw": 390, "title": "", "text": "eval " + str(e)[:60], "banner": False}
            t = info["text"]
            row = {"id": i, "kb": round(size[0] / 1024), "errors": errs[:3], "console": cons[:3], "bad": sorted(set(bad))[:6],
                   "sideways": max(0, info["sw"] - info["iw"]), "top": [f"{k // 1024}K {u}" for k, u in sorted(big, reverse=True)[:4]], "title": info["title"], "banner": info["banner"],
                   "demo": bool(re.search(r"\b(demo|sample|example|fixture|made[- ]up)\b", t, re.I)),
                   "dates": sorted(set(re.findall(r"\b(?:20\d\d-\d\d-\d\d|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2})\b", t)))[:8],
                   "text": t[:400]}
            if shots: os.makedirs(shots, exist_ok=True); pg.screenshot(path=os.path.join(shots, i + ".png"))
            rows.append(row); print(json.dumps(row), flush=True)
            ctx.close()
        b.close()
    if out: json.dump(rows, open(out, "w"), indent=1)
main()
