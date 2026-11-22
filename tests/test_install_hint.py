"""gate/install-hint.js: the 'hide the Safari bars' card shows only in an iPhone Safari tab, once, and never in the installed app / desktop."""
import os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "tools", "web_public", "gate", "install-hint.js")
IOS = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
DESK = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
fails = []
def check(name, ok, info=""):
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else "  -> " + str(info)))
    if not ok: fails.append(name)
def main():
    from playwright.sync_api import sync_playwright
    d = tempfile.mkdtemp(); page = os.path.join(d, "p.html")
    open(page, "w").write('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><body><h1>x</h1><script src="file://%s"></script></body>' % JS)
    url = "file://" + page
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        def run(ua, standalone=False, pre=None, w=390, h=844):
            ctx = b.new_context(user_agent=ua, viewport={"width": w, "height": h}, has_touch=True)
            p = ctx.new_page(); errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            if standalone: p.add_init_script("Object.defineProperty(navigator,'standalone',{value:true})")
            p.goto(url); p.wait_for_timeout(200)
            r = p.evaluate("() => { const c = document.getElementById('installHint'); if (!c) return null; const r = c.getBoundingClientRect(); const b = c.querySelector('button').getBoundingClientRect(); return {top: r.top, left: r.left, right: window.innerWidth - r.right, bh: b.height, text: c.innerText}; }")
            return ctx, p, r, errs
        ctx, p, r, errs = run(IOS)
        check("iPhone Safari tab: the card shows, inside the screen, with a 44 px button", r and r["top"] >= 0 and r["left"] >= 8 and r["right"] >= 8 and r["bh"] >= 44, r)
        check("it says how: Share, Add to Home Screen", r and "Share" in r["text"] and "Add to Home Screen" in r["text"], r)
        check("no page errors", not errs, errs)
        p.click("#installHint button"); p.wait_for_timeout(100)
        gone = p.evaluate("() => !document.getElementById('installHint')")
        saved = p.evaluate("() => localStorage.getItem('olympus.installhint.v1')")
        check("'Got it' removes the card and remembers it", gone and saved == "1", (gone, saved))
        p.reload(); p.wait_for_timeout(200)
        check("after a reload it stays hidden", p.evaluate("() => !document.getElementById('installHint')"))
        ctx.close()
        ctx, p, r, errs = run(IOS, standalone=True)
        check("installed app (standalone): nothing shows", r is None, r); ctx.close()
        ctx, p, r, errs = run(DESK, w=1280, h=800)
        check("desktop: nothing shows", r is None, r); ctx.close()
        b.close()
    print("install hint: %s" % ("ALL PASS" if not fails else "%d FAILED" % len(fails)))
    return 1 if fails else 0
if __name__ == "__main__":
    sys.exit(main())
