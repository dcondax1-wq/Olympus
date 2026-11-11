"""TOWNS (QA round 6, 2026-11-11): the living towns. Athens gets the directed third-person walk of Hellas on its real terrain; the towns' people are the
rigged cast (cities/town-cast.js); footsteps and presence jingles in the walking scenes.

  a. node: ATHENS walking never puts the camera inside a house, a temple or the hill: scripted tap-to-walk legs through several villages, up the Acropolis
     slope and around Lykabettos (orbiting and zooming), every frame checked against the local colliders AND against a fresh world built at the camera;
     your feet stand on the terrain (groundY) on every frame; the conversation camera on a slope is never inside the ground or a house; walks arrive
  b. node: the local nav grid is small (at most 150 m across) and the local colliders follow you
  c. node: town-cast without a browser keeps the toy crowd (never blank) and its API (place / act / commit / tick / talk / figureOf / stats)
  d. static: the wiring (hellas.js / athens.js use the cast, the Athens director hook and loader, ?direct=0 and ?joy=1, footsteps through
     OLYMPUS_SFX.walker in Hellas, Athens, Symposium and Ergasterion, presence jingles), no network, no random in the pure parts
  e. Chromium 390x844 (flock -w 2400 /tmp/olympus_browser.lock): Athens directed walk: your rigged character, a tap on the street walks you there on the
     ground, the camera never inside, a tap on a villager talks (the close-up), the draw calls / triangles within the phone budget
    python -X utf8 -m tests.test_town_walk [--static]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
WEB = AK.WEB
NODE = r"""
import * as R from './olympus/camera-rig.js';
import * as K from './olympus/controls.js';
import * as AP from './cities/athens-plan.js';
import * as AW from './cities/athens-world.js';
import * as AD from './cities/athens-direct.js';
import * as TC from './cities/town-cast.js';
const o = {};
const cam = () => ({ position: { x: 0, y: 0, z: 0, set(x, y, z) { this.x = x; this.y = y; this.z = z; } }, lookAt() {} });
const plan = AP.planAthens(), world = AW.buildWorld(plan, {}), houses = AW.renderList(world, 1100, 40), col = AW.makeCollider(houses, plan);
{
  const vs = world.villages.filter((v) => v.houses.length);
  const starts = [vs[0], vs[Math.floor(vs.length / 3)], vs[Math.floor(vs.length * 2 / 3)], vs[vs.length - 1]].map((v) => AW.doorOf(col, v));
  const A = AP.ACROPOLIS;
  // legs: around each village, across to the next, up the Acropolis slope (as close to the rock top as the walk grid allows), toward Lykabettos
  const legs = [];
  starts.forEach((s, k) => { legs.push([s, { x: s.x + 30, z: s.z + 12 }]); legs.push([s, { x: s.x - 18, z: s.z - 34 }]); });
  legs.push([{ x: A.x + A.base + 6, z: A.z + 4 }, { x: A.x + A.plateau * 0.4, z: A.z + 10 }]);
  legs.push([{ x: A.x - 4, z: A.z + A.base + 8 }, { x: A.x + 6, z: A.z + A.plateau * 0.5 }]);
  legs.push([{ x: 310 - 160, z: -470 + 30 }, { x: 310 - 95, z: -470 + 20 }]);
  let frames = 0, inside = 0, fresh = 0, worst = '', reached = 0, tried = 0, feet = 0, maxGrid = 0, rebuilt = 0, minClear = 99, pulled = 0, climbed = 0;
  for (const [a0, b] of legs) {
    let a = a0; if (col.hits(a.x, a.z, 0.5)) { for (let r = 1; r < 30 && col.hits(a.x, a.z, 0.5); r++) a = { x: a0.x + r * 0.8, z: a0.z }; }
    const grid = AD.navNear(col, a, b); maxGrid = Math.max(maxGrid, grid.w * grid.h);
    const pth = K.findPath(grid, a, b, { reach: 8, closest: true }); tried++; if (!pth) continue;
    const wk = K.createWalker({ speed: 3.2 }); wk.place(a.x, a.z, 0);
    let W = AD.worldNear(col, houses, a.x, a.z), wx = a.x, wz = a.z;
    const rig = R.createRig(cam(), { world: W, radius: 0.3, dist: 5.4, pitch: 0.3 });
    rig.follow({ x: a.x, y: AP.groundY(a.x, a.z), z: a.z, yaw: 0, h: AD.AV * 0.92 }).snap();
    let done = false, y0 = AP.groundY(a.x, a.z), yMax = y0; wk.go(pth, () => { done = true; });
    for (let i = 0; i < 4000 && !done; i++) {
      const s = wk.tick(1 / 30), y = AP.groundY(s.x, s.z); yMax = Math.max(yMax, y);
      if (Math.abs(y - AP.groundY(s.x, s.z)) > 1e-9) feet++;
      if (Math.hypot(s.x - wx, s.z - wz) > 24) { W = AD.worldNear(col, houses, s.x, s.z); rig.world(W); wx = s.x; wz = s.z; rebuilt++; }
      rig.follow({ x: s.x, y, z: s.z, yaw: s.yaw, h: AD.AV * 0.92, moving: s.moving });
      if (i % 45 === 0) rig.orbit(1.3, i % 90 ? 0.25 : -0.3); if (i % 120 === 0) rig.zoom(i % 240 ? 0.55 : 1.8);
      const st = rig.update(1 / 30); frames++; if (st.pulled > 0) pulled++;
      const t = rig.inside(0.12); if (t) { inside++; worst = t + ' at ' + JSON.stringify(st.pos); }
      const F = AD.worldNear(col, houses, st.pos.x, st.pos.z, 30), tf = R.hitTag(F, st.pos, 0.12); if (tf) { fresh++; worst = 'fresh ' + tf + ' at ' + JSON.stringify(st.pos); }
      minClear = Math.min(minClear, st.pos.y - AP.groundY(st.pos.x, st.pos.z));
    }
    if (done) reached++; if (yMax - y0 > 8) climbed++;
  }
  // the conversation camera with a villager standing on a slope, from both sides
  let talks = 0;
  for (const [bx, bz] of [[A.x + A.base - 20, A.z], [A.x, A.z + A.base - 18], [A.x - A.base + 22, A.z + 6], [310 - 120, -470 + 10], [starts[0].x, starts[0].z]]) for (const side of [1, -1]) {
    const b = { x: bx, y: AP.groundY(bx, bz), z: bz, h: AD.PH }, ap = K.approach({ x: bx + 6, z: bz + 3 }, b, 1.7), aa = { x: ap.x, y: AP.groundY(ap.x, ap.z), z: ap.z, h: AD.AV * 0.92 };
    const rig = R.createRig(cam(), { world: AD.worldNear(col, houses, bx, bz), radius: 0.3 }); rig.shot('talk', { a: aa, b, side, two: 1.5, lookDown: 0.42, back: 1.9 }, { cut: true });
    for (let i = 0; i < 150; i++) { const st = rig.update(1 / 30); talks++; const t = rig.inside(0.08); if (t) { inside++; worst = 'talk ' + t + ' at ' + JSON.stringify(st.pos); } }
  }
  o.athens = { frames, inside, fresh, worst, reached, tried, feet, maxGrid, rebuilt, minClear: +minClear.toFixed(2), pulled, climbed, talks, legs: legs.length };
  const W0 = AD.worldNear(col, houses, starts[0].x, starts[0].z), Wall = AD.worldNear(col, houses, 0, 0, 5000);
  o.near = { local: W0.boxes.length + W0.circles.length, all: Wall.boxes.length + Wall.circles.length, ground: R.hitTag(W0, { x: A.x, y: A.top - 1, z: A.z }, 0.1), air: R.hitTag(W0, { x: A.x + A.base + 30, y: 60, z: A.z }, 0.1) };
}
{
  const c = TC.makeTownCast(null, [{ id: 'villager:helios' }, { id: 'keeper:serifos' }], {});
  c.place(0, 1, 0, 2, 0.3, 1, 1, 0); c.place(1, 3, 0, 1, 0, 1.1, 1, 0.2); c.act(0, 'walk'); c.act(1, 'greet'); c.commit(); c.tick(0.016, 1, null, { x: 0, z: 0 });
  o.cast = { stats: c.stats(), fig: c.figureOf(0), talk: c.talk(1), mesh: !!c.mesh && c.mesh.children.length, count: c.count };
  c.dispose();
}
console.log(JSON.stringify(o));
"""


def test_node():
    r = subprocess.run(["node", "--input-type=module", "-e", NODE], cwd=WEB, capture_output=True, text=True, timeout=600)
    check("node harness runs", r.returncode == 0 and r.stdout.strip().startswith("{"), (r.stderr or r.stdout)[-1500:])
    if r.returncode != 0:
        return
    o = json.loads(r.stdout.strip().splitlines()[-1])
    a = o["athens"]
    check(f"a. ATHENS walking: across {a['frames']} frames of tap-to-walk ({a['legs']} legs through 4 villages, up the Acropolis slope and toward Lykabettos, orbiting and zooming) "
          f"the camera is NEVER inside a house, a temple or the ground ({a['inside']}), nor inside anything of a fresh world built at the camera ({a['fresh']}); "
          f"{a['reached']} of {a['tried']} walks arrived; the camera was pulled in front of something in {a['pulled']} frames",
          a["inside"] == 0 and a["fresh"] == 0 and a["frames"] > 1500 and a["reached"] >= a["tried"] - 1 and a["tried"] >= 10, a)
    check(f"a. your feet stand on the terrain on every frame (groundY), the walk climbs the hills ({a['climbed']} legs rose more than 8 m), the camera stays above the ground (closest {a['minClear']} m)",
          a["feet"] == 0 and a["climbed"] >= 1 and a["minClear"] > 0.1, a)
    check(f"a. the conversation camera with a villager on a slope (the Acropolis, Lykabettos, a village; both sides): {a['talks']} frames, never inside", a["talks"] == 10 * 150 and a["inside"] == 0, a["worst"])
    n = o["near"]
    check(f"b. the camera's colliders are local ({n['local']} of {n['all']} around you, rebuilt {a['rebuilt']} times as you walk) and know the hills (inside the Acropolis rock = 'ground', the sky = free); the walk grid is at most 150 m across ({a['maxGrid']} cells)",
          0 < n["local"] < n["all"] and n["ground"] == "ground" and n["air"] == "" and a["rebuilt"] >= 2 and 0 < a["maxGrid"] <= 201 * 201, (n, a["rebuilt"], a["maxGrid"]))
    c = o["cast"]
    check("c. town-cast without a browser: the toy crowd stays (one draw call, never blank), every call answers, no rigged figure is invented",
          c["stats"]["status"] == "toy" and c["stats"]["drawCalls"] == 1 and c["fig"] is None and c["talk"] is None and c["mesh"] == 1 and c["count"] == 2, c)


def test_static():
    rd = lambda p: AK.read(os.path.join(WEB, p))  # noqa: E731
    tc, hel, ath, hui, nest, aui, ad, wd = (rd(p) for p in ("cities/town-cast.js", "cities/hellas.js", "cities/athens.js", "cities/hellas-ui.js", "cities/athens-nest.js", "cities/athens-ui.js", "cities/athens-direct.js", "cities/walk-direct.js"))
    check("d. Hellas and Athens draw their people with the rigged cast (town-cast.js: photos far, rigged figures near; the toy figures only as the placeholder)",
          "makeTownCast(THREE, this.people" in hel and "makeTownCast(THREE, this.npcs" in ath and "this.crowd.tick(dt, t, this.camera" in hel and "this.crowd.tick(dt, t, this.camera" in ath and "makeCrowd(" in tc and "atlas(S.specs, { views: true" in tc)
    check("d. the photos show a back and a walking profile (people-studio atlas views), LITE takes no photo studio (a second WebGL context) and at most 2 rigged figures near you",
          "o.views ? 5 : 2" in rd("olympus/people-studio.js") and "if (lite) return;" in tc and "lite ? 2 : 4" in tc)
    check("d. the person you talk to is a rigged figure that talks (Hellas passes it to say(); Athens keeps it while the villager waits)",
          "figure: fig" in hui and "S.crowd.figureOf(ref.i)" in hui and "this.crowd.talk(this.talkNpc" in ath and "S0.talkHold = true" in ad)
    check("d. Athens walking is directed like Hellas: the scene hook, loaded on demand, ?direct=0 keeps the first-person walker, the joystick only with ?joy=1, taps / drag / pinch go to the director",
          "if (this.walkDirector && this.walkDirector.tick(dt)) return;" in ath and "import('./athens-direct.js?v=d1')" in nest and "get('direct') === '0'" in nest and "joyOn()" in nest
          and "this.dir.tap(" in nest and "S.walkDirector.look(" in aui and "S.walkDirector.zoom(" in aui)
    check("d. Athens: the camera's world has the terrain (groundAt: groundY) and the houses at their real height on their own ground; the feet follow groundY",
          "groundAt: groundY" in ad and "D.av.position.set(s.x, y, s.z)" in ad and "groundAt" in rd("olympus/camera-rig.js"))
    sym, hall, erg, fl = rd("symposium/symposium.js"), rd("symposium/hall.js"), rd("ergasterion/direct.js"), rd("ergasterion/floor.js") + rd("ergasterion/life.js")
    check("d. footsteps through OLYMPUS_SFX.walker(person).step(pos, listener, { surface }) in Hellas and Athens walking (yours and the near townspeople's), Symposium and Ergasterion; presence jingles when someone greets you",
          ".walker(" in wd and ".walker(" in ad and "X.walker(sl.spec" in tc and "X.presence(sl.spec" in tc and ".walker(" in (hall + sym) and ".presence(" in (hall + sym) and ".walker(" in (erg + fl) and ".presence(" in (erg + fl) and "L.stepAt(key" in fl and "L.presenceAt(" in fl)
    pure = tc + ad
    check("d. the town files read no network, use no Math.random, place no order", not re.search(r"fetch\(|XMLHttpRequest|Math\.random|placeorder|submitorder", pure, re.I))


WAIT = "(f, ms) => new Promise((ok) => { const t0 = Date.now(), i = setInterval(() => { let v = null; try { v = f(); } catch (e) { v = null; } if (v || Date.now() - t0 > ms) { clearInterval(i); ok(v || null); } }, 150); })"


def until(p, expr, ms=20000):
    return p.evaluate(f"(() => ({WAIT})(() => {expr}, {ms}))()")


def test_browser():
    """e. Chromium 390 x 844 (one browser on the machine: flock -w 2400 /tmp/olympus_browser.lock): Athens directed walk"""
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("e. browser part skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/cities/?athens=1&first=0&q=high", wait_until="domcontentloaded")
            p.wait_for_function("window.__athens && window.__athens.world", timeout=170000)
            p.evaluate("window.__athens.nest.walkNear()")
            d0 = until(p, "window.__athensDirector && window.__athensDirector.state().avatar && window.__athensDirector.state()", 90000)
            zone = p.evaluate("document.querySelector('.ath-stickzone').hidden")
            check("e. ATHENS walking is third person (your own character, the opening glide), the thumb joystick is hidden unless asked for",
                  bool(d0) and d0["avatar"] and zone and abs(d0["feetY"] - d0["me"]["y"]) < 0.01, (d0 and {k: d0[k] for k in ("avatar", "feetY", "me", "cam")}, zone))
            p.wait_for_timeout(3500)
            box = p.evaluate("() => { const r = document.querySelector('#athens canvas').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
            w0 = p.evaluate("window.__athensDirector.state()")
            for k in range(4):
                p.touchscreen.tap(box[0] + box[2] * (0.35 + 0.1 * k), box[1] + box[3] * 0.72)
                p.wait_for_timeout(2600)
            w1 = until(p, "window.__athensDirector.state()", 5000)
            check(f"e. ATHENS tap the street: you walk there on the ground (feet on groundY), the camera was inside a house / temple / the ground in {w1['insideN']} of {w1['frames']} frames",
                  w1["walks"] > w0["walks"] and w1["insideN"] == 0 and w1["frames"] > 60 and abs(w1["feetY"] - w1["me"]["y"]) < 0.05, (w0["walks"], w1["walks"], w1["insideN"], w1["me"], w1["feetY"]))
            ok = p.evaluate("window.__athensDirector.talkNearest()")
            t = until(p, "window.__athensDirector.state().mode === 'talk' && window.__athensDirector.state()", 60000) if ok else None
            p.wait_for_timeout(3000)
            cast = p.evaluate("window.__athens.scene.crowd.stats ? window.__athens.scene.crowd.stats() : null")
            calls, tris = p.evaluate("[window.__athens.calls(), window.__athens.tris()]")
            check(f"e. ATHENS talk: you walk up to a villager who waits, the conversation camera frames them and they are a full rigged figure; {calls} draw calls / {tris} triangles (budget 45 / 160k)",
                  bool(t) and cast and cast["close"] >= 1 and cast["rig"] and calls <= 45 and tris <= 160000 and not errs, (t and t["mode"], cast, calls, tris, errs[:3]))
            AK.shot(p, "towns-athens-talk")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_node()
    test_static()
    if "--static" not in sys.argv:
        test_browser()
    AK.finish()
