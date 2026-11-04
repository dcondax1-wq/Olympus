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
  const env={AudioContext:AC,OLYMPUS:(opts.saver||opts.lite)?{saver:()=>!!opts.saver,lite:()=>!!opts.lite}:undefined,localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>{store[k]=v}},
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
// the UI cues (open / close / success / warning) and the Sound switch (2026-11-04)
out.cues=am.s.cues; out.cuesPlay=am.s.cues.map(n=>am.s.play(n));
let lt=mk({lite:true}); lt.h.pointerdown(); lt.s.ambient('smithy');
out.liteCues=lt.s.cues.map(n=>lt.s.play(n)); out.liteTap=lt.s.play('tap'); out.liteBed=lt.s.ambientState().playing; out.liteSound=lt.s.sound();
lt.s.sound(true); out.liteOnCues=lt.s.cues.map(n=>lt.s.play(n)); out.liteOnBed=lt.s.ambientState().playing; out.liteStored=JSON.parse(lt.store['olympus.sfx']).s;
lt.s.sound(null); out.liteAuto=lt.s.ambientState().playing;
let rd=mk({reduced:true}); rd.h.pointerdown(); rd.s.ambient('lab'); out.redCues=rd.s.cues.map(n=>rd.s.play(n)); out.redBed=rd.s.ambientState().playing; rd.s.sound(true); out.redOnBed=rd.s.ambientState().playing; out.redOnCue=rd.s.play('success');
let sf=mk({}); sf.h.pointerdown(); sf.s.ambient('coins'); out.offBefore=sf.s.ambientState().playing; sf.s.sound(false); out.offBed=sf.s.ambientState().playing; out.offCue=sf.s.play('open'); out.offTap=sf.s.play('tap'); out.offAllowed=sf.s.sound();
sf.s.sound(null); out.offBack=sf.s.ambientState().playing;
let dc=mk({}); dc.h.pointerdown(); const b0=dc.log.starts; let el={getAttribute:()=> 'success'}; dc.h.click({target:{closest:(q)=>q==='[data-oly-cue]'?el:null}}); out.dataCue=dc.log.starts>b0; const b1=dc.log.starts; dc.h.click({target:{closest:()=>null}}); out.dataNone=dc.log.starts===b1;
const all=[]; for (const n of am.s.ambients) { am.s.ambient(n); all.push(am.s.ambientState().playing===n); } am.s.ambientStop(); out.ambAll=all.every(Boolean); out.ambNamesList=am.s.ambients; out.ambErr=am.s.state().errors;
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
        self.assertEqual(self.o["pre"], [False] * len(self.o["pre"]))
        self.assertGreaterEqual(len(self.o["pre"]), 10)        # tick tap portal thunder rankup pad + open close success warning
        self.assertEqual((self.o["preCtx"], self.o["preStarts"]), (0, 0))

    def test_all_sounds_schedule_no_errors(self):
        self.assertTrue(self.o["unlocked"])
        self.assertEqual(self.o["post"], [True] * len(self.o["pre"]))
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
        self.assertEqual(o["ambNames"], len(o["ambNamesList"]))
        for bed in ("wind", "forge", "sea", "city", "forest", "crowd", "chimes", "space", "smithy", "scroll", "coins", "agora", "lab", "breeze"):
            self.assertIn(bed, o["ambNamesList"])
        self.assertEqual((o["ambOff"], o["ambStored"]), ("", False))   # the owner's switch stops it and is stored
        self.assertEqual(o["ambBack"], "sea")
        self.assertEqual((o["ambMuted"], o["ambUnmuted"]), ("", "sea"))  # mute silences the bed, unmute brings it back
        self.assertEqual((o["ambSwitch"], o["ambStopped"]), ("forge", ""))
        self.assertTrue(o["ambAll"])                      # every bed builds with no error
        self.assertEqual(o["ambErr"], 0)

    def test_ambience_off_on_battery_saver(self):
        self.assertTrue(self.o["saverFlag"])
        self.assertEqual(self.o["saverAuto"], "")         # saver + no owner setting: silent
        self.assertEqual(self.o["saverOwnerOn"], "wind")  # the owner turned ambience on: it plays

    def test_ui_cues_and_the_sound_switch(self):
        o = self.o
        self.assertEqual(o["cues"], ["open", "close", "success", "warning"])
        self.assertEqual(o["cuesPlay"], [True] * 4)                       # after the first tap they sound
        self.assertEqual(o["liteCues"], [False] * 4)                      # LITE: silent by default ...
        self.assertTrue(o["liteTap"])                                     # ... but the old sounds are untouched
        self.assertEqual((o["liteBed"], o["liteSound"]), ("", False))     # a bed wanted in LITE stays silent
        self.assertEqual(o["liteOnCues"], [True] * 4)                     # the owner turned Sound on: they play
        self.assertEqual((o["liteOnBed"], o["liteStored"]), ("smithy", True))
        self.assertEqual(o["liteAuto"], "")                               # null = automatic again
        self.assertEqual(o["redCues"], [False] * 4)                       # reduced motion: silent by default
        self.assertEqual((o["redBed"], o["redOnBed"], o["redOnCue"]), ("", "lab", True))
        self.assertEqual((o["offBefore"], o["offBed"], o["offCue"], o["offTap"], o["offAllowed"]), ("coins", "", False, True, False))   # Sound off: bed and cues stop
        self.assertEqual(o["offBack"], "coins")
        self.assertTrue(o["dataCue"])                                     # data-oly-cue="success" on any element
        self.assertTrue(o["dataNone"])

    def test_every_app_has_its_own_bed(self):
        """the kit's table (olympus.js AMBIENT) gives every app in the launcher a bed that exists in sfx.js; the new fitting ones are used"""
        import re
        js = (ROOT / "tools/web_public/olympus/olympus.js").read_text(encoding="utf-8")
        table = dict(re.findall(r"(\w+): '(\w+)'", js.split("var AMBIENT = {")[1].split("};")[0]))
        beds = set(self.o["ambNamesList"])
        apps = re.findall(r"app\('([a-z0-9]+)'", (ROOT / "tools/web_public/jarvis/apps.js").read_text(encoding="utf-8"))
        self.assertTrue(apps)
        missing = [a for a in apps if a not in table]
        self.assertFalse(missing, missing)
        self.assertTrue(all(b in beds for b in table.values()), [b for b in table.values() if b not in beds])
        for app, bed in {"prometheus": "smithy", "hephaestus": "smithy", "athena": "scroll", "plutus": "coins", "ledger": "coins", "forum": "agora", "labyrinth": "lab", "fates": "lab"}.items():
            self.assertEqual(table[app], bed, app)

    def test_pad_toggle(self):
        self.assertTrue(self.o["padOn"])
        self.assertFalse(self.o["padOff"])


if __name__ == "__main__":
    unittest.main()
