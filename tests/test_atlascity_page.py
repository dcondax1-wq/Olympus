"""ATLAS Strategy City stays read-only and presents the three routed setups separately from paper outposts."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tools" / "web_public" / "atlascity"

def test_files_and_safe_source():
    html = (PAGE / "index.html").read_text(encoding="utf-8")
    js = (PAGE / "city.js").read_text(encoding="utf-8")
    css = (PAGE / "city.css").read_text(encoding="utf-8")
    assert 'ATLAS Strategy City' in html
    assert all(f'data-key="{key}"' in html for key in ("ema_lon_vix", "macd_sweep", "sr_nyreclaim"))
    assert 'Research district · never routed here' in html and 'id="outposts"' in html
    assert 'PAPER ONLY' in js
    assert "s.route===false" in js
    assert "'../home.json?atlas_city='" in js
    assert not re.search(r"WebSocket|sendBeacon|XMLHttpRequest|/api/|fetch\([^)]*POST|NINJATRADER_LIVE", js, re.I)
    assert "prefers-reduced-motion" in css and "data-lite=true" in css
    assert "min-height:44px" in css
    assert 'class="capital-core hq"' in html and "ATLAS HQ" in html
    assert "row<14" in js and "col<14" in js
    assert "form-3" in css and "capital-tower" in css
    subprocess.run(["node", "--check", str(PAGE / "city.js")], check=True)

def test_source_freshness_regression():
    subprocess.run(["node", str(ROOT / "tests" / "atlascity_freshness.mjs")], check=True)


if __name__ == "__main__":
    test_files_and_safe_source()
    test_source_freshness_regression()
    print("ATLAS Strategy City: read-only shell and syntax PASS")

