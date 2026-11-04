// The ONE table of the Data City's density caps (no DOM, no three.js). Three profiles:
//   full   a PC at the ultra / high tier: everything on (about 100-110 draw calls, 350-480k triangles)
//   phone  a phone (small viewport, a coarse pointer or iOS) at the high tier, or the battery saver: about 60 calls / 220k triangles, no
//          airships, 2 trains of 4 cars, one reflected tile, one neon board per district, thinner fireworks, no lens flare / aurora /
//          fireflies, a pixel ratio of at most 1.5
//          (farAlt: above this camera height the small details nobody can see from the overview are not drawn: heralds, billboards, rail pylons,
//          sign poles, cranes; lmLod: the temple and the Pharos beyond this distance)
//   lite   the LITE tier (OLYMPUS low / off), exactly what it always was
// profileOf(level, phone, saver): 'low' / 'off' = lite; (phone or saver) below ultra = phone; else full. ?phone=1 / ?phone=0 forces the hint.
export const PROFILES = {
  full: { cars: 520, flyers: 90, airships: 3, trains: [3, 6], ships: 9, cranes: 8, signs: 2, boards: 4, mirrors: 4, mirrorNear: 100, maxFull: 22, lod: 170, rich: 70,
          outskirts: 2600, pulses: 34, drops: 7000, flow: 1600, stars: 1800, oldCars: 1500, fog: 3, shells: 8, spark: 1, lmLod: 0, farAlt: 0, dpr: 1.75,
          kit: { godGroups: 2, lens: true, aurora: true, fireflies: true, lightning: true } },
  phone: { cars: 160, flyers: 28, airships: 0, trains: [2, 4], ships: 5, cranes: 4, signs: 1, boards: 2, mirrors: 1, mirrorNear: 60, maxFull: 7, lod: 125, rich: 0,
           outskirts: 800, pulses: 12, drops: 3000, flow: 600, stars: 700, oldCars: 0, fog: 1, shells: 3, spark: 0.5, lmLod: 330, farAlt: 150, dpr: 1.5,
           kit: { godGroups: 1, lens: false, aurora: false, fireflies: false, lightning: true } },
  lite: { cars: 160, flyers: 28, airships: 3, trains: [1, 6], ships: 4, cranes: 8, signs: 2, boards: 4, mirrors: 0, mirrorNear: 0, maxFull: 12, lod: 125, rich: 0,
          outskirts: 900, pulses: 11, drops: 1800, flow: 420, stars: 450, oldCars: 420, fog: 1, shells: 8, spark: 1, lmLod: 0, farAlt: 0, dpr: 1.5,
          kit: { godGroups: 2, lens: true, aurora: true, fireflies: true, lightning: true } },
};

/** is this a phone? small viewport, a coarse pointer or iOS (?phone=1 / ?phone=0 force it, for tests) */
export function phoneHint() {
  try {
    const f = new URLSearchParams(location.search).get('phone');
    if (f === '1') return true;
    if (f === '0') return false;
    const small = Math.min(innerWidth, innerHeight) <= 520, coarse = !!matchMedia('(pointer: coarse)').matches;
    const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    return small || coarse || ios;
  } catch (e) { return false; }
}

export function profileOf(level, phone, saver) {
  if (level === 'low' || level === 'off') return 'lite';
  // 2026-11-04: phones keep the FULL look (owner: the phone cuts made it look worse); the thin 'phone' profile is only for the battery saver
  // or an explicit ?phone=1 (phoneHint() still answers true for ?phone=1, so a test or the owner can ask for it)
  const forced = (() => { try { return new URLSearchParams(location.search).get('phone') === '1'; } catch (e) { return false; } })();
  return (saver || forced) && level !== 'ultra' ? 'phone' : 'full';
}
