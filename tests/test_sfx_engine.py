"""OLYMPUS sound engine (olympus/sfx.js, 2026-11-11, docs/SOUND_API.md): runs sfx.js in node against a counting fake WebAudio.

Checks: every name and alias exists and plays; nothing (not even an AudioContext) before the first tap; every node a sound makes is
disconnected when it ends; voices are capped per category; mute silences everything at once; at() places a sound in listener space
(three.js convention) and skips sounds out of earshot; the shared reverb switches room with the bed; category volume / Quiet / duck
are stored or counted; music is off by default and follows its district; the 24 beds build with no error; the kit's OLYMPUS.sound
gets the new hooks; sound('tap') plays a cue and never flips the owner's switch.
Run: python -m unittest tests.test_sfx_engine  (about 6 s: it waits for real sounds to end)
"""
import json, pathlib, shutil, subprocess, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
JS = ROOT / "tools/web_public/olympus/sfx.js"

HARNESS = r"""
const mod = require(process.argv[1]);
function mk(opts) {
  opts = opts || {};
  const log = { created: 0, starts: 0, nodes: 0, live: new Set(), conv: 0, panners: [], resumed: 0 }, store = {};
  if (opts.saved) store['olympus.sfx'] = JSON.stringify(opts.saved);
  const param = (v) => ({ value: v || 0, setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {}, setTargetAtTime() {}, cancelScheduledValues() {} });
  function node(kind) {
    const n = { kind, outs: 0, connect(d) { if (!this.outs) log.live.add(this); this.outs++; return d; },
      disconnect() { this.outs = 0; log.live.delete(this); }, start() { log.starts++; }, stop() {},
      gain: param(1), frequency: param(), detune: param(), Q: param(), playbackRate: param(1), pan: param(), type: '' };
    log.nodes++; return n;
  }
  class AC {
    constructor() { log.created++; this.state = 'suspended'; this.t0 = Date.now(); this.sampleRate = 8000; this.destination = { kind: 'dest' }; this.listener = {}; }
    get currentTime() { return (Date.now() - this.t0) / 1000; }
    resume() { log.resumed++; this.state = 'running'; } suspend() { this.state = 'suspended'; }
    createGain() { return node('gain'); } createOscillator() { return node('osc'); } createBiquadFilter() { return node('filter'); }
    createDynamicsCompressor() { const n = node('comp'); n.threshold = param(); n.knee = param(); n.ratio = param(); n.attack = param(); n.release = param(); return n; }
    createBufferSource() { return node('src'); } createStereoPanner() { return node('stereo'); }
    createConvolver() { log.conv++; return node('conv'); }
    createPanner() { const n = node('panner'); n.positionX = param(); n.positionY = param(); n.positionZ = param(); log.panners.push(n); return n; }
    createBuffer(c, n) { const ch = []; for (let i = 0; i < c; i++) ch.push(new Float32Array(n)); return { getChannelData: (i) => ch[i] }; }
  }
  if (opts.noPanner) delete AC.prototype.createPanner;
  const h = {}, doc = { hidden: false, addEventListener: (e, f) => { h['doc_' + e] = f; } };
  const env = { AudioContext: AC, localStorage: { getItem: k => store[k] || null, setItem: (k, v) => { store[k] = v; } },
    matchMedia: () => ({ matches: false }), addEventListener: (e, f) => { (h[e] = h[e] || []).push(f); }, removeEventListener() {},
    navigator: {}, document: doc, OLYMPUS: opts.kit ? { sound: function () { return 'kit'; }, lite: () => false, saver: () => false } : undefined };
  const s = mod.create(env);
  const tap = () => h.pointerdown.forEach(f => f());
  return { s, log, store, h, doc, env, tap };
}
const wait = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const out = {};
  // 1. before the first tap: nothing
  let t = mk({ kit: true });
  out.pre = { play: t.s.names.map(n => t.s.play(n)).some(Boolean), at: t.s.at('step-stone', { x: 1, y: 0, z: -2 }), bus: t.s.bus('ui'), ctx: t.s.context(), created: t.log.created, nodes: t.log.nodes };
  out.hooks = ['at', 'world', 'cue', 'music', 'duck', 'volume', 'listener', 'bus'].every(k => typeof t.env.OLYMPUS.sound[k] === 'function') && t.env.OLYMPUS.sound() === 'kit';
  t.tap();
  out.unlock = { created: t.log.created, resumed: t.log.resumed > 0, silentSample: t.log.starts >= 1, conv: t.log.conv, reverb: t.s.state().reverb, bus: !!t.s.bus('voices'), ctx: !!t.s.context() };
  // 2. every name and alias plays
  out.names = { all: t.s.names.slice(), cues: t.s.cues, worlds: t.s.worlds, legacy: t.s.legacy };
  out.playAll = t.s.names.filter(n => n !== 'pad').filter(n => !t.s.play(n));
  await wait(40);
  out.aliases = ['notification', 'money-in', 'level-up', 'toggle-off', 'swipe-back', 'footstep', 'anvil', 'clink'].filter(n => !t.s.play(n));
  await wait(40); out.surface = [t.s.at('step', { x: 1, y: 0, z: -1 }, null, { surface: 'sand' }), t.s.play('footstep', { surface: 'wood' })];
  out.bad = t.s.play('nope'); out.badAt = t.s.at('nope', { x: 0, y: 0, z: 0 });
  out.capped = t.s.state().voices;
  let ui = 0; for (const v of [t.s.state()]) ui = v.voices;
  out.errors1 = t.s.state().errors;
  // 3. everything is released when the sounds end
  await wait(4300);
  out.after = { voices: t.s.state().voices, nodes: t.s.state().nodes, released: t.s.state().released, errors: t.s.state().errors };
  // 4. cap: ten different UI cues at once stay within six UI voices
  for (const n of t.s.cues) t.s.play(n);
  out.uiVoices = t.s.state().voices;
  // 5. mute: everything stops at once and stays silent
  t.s.music(true); t.s.ambient('agora');
  out.beforeMute = { bed: t.s.ambientState().playing, music: t.s.musicState().playing };
  t.s.mute(true);
  out.muted = { play: t.s.play('success'), at: t.s.at('coin', { x: 0, y: 0, z: -1 }), voices: t.s.state().voices, bed: t.s.ambientState().playing, music: t.s.musicState().playing };
  t.s.mute(false); t.s.music(false); t.s.ambientStop();
  // 6. positional: listener turned left (yaw +90 deg) at the origin; a source at world -x is straight ahead (-z)
  const p0 = t.log.panners.length;
  out.atOk = t.s.at('step-stone', { x: -5, y: 0, z: 0 }, { x: 0, y: 0, z: 0, yaw: Math.PI / 2 });
  const pn = t.log.panners[p0];
  out.pannerPos = pn ? [Math.round(pn.positionX.value * 100) / 100, Math.round(pn.positionY.value * 100) / 100, Math.round(pn.positionZ.value * 100) / 100] : null;
  out.camera = t.s.at('hammer', { x: 3, y: 1, z: 0 }, { position: { x: 3, y: 1, z: 4 }, rotation: { y: 0 } }) && (() => { const q = t.log.panners[t.log.panners.length - 1]; return [q.positionX.value, q.positionZ.value]; })();
  const pBefore = t.log.panners.length;
  out.far = t.s.at('cheer', { x: 500, y: 0, z: 0 }, { x: 0, y: 0, z: 0 }); out.farNoNode = t.log.panners.length === pBefore;
  t.s.listener({ x: 10, y: 0, z: 10 }); out.defListener = t.s.at('door', { x: 10, y: 0, z: 7 }) && t.log.panners[t.log.panners.length - 1].positionZ.value;
  let np = mk({ noPanner: true }); np.tap(); out.noPanner = np.s.at('coin', { x: 2, y: 0, z: -2 }) && np.s.state().errors === 0;
  // 7. the shared reverb follows the bed's room
  t.s.ambient('smithy'); out.roomSmithy = t.s.state().room; t.s.ambient('scroll'); out.roomScroll = t.s.state().room; t.s.ambient('crowd'); out.roomCrowd = t.s.state().room;
  out.roomSet = t.s.room('tent'); out.roomBad = t.s.room('cave');
  t.s.ambientStop();
  // 8. every bed (old names and new) builds; they run a while without errors; the old names map to the new beds
  const beds = {}; for (const n of t.s.ambients) { t.s.ambient(n); beds[n] = [t.s.ambientState().playing === n, t.s.ambientState().bed]; }
  t.s.ambient('chimes'); await wait(1200); out.bedsErr = t.s.state().errors; t.s.ambientStop();
  out.beds = beds; out.bedBuilders = t.s.beds;
  // 9. categories, Quiet, duck
  out.vol = [t.s.volume('ambience', 0.3), t.s.volume('ambience'), JSON.parse(t.store['olympus.sfx']).c, t.s.volume('nope', 1)];
  out.quiet = [t.s.quiet(true), JSON.parse(t.store['olympus.sfx']).q]; t.s.music(true); out.quietMusic = t.s.musicState().playing; t.s.quiet(false); out.quietBack = t.s.musicState().playing; t.s.music(false);
  out.duck = [t.s.duck(true), t.s.duck(true), t.s.duck(false), t.s.duck(false), t.s.duck()];
  t.env.OLYMPUS_QUIET = () => true; t.s.ambient('sea'); await wait(800); out.autoDuck = t.s.duck(); t.env.OLYMPUS_QUIET = () => false; await wait(800); out.autoDuckOff = t.s.duck(); t.s.ambientStop();
  // 10. music: off by default; on = the district (or the bed's); its notes are scheduled
  let m = mk({}); m.tap();
  out.musicDefault = m.s.musicState();
  m.s.ambient('coins'); m.s.music(true); out.musicBed = m.s.musicState().playing;
  const st0 = m.log.starts;                                  // counted from the district switch: its first note is scheduled at once (a phrase never starts on a rest)
  m.s.district('research'); out.musicDistrict = m.s.musicState().playing; out.musicBad = m.s.district('jazz');
  await wait(1500); out.musicNotes = m.log.starts - st0;
  out.musicStored = JSON.parse(m.store['olympus.sfx']).mu;
  m.s.music(false); out.musicOff = m.s.musicState().playing; m.s.ambientStop();
  // 11. sound('tap') plays a cue and leaves the switch alone; sound(false) silences world sounds and cues
  let w = mk({}); w.tap(); out.soundStr = [w.s.sound('tap'), 's' in JSON.parse(w.store['olympus.sfx'] || '{}')];
  w.s.sound(false); out.soundOff = [w.s.play('open'), w.s.at('coin', { x: 0, y: 0, z: -1 }), w.s.play('tap')];
  // 12. hidden tab: the bed stops; back: it returns
  let hd = mk({}); hd.tap(); hd.s.ambient('night'); hd.doc.hidden = true; hd.h.doc_visibilitychange(); out.hidden = hd.s.ambientState().playing; hd.doc.hidden = false; hd.h.doc_visibilitychange(); out.visible = hd.s.ambientState().playing;
  // 13. a stored owner's profile is read back (category volumes, quiet, music)
  let sv = mk({ saved: { v: 0.5, m: false, c: { music: 0.2 }, q: true, mu: true } }); out.saved = [sv.s.volume('music'), sv.s.quiet(), sv.s.musicState().on, sv.s.state().volume];
  // 14. onUnlock waits for the first tap
  let ou = mk({}); let called = 0; ou.s.onUnlock(() => called++); out.onUnlockPre = called; ou.tap(); out.onUnlockPost = called;
  console.log(JSON.stringify(out));
  setTimeout(() => process.exit(0), 20);
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(shutil.which("node"), "node missing")
class SfxEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", "-e", HARNESS, str(JS)], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        cls.o = json.loads(r.stdout.strip().splitlines()[-1])

    def test_nothing_before_the_first_tap(self):
        p = self.o["pre"]
        self.assertEqual((p["play"], p["at"], p["bus"], p["ctx"], p["created"], p["nodes"]), (False, False, None, None, 0, 0))
        u = self.o["unlock"]
        self.assertEqual(u["created"], 1)                      # one AudioContext, made by the tap
        self.assertTrue(u["resumed"] and u["silentSample"])    # iOS: resumed inside the gesture, one silent sample played
        self.assertTrue(u["reverb"] and u["conv"] >= 1)        # the shared reverb exists
        self.assertTrue(u["bus"] and u["ctx"])

    def test_names_old_and_new(self):
        n = self.o["names"]
        for x in ("tick", "tap", "portal", "thunder", "rankup", "pad"):
            self.assertIn(x, n["legacy"])
        for x in ("open", "close", "tap", "success", "warning", "error", "swipe", "toggle", "notify", "money", "levelup"):
            self.assertIn(x, n["all"])
        for x in ("step-stone", "step-sand", "step-wood", "hammer", "quill", "scroll", "coin", "crate", "cheer", "groan", "door", "fire"):
            self.assertIn(x, n["worlds"])
        self.assertEqual(self.o["playAll"], [])                # every name sounds after the tap
        self.assertEqual(self.o["aliases"], [])                # notification, money-in, level-up, toggle-off ... resolve
        self.assertEqual(self.o["surface"], [True, True])      # step + {surface}
        self.assertFalse(self.o["bad"])
        self.assertFalse(self.o["badAt"])
        self.assertEqual(self.o["errors1"], 0)

    def test_nodes_released_and_voices_capped(self):
        a = self.o["after"]
        self.assertEqual((a["voices"], a["nodes"], a["errors"]), (0, 0, 0))   # every sound's nodes disconnected after it ends
        self.assertGreaterEqual(a["released"], 20)
        self.assertLessEqual(self.o["capped"], 6 + 6 + 1)       # ui 6 + world 6 at most, whatever was asked
        self.assertLessEqual(self.o["uiVoices"], 6)

    def test_mute_silences_everything(self):
        self.assertEqual(self.o["beforeMute"], {"bed": "agora", "music": "trading"})
        self.assertEqual(self.o["muted"], {"play": False, "at": False, "voices": 0, "bed": "", "music": ""})

    def test_positional(self):
        self.assertTrue(self.o["atOk"])
        self.assertEqual(self.o["pannerPos"], [0, 0, -5])      # turned left: world -x is straight ahead
        self.assertEqual(self.o["camera"], [0, -4])            # a three.js-style camera {position, rotation}
        self.assertFalse(self.o["far"])                         # out of earshot: skipped ...
        self.assertTrue(self.o["farNoNode"])                    # ... and nothing built
        self.assertEqual(self.o["defListener"], -3)            # listener(L) is the default
        self.assertTrue(self.o["noPanner"])                     # no PannerNode (old Safari): stereo + distance gain, no error

    def test_reverb_rooms_follow_the_bed(self):
        self.assertEqual((self.o["roomSmithy"], self.o["roomScroll"], self.o["roomCrowd"]), ("tent", "hall", "courtyard"))
        self.assertEqual((self.o["roomSet"], self.o["roomBad"]), ("tent", "tent"))

    def test_every_bed_builds(self):
        beds = self.o["beds"]
        self.assertEqual(len(beds), 24)
        self.assertTrue(all(v[0] for v in beds.values()), [k for k, v in beds.items() if not v[0]])
        for new in ("marble", "agora", "workshop", "desert", "harbour", "night", "library", "colosseum"):
            self.assertIn(new, beds)
        for old, new in {"forge": "workshop", "smithy": "workshop", "sea": "harbour", "scroll": "library", "crowd": "colosseum", "space": "night",
                         "chimes": "temple", "wind": "temple", "coins": "treasury", "city": "agora", "lab": "marble", "forest": "grove", "breeze": "desert"}.items():
            self.assertEqual(beds[old][1], new, old)
        self.assertEqual(self.o["bedsErr"], 0)

    def test_categories_quiet_duck(self):
        v = self.o["vol"]
        self.assertEqual((v[0], v[1], v[2]["ambience"], v[3]), (0.3, 0.3, 0.3, False))
        self.assertEqual(self.o["quiet"], [True, True])
        self.assertEqual((self.o["quietMusic"], self.o["quietBack"]), ("", "trading"))   # Quiet: no music
        self.assertEqual(self.o["duck"], [True, True, True, False, False])                # counted
        self.assertEqual((self.o["autoDuck"], self.o["autoDuckOff"]), (True, False))     # OLYMPUS_QUIET ducks the beds by itself

    def test_music(self):
        d = self.o["musicDefault"]
        self.assertEqual((d["on"], d["playing"]), (False, ""))                          # off by default
        self.assertEqual(set(d["districts"]), {"trading", "money", "life", "research"})
        self.assertEqual(self.o["musicBed"], "money")           # follows the bed (coins = the treasury)
        self.assertEqual(self.o["musicDistrict"], "research")
        self.assertFalse(self.o["musicBad"])
        self.assertGreater(self.o["musicNotes"], 0)             # notes scheduled
        self.assertTrue(self.o["musicStored"])
        self.assertEqual(self.o["musicOff"], "")

    def test_sound_switch_and_string(self):
        self.assertEqual(self.o["soundStr"], [True, False])     # sound('tap') played it, the switch untouched
        self.assertEqual(self.o["soundOff"], [False, False, True])   # Off: cues and world silent, the old tap follows mute only

    def test_hidden_tab_and_saved_profile(self):
        self.assertEqual((self.o["hidden"], self.o["visible"]), ("", "night"))
        self.assertEqual(self.o["saved"], [0.2, True, True, 0.5])
        self.assertEqual((self.o["onUnlockPre"], self.o["onUnlockPost"]), (0, 1))

    def test_kit_hooks(self):
        self.assertTrue(self.o["hooks"])                        # OLYMPUS.sound.at / world / cue / music ... and sound() still the kit's

    def test_static_es5_no_files(self):
        import re
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", JS.read_text(encoding="utf-8"), flags=re.S)
        self.assertFalse(re.search(r"=>|\blet\s|\bconst\s|`|\bclass\s|\basync\b", code))     # a classic ES5 script (old iPhones)
        # 2026-11-11 the recorded layer: the only network call is env.fetch(url) of our own assets/audio/ files (same origin, relative to sfx.js);
        # no other host, no CDN, no XMLHttpRequest, no .mp3 / .wav
        self.assertFalse(re.search(r"XMLHttpRequest|\.mp3\b|\.wav\b|https?:|cdn", code))
        self.assertEqual(re.findall(r"\bfetch\(", code), ["fetch("])
        self.assertIn("env.fetch(url)", code)
        self.assertIn("url = smpBase() + stem + '.' + f", code)


# ------------------------------------------------------------------------------------------------ the recorded layer (2026-11-11, CC0 recordings)
AUDIO = ROOT / "tools/web_public/assets/audio"
LIC = ROOT / "docs/ASSETS_LICENSES.md"
SAMPLE_HARNESS = r"""
const mod = require(process.argv[1]), fs = require('fs'), path = require('path'), dir = process.argv[2];
function mk(opts) {
  opts = opts || {};
  const log = { nodes: 0, live: new Set(), starts: [], rates: [], fetched: [], decoded: 0 };
  const param = (v) => ({ value: v || 0, setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {}, setTargetAtTime() {}, cancelScheduledValues() {}, setValueCurveAtTime() {} });
  function node(kind) {
    const n = { kind, outs: 0, connect(d) { if (!this.outs) log.live.add(this); this.outs++; return d; }, disconnect() { this.outs = 0; log.live.delete(this); },
      start(t, off, dur) { if (kind === 'src' && this.buffer && this.buffer.fake) log.starts.push([off, dur]); }, stop() {},
      gain: param(1), frequency: param(), detune: param(), Q: param(), playbackRate: param(1), pan: param(), type: '' };
    if (kind === 'src') Object.defineProperty(n, 'rate', { get() { return n.playbackRate.value; } });
    log.nodes++; return n;
  }
  class AC {
    constructor() { this.state = 'running'; this.t0 = Date.now(); this.sampleRate = 8000; this.destination = { kind: 'dest' }; }
    get currentTime() { return (Date.now() - this.t0) / 1000; }
    resume() {} suspend() {}
    createGain() { return node('gain'); } createOscillator() { return node('osc'); } createBiquadFilter() { return node('filter'); }
    createDynamicsCompressor() { const n = node('comp'); n.threshold = param(); n.knee = param(); n.ratio = param(); n.attack = param(); n.release = param(); return n; }
    createBufferSource() { const s = node('src'); return s; } createStereoPanner() { return node('stereo'); } createConvolver() { return node('conv'); }
    createPanner() { const n = node('panner'); n.positionX = param(); n.positionY = param(); n.positionZ = param(); return n; }
    createBuffer(c, n) { const ch = []; for (let i = 0; i < c; i++) ch.push(new Float32Array(n)); return { getChannelData: (i) => ch[i], duration: n / 8000 }; }
    decodeAudioData(ab, ok, no) {                               // a real file's bytes in, a fake buffer out (its length from the manifest)
      log.decoded++; const b = { fake: true, duration: 60, numberOfChannels: 1, length: 60 * 8000, bytes: ab.byteLength };
      if (opts.badDecode) { const e = new Error('EncodingError'); if (no) no(e); return Promise.reject(e); }
      if (ok) ok(b); return Promise.resolve(b);
    }
  }
  const h = {};
  const env = { AudioContext: AC, localStorage: { getItem: () => null, setItem() {} }, matchMedia: () => ({ matches: false }),
    addEventListener: (e, f) => { (h[e] = h[e] || []).push(f); }, navigator: {}, document: { hidden: false, addEventListener() {}, createElement: () => ({ canPlayType: (t) => opts.noOgg && /ogg/.test(t) ? '' : 'probably' }) },
    audioBase: opts.base || 'assets/audio/',
    fetch: (url) => { log.fetched.push(url); if (opts.offline) return Promise.reject(new Error('offline'));
      const f = path.join(dir, path.basename(url)); if (!fs.existsSync(f)) return Promise.resolve({ ok: false, status: 404 });
      const b = fs.readFileSync(f); return Promise.resolve({ ok: true, status: 200, arrayBuffer: () => Promise.resolve(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)) }); } };
  const s = mod.create(env);
  const tap = () => h.pointerdown.forEach(f => f());
  return { s, log, tap, env };
}
const wait = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const out = {};
  let t = mk({});
  out.preFetch = t.log.fetched.length;                          // nothing fetched before the first tap
  t.s.play('tap'); out.preFetch2 = t.log.fetched.length;
  t.tap(); await t.s.preload(['ui', 'steps', 'forge', 'harp']);
  out.fetched = t.log.fetched.slice(0, 4); out.state = t.s.samples();
  // round robin: 40 stone steps never play the same take twice in a row, pitch jitter varies
  const s0 = t.log.starts.length;
  for (let i = 0; i < 40; i++) { t.s.at('step', { x: i, y: 0, z: -2 }, { x: 0, y: 0, z: 0 }, { surface: 'stone' }); await wait(32); }
  const st = t.log.starts.slice(s0).map(x => x[0]);
  out.steps = st.length; out.repeats = st.filter((x, i) => i && x === st[i - 1]).length; out.takes = new Set(st).size;
  // a cue layers the real tap with the harp; the harp retunes
  const s1 = t.log.starts.length; t.s.play('success'); out.successRec = t.log.starts.length - s1;
  const s2 = t.log.starts.length; t.s.play('success', { synth: true }); out.successSynth = t.log.starts.length - s2;
  const s3 = t.log.starts.length; t.s.play('hammer'); out.hammerRec = t.log.starts.length - s3;
  out.played = t.s.samples().played; out.errors = t.s.state().errors;
  await wait(3200); out.after = { voices: t.s.state().voices, nodes: t.s.state().nodes };
  // a bed with its loops: the looper starts and the bed's files are fetched
  t.s.ambience(true); t.s.ambient('harbour'); await wait(300); out.bedFetched = t.log.fetched.filter(u => /loop-sea|nature/.test(u)).length; out.bedPlayed = t.s.samples().played > out.played;
  t.s.ambientStop();
  // samples(false): synth only (the lab's A/B)
  t.s.samples(false, false); const s4 = t.log.starts.length; t.s.play('success'); out.offRec = t.log.starts.length - s4; t.s.samples(true, false);
  // the format: Opus first where it plays; m4a where it does not (iPhone); a failing format falls back to the other
  let m = mk({ noOgg: true }); m.tap(); await m.s.preload(['ui']); out.m4a = [m.s.samples().fmt, m.log.fetched[0]];
  // offline / missing files: the synth plays, nothing throws
  let f = mk({ offline: true, base: 'offline/assets/audio/' });   // another page (the bytes cache is per page)
   f.tap(); await f.s.preload(['ui', 'steps']); out.offline = { failed: f.s.samples().failed, play: f.s.play('success'), at: f.s.at('step', { x: 1, y: 0, z: -1 }), errors: f.s.state().errors, fetched: f.log.fetched.length };
  let d = mk({ badDecode: true, base: 'bad/assets/audio/' }); d.tap(); await d.s.preload(['ui']); out.badDecode = { failed: d.s.samples().failed, tried: d.log.fetched, play: d.s.play('tap'), errors: d.s.state().errors };
  // murmur + presence
  t.s.duck(false);
  const tl = { keys: [{ t: 0, v: 'A', a: 0.9 }, { t: 120, v: 'S', a: 0.3 }, { t: 220, v: 'O', a: 0.7 }, { t: 400, v: 'rest', a: 0 }] };
  const mh = t.s.murmur({ timbre: { hz: 180, formant: 1, breath: 0.06, wave: 'sine' }, gender: 'f' }, tl, {});
  out.murmur = !!(mh && mh.stop); if (mh) mh.stop();
  out.presenceOf = [t.s.presenceOf({ accessory: 'key' }).jingle, t.s.presenceOf({ kind: 'scanner' }).jingle, t.s.presenceOf({ id: 'builder:x' }).jingle, t.s.presenceOf({}).jingle];
  const w = t.s.walker({ kind: 'keeper', surface: 'wood' }); let ws = 0; for (let i = 0; i < 6; i++) { if (w.step({ x: i * 2, y: 0, z: -3 }, { x: 0, y: 0, z: 0 })) ws++; await wait(35); }
  out.walker = ws; out.presence = t.s.presence({ accessory: 'pouch' }, { x: 1, y: 0, z: -1 }, { x: 0, y: 0, z: 0 });
  out.jingles = t.s.jingles.map(k => t.s.play('jingle', { kind: k }));
  let pre = mk({}); out.murmurPre = pre.s.murmur({ timbre: {} }, tl, {});
  console.log(JSON.stringify(out));
  setTimeout(() => process.exit(0), 20);
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(shutil.which("node"), "node missing")
class SampleLayerTest(unittest.TestCase):
    """the recorded layer in node: lazy fetch after the tap, round robin + jitter, layering, the format choice, fallback to the synth, murmur, presence"""

    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", "-e", SAMPLE_HARNESS, str(JS), str(AUDIO)], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        cls.o = json.loads(r.stdout.strip().splitlines()[-1])

    def test_lazy_after_the_tap(self):
        self.assertEqual((self.o["preFetch"], self.o["preFetch2"]), (0, 0))                     # no download before the first tap
        self.assertTrue(all(u.startswith("assets/audio/") and u.endswith(".ogg") for u in self.o["fetched"]), self.o["fetched"])
        st = self.o["state"]
        self.assertEqual(st["fmt"], "ogg")
        self.assertTrue({"ui", "steps", "forge", "harp"} <= set(st["loaded"]), st)
        self.assertEqual(st["failed"], [])

    def test_round_robin_and_jitter(self):
        self.assertGreaterEqual(self.o["steps"], 30)
        self.assertEqual(self.o["repeats"], 0)                  # never the same take twice in a row
        self.assertGreaterEqual(self.o["takes"], 5)             # the stone bank has 7 takes

    def test_layered_with_the_synth_and_released(self):
        self.assertGreaterEqual(self.o["successRec"], 5)        # 4 harp notes + the cymbal: recordings
        self.assertEqual(self.o["successSynth"], 0)             # {synth: true}: no recording at all
        self.assertEqual(self.o["hammerRec"], 1)                # the real anvil (its ring tail is synthesised)
        self.assertEqual(self.o["errors"], 0)
        self.assertEqual(self.o["after"], {"voices": 0, "nodes": 0})
        self.assertGreaterEqual(self.o["bedFetched"], 2)        # the harbour fetches its sea loop and its gulls
        self.assertTrue(self.o["bedPlayed"])                    # the looper started
        self.assertEqual(self.o["offRec"], 0)                   # samples(false): synth only

    def test_format_and_fallback(self):
        self.assertEqual(self.o["m4a"][0], "m4a")               # no Opus here (older iPhone): AAC
        self.assertTrue(self.o["m4a"][1].endswith("ui.m4a"))
        off = self.o["offline"]
        # QA round 6 (real-phone pass): the format is found out on the first file while the others wait; when neither format of it works the
        # recorded layer stops for the session (synth only), so offline costs 2 requests, not 2 per file
        self.assertEqual(sorted(off["failed"]), ["ui"])         # the tap asks for the UI taps and the harp; the test asked for steps: never fetched
        self.assertTrue(off["play"] and off["at"])              # the synth plays
        self.assertEqual(off["errors"], 0)
        self.assertEqual(off["fetched"], 2)                     # the first file: the best format, then the other, then give up for the session
        bd = self.o["badDecode"]
        self.assertEqual((sorted(bd["failed"]), len(bd["tried"]), bd["play"], bd["errors"]), (["ui"], 2, True, 0))   # a file that will not decode: both formats tried, then the synth

    def test_murmur_and_presence(self):
        self.assertTrue(self.o["murmur"])
        self.assertIsNone(self.o["murmurPre"])                  # before the tap: nothing
        self.assertEqual(self.o["presenceOf"], ["keys", "pouch", "metal", "beads"])
        self.assertGreaterEqual(self.o["walker"], 5)
        self.assertTrue(self.o["presence"])
        self.assertEqual(self.o["jingles"], [True] * 7)


class AssetFilesTest(unittest.TestCase):
    """the committed files: both formats, sizes within the budget, measured levels and seams, licence rows, the manifest embedded in sfx.js"""

    @classmethod
    def setUpClass(cls):
        cls.m = json.loads((AUDIO / "manifest.json").read_text(encoding="utf-8"))

    def test_every_file_both_formats_and_budget(self):
        tot = 0
        for stem in self.m["files"]:
            for ext in ("ogg", "m4a"):
                p = AUDIO / (stem + "." + ext)
                self.assertTrue(p.exists(), p)
                tot += p.stat().st_size
        self.assertLessEqual(tot, 8 * 1024 * 1024)              # the whole recorded layer, both formats
        import re
        files, js = self.m["files"], JS.read_text(encoding="utf-8")
        bf = re.search(r"var BED_FILES = (\{.*?\});", js, re.S).group(1)
        places = re.findall(r"(\w+): \[([^\]]*)\]", bf)
        self.assertEqual(len(places), 11)
        for place, stems in places:
            used = {x.strip(" '") for x in stems.split(",")} | {"ui", "harp"}
            for ext in ("ogg", "m4a"):
                self.assertLess(sum(files[x]["kb"][ext] for x in used), 1024, (place, ext))   # a place's first load (one format) stays under 1 MB

    def test_measured_levels_and_seams(self):
        for r in self.m["measure"]:
            self.assertLessEqual(r["ogg_peak"], -2.9, r["file"])   # peaks <= -3 dBFS after decoding (codec overshoot included)
            self.assertLessEqual(r["m4a_peak"], -2.9, r["file"])
            if r["kind"] == "loop":
                self.assertTrue(-25 <= r["lufs"] <= -15.5, r)       # beds about -16 LUFS (crackly fire lower: its peaks rule)
                self.assertLess(r["seam_jump"], 1.0, r)             # the loop's seam step is smaller than the file's own 99.9th percentile step
                self.assertLess(r["m4a_seam_jump"], 1.5, r)
                self.assertLess(r["seam_step_db"], 3.0, r)          # no level jump at the seam
                self.assertLess(abs(r["m4a_pad_ms"]), 25, r)        # AAC's padding: < 25 ms (the engine loops the nominal length)
            self.assertGreater(r["centroid"], 60, r["file"])        # spectral sanity: not DC / rumble only
            self.assertLess(r["centroid"], 12000, r["file"])

    def test_licence_row_for_every_file(self):
        txt = LIC.read_text(encoding="utf-8")
        block = txt.split("<!-- AUDIO:BEGIN")[1].split("<!-- AUDIO:END -->")[0]
        rows = [l for l in block.splitlines() if l.startswith("| ") and "---" not in l and not l.startswith("| asset")]
        self.assertGreaterEqual(len(rows), 20)
        for l in rows:
            cells = [c.strip() for c in l.strip("|").split("|")]
            self.assertEqual(cells[3], "CC0", l)
            self.assertTrue(cells[1] and cells[2].startswith(("https://opengameart.org/content/", "https://github.com/sgossner/VCSL")), l)
        named = set()
        for l in rows:
            named |= {x.strip() for x in l.strip("|").split("|")[4].split(",")}
        self.assertEqual(named, set(self.m["files"]))            # every committed file is covered by a CC0 row

    def test_manifest_embedded_in_sfx_js(self):
        import re
        js = JS.read_text(encoding="utf-8")
        emb = json.loads(re.search(r"/\*AUDIO\*/(.*?)/\*/AUDIO\*/", js, re.S).group(1))
        self.assertEqual(emb["banks"], self.m["banks"])
        self.assertEqual(emb["loops"], self.m["loops"])
        self.assertEqual(set(emb["files"]), set(self.m["files"]))

    @unittest.skipUnless(shutil.which("ffprobe"), "ffprobe missing")
    def test_codecs(self):
        for stem, f in self.m["files"].items():
            for ext, codec in (("ogg", "opus"), ("m4a", "aac")):
                r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,channels", "-of", "json", str(AUDIO / (stem + "." + ext))], capture_output=True, text=True)
                s = json.loads(r.stdout)["streams"][0]
                self.assertEqual((s["codec_name"], s["channels"]), (codec, f["ch"]), (stem, ext))


if __name__ == "__main__":
    unittest.main()
