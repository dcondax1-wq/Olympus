"""Exercise the Cities startup rescue without a browser or network."""
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "tools/web_public/cities/index.html"


def main():
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node is required for the Cities recovery test")
    html = HTML.read_text(encoding="utf-8")
    start = html.index("let recovering = false;")
    end = html.index("// Module import settles", start)
    source = html[start:end]
    script = r"""
const assert = require('node:assert/strict');
const source = process.argv[1];
const actualImport = "import('./atlas-entry.js?v=a5')";
assert.ok(source.includes(actualImport), 'recovery module import changed');
// Keep the actual page function and replace only its module boundary with a stub.
const executable = source.replace(actualImport, 'loadRecovery()');

async function exercise(state, rejectImport = false) {
  let calls = 0, kitReady = 0, recovered = 0, retries = [];
  const body = { dataset: { ready: state } };
  const loading = { style: {}, textContent: '', append: x => retries.push(x) };
  const document = {
    body,
    querySelector: selector => selector === '#loading' ? loading : null,
    createElement: tag => ({ tag, style: {}, textContent: '' }),
  };
  const window = { OLYMPUS: { ready: () => kitReady++ } };
  const loadRecovery = async () => {
    calls++;
    if (rejectImport) throw new Error('network unavailable');
    return { recoverAtlas: async () => { recovered++; body.dataset.ready = 'fallback'; } };
  };
  const recover = new Function('document', 'window', 'loadRecovery', 'location',
    executable + '; return recover;')(document, window, loadRecovery, { reload() {} });
  await recover();
  await recover();
  return { calls, recovered, kitReady, retries, loading, body, abandoned: window.__citiesImportAbandoned };
}

(async () => {
  const initial = await exercise('false');
  assert.equal(initial.calls, 1, 'not-ready page must try the independent atlas');
  assert.equal(initial.recovered, 1);
  assert.equal(initial.body.dataset.ready, 'fallback');
  assert.equal(initial.abandoned, true);
  for (const state of ['true', 'fallback']) {
    const ready = await exercise(state);
    assert.equal(ready.calls, 0, `already-ready ${state} must not recover again`);
  }
  const disconnected = await exercise('false', true);
  assert.equal(disconnected.calls, 1);
  assert.equal(disconnected.kitReady, 1, 'the kit veil must lift when recovery import fails');
  assert.equal(disconnected.retries.length, 1, 'offer a retry when city files cannot load');
  assert.equal(disconnected.retries[0].textContent, 'Reload Cities');
  console.log('Cities startup recovery: false / true / fallback / offline passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run([node, "-e", script, source], capture_output=True, text=True)
    print(result.stdout, end="")
    if result.returncode:
        raise AssertionError(result.stderr)


if __name__ == "__main__":
    main()
