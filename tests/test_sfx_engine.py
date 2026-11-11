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
  m.s.district('research'); out.musicDistrict = m.s.musicState().playing; out.musicBad = m.s.district('jazz');
  const st0 = m.log.starts; await wait(1500); out.musicNotes = m.log.starts - st0;
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
        self.assertFalse(re.search(r"fetch\(|XMLHttpRequest|\.mp3|\.ogg|\.wav|https?:", code))   # all synthesised: no files, no network


if __name__ == "__main__":
    unittest.main()
