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
  const env={AudioContext:AC,localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>{store[k]=v}},
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
console.log(JSON.stringify(out));
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

    def test_pad_toggle(self):
        self.assertTrue(self.o["padOn"])
        self.assertFalse(self.o["padOff"])


if __name__ == "__main__":
    unittest.main()
