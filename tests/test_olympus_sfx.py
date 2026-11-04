"""OLYMPUS sfx: runs tools/web_public/olympus/sfx.js in node against a fake WebAudio."""
import json, pathlib, shutil, subprocess, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
JS = ROOT / "tools/web_public/olympus/sfx.js"

HARNESS = r"""
const mod = require(process.argv[1]);
function mk(opts){
  const log={starts:0,created:0,vib:[]}, store={};
  const param=()=>({value:0,setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){},setTargetAtTime(){},cancelScheduledValues(){}});
  const node=()=>({connect(){},start(){log.starts++},stop(){},gain:param(),frequency:param(),detune:param(),Q:param(),type:''});
  class AC{constructor(){log.created++;this.state='suspended';this.currentTime=0;this.sampleRate=8000;this.destination={};}
    resume(){this.state='running'} suspend(){this.state='suspended'}
    createGain(){return node()} createOscillator(){return node()} createBiquadFilter(){return node()}
    createDynamicsCompressor(){return node()} createBufferSource(){return node()}
    createBuffer(c,n){return {getChannelData(){return new Float32Array(n)}}}}
  const h={};
  const env={AudioContext:AC,OLYMPUS:opts.saver?{saver:()=>true}:undefined,localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>{store[k]=v}},
    matchMedia:()=>({matches:!!opts.reduced}),addEventListener:(e,f)=>{h[e]=f},removeEventListener(){},
    navigator:opts.vibrate===false?{}:{vibrate:p=>{log.vib.push(p);return true}}};
  return {s:mod.create(env),log,store,h};
}
const out={};
let t=mk({}); out.pre=t.s.names.map(n=>t.s.play(n)); out.preCtx=t.log.created; out.preStarts=t.log.starts;
t.h.pointerdown(); out.unlocked=t.s.state().unlocked;
out.post=t.s.names.map(n=>t.s.play(n)); out.postStarts=t.log.starts>0; out.vibN=t.log.vib.length;
out.bad=t.s.play('nope'); out.err=t.s.state().errors;
t.s.mute(true); const b=t.log.starts; out.mutedPlay=t.s.play('tap'); out.mutedNoSched=(t.log.starts===b);
out.stored=JSON.parse(t.store['olympus.sfx']); out.vol=t.s.setVolume(5); t.s.mute(false); out.after=t.s.play('tick');
let n=mk({vibrate:false}); n.h.pointerdown(); out.noVib=[n.s.play('tap'),n.s.play('thunder')]; out.noVibErr=n.s.state().errors;
let r=mk({reduced:true}); r.h.pointerdown(); r.s.play('tap'); r.s.play('pad'); out.redVib=r.log.vib.length; out.redPad=r.s.state().padOn;
let p=mk({}); p.h.pointerdown(); p.s.play('pad'); out.padOn=p.s.state().padOn; p.s.stop('pad'); out.padOff=p.s.state().padOn;
// ambience
let am=mk({}); out.ambPre=am.s.ambient('sea'); out.ambNoCtx=am.log.created; out.ambPlayingPre=am.s.ambientState().playing;   // wanted, but no gesture: nothing plays
am.h.pointerdown(); out.ambPlaying=am.s.ambientState().playing; out.ambStarts=am.log.starts>0;
out.ambBad=am.s.ambient('nope'); out.ambNames=am.s.ambients.length;
am.s.ambience(false); out.ambOff=am.s.ambientState().playing; out.ambStored=JSON.parse(am.store['olympus.sfx']).a;
am.s.ambience(true); out.ambBack=am.s.ambientState().playing;
am.s.mute(true); out.ambMuted=am.s.ambientState().playing; am.s.mute(false); out.ambUnmuted=am.s.ambientState().playing;
am.s.ambient('forge'); out.ambSwitch=am.s.ambientState().playing; am.s.ambientStop(); out.ambStopped=am.s.ambientState().playing;
const all=[]; for (const n of am.s.ambients) { am.s.ambient(n); all.push(am.s.ambientState().playing===n); } am.s.ambientStop(); out.ambAll=all.every(Boolean); out.ambErr=am.s.state().errors;
let sv2=mk({saver:true}); sv2.s.ambient('wind'); sv2.h.pointerdown();
out.saverAuto=sv2.s.ambientState().playing; out.saverFlag=sv2.s.ambientState().saver; sv2.s.ambience(true); out.saverOwnerOn=sv2.s.ambientState().playing;
console.log(JSON.stringify(out));
setTimeout(()=>process.exit(0),50);
"""


@unittest.skipUnless(shutil.which("node"), "node missing")
class SfxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", "-e", HARNESS, str(JS)], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        cls.o = json.loads(r.stdout.strip().splitlines()[-1])

    def test_nothing_before_gesture(self):
        self.assertEqual(self.o["pre"], [False] * 6)
        self.assertEqual((self.o["preCtx"], self.o["preStarts"]), (0, 0))

    def test_all_sounds_schedule_no_errors(self):
        self.assertTrue(self.o["unlocked"])
        self.assertEqual(self.o["post"], [True] * 6)
        self.assertTrue(self.o["postStarts"])
        self.assertEqual(self.o["err"], 0)
        self.assertFalse(self.o["bad"])
        self.assertGreaterEqual(self.o["vibN"], 5)

    def test_mute_and_volume(self):
        self.assertFalse(self.o["mutedPlay"])
        self.assertTrue(self.o["mutedNoSched"])
        self.assertTrue(self.o["stored"]["m"])
        self.assertEqual(self.o["vol"], 1)
        self.assertTrue(self.o["after"])

    def test_haptics_safe_and_reduced_motion(self):
        self.assertEqual(self.o["noVib"], [True, True])
        self.assertEqual(self.o["noVibErr"], 0)
        self.assertEqual(self.o["redVib"], 0)
        self.assertFalse(self.o["redPad"])

    def test_ambience_beds(self):
        o = self.o
        self.assertTrue(o["ambPre"])                      # wanted before any gesture ...
        self.assertEqual((o["ambNoCtx"], o["ambPlayingPre"]), (0, ""))   # ... but no audio context, nothing plays
        self.assertEqual(o["ambPlaying"], "sea")          # the first gesture starts it
        self.assertTrue(o["ambStarts"])
        self.assertFalse(o["ambBad"])
        self.assertEqual(o["ambNames"], 8)
        self.assertEqual((o["ambOff"], o["ambStored"]), ("", False))   # the owner's switch stops it and is stored
        self.assertEqual(o["ambBack"], "sea")
        self.assertEqual((o["ambMuted"], o["ambUnmuted"]), ("", "sea"))  # mute silences the bed, unmute brings it back
        self.assertEqual((o["ambSwitch"], o["ambStopped"]), ("forge", ""))
        self.assertTrue(o["ambAll"])                      # all eight beds build with no error
        self.assertEqual(o["ambErr"], 0)

    def test_ambience_off_on_battery_saver(self):
        self.assertTrue(self.o["saverFlag"])
        self.assertEqual(self.o["saverAuto"], "")         # saver + no owner setting: silent
        self.assertEqual(self.o["saverOwnerOn"], "wind")  # the owner turned ambience on: it plays

    def test_pad_toggle(self):
        self.assertTrue(self.o["padOn"])
        self.assertFalse(self.o["padOff"])


if __name__ == "__main__":
    unittest.main()
