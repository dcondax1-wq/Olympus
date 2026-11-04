/* OLYMPUS sensory layer: synthesized WebAudio sounds + haptics. No files, no CDN.
   window.OLYMPUS_SFX = { play(name), stop(name), mute(on?), setVolume(v), unlock(), state(), names }
   Sounds: tick, tap, portal, thunder, rankup, pad.  Silent until the first user gesture.
   Ambience (2026-11-04, docs/OLYMPUS_SFX.md): ambient(name) / ambientStop() / ambience(on?) / ambientState(): low, synthesised beds
   (wind, forge, sea, city, forest, crowd, chimes, space), gesture-gated, silent when muted, off in battery-saver (unless the owner
   turned ambience on), paused on a hidden tab. Setting 'a': true | false | absent (= on unless battery saver).
   Settings in localStorage 'olympus.sfx' = {"v":0.35,"m":false,"a":true}.
   iOS: WebAudio follows the ringer switch (silent switch = no sound). We never override it
   (audioSession 'ambient' where supported); haptics are a safe no-op on iOS Safari. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && !root.OLYMPUS_SFX) root.OLYMPUS_SFX = api.create(root);
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  var KEY = 'olympus.sfx';
  var NAMES = ['tick', 'tap', 'portal', 'thunder', 'rankup', 'pad'];
  var AMBIENTS = ['wind', 'forge', 'sea', 'city', 'forest', 'crowd', 'chimes', 'space'];
  var AMB_LEVEL = 0.5;   // the bed's bus, relative to the master (the sounds' own peaks are ~0.1-0.4): a murmur under everything
  var HAPTIC = { tick: 4, tap: 8, portal: [10, 30, 18], thunder: [30, 40, 60, 40, 90], rankup: [15, 40, 15, 40, 40] };

  function create(env) {
    env = env || {};
    var ctx = null, master = null, padNode = null, unlocked = false, listening = false;
    var vol = 0.35, muted = false, errors = 0, scheduled = 0;
    var ambOn = null, ambWant = '', ambPlay = null, noiseBuf = null;   // ambience: owner's setting (null = auto), the wanted bed, the running one

    function ls() { try { return env.localStorage || null; } catch (e) { return null; } }
    function load() {
      try {
        var s = ls(); var o = s && JSON.parse(s.getItem(KEY) || 'null');
        if (o && typeof o.v === 'number') vol = clamp(o.v);
        if (o && typeof o.m === 'boolean') muted = o.m;
        if (o && typeof o.a === 'boolean') ambOn = o.a;
      } catch (e) {}
    }
    function save() { try { var s = ls(); if (s) { var o = { v: vol, m: muted }; if (ambOn !== null) o.a = ambOn; s.setItem(KEY, JSON.stringify(o)); } } catch (e) {} }
    function clamp(x) { x = +x; return isNaN(x) ? 0 : Math.max(0, Math.min(1, x)); }
    function reduced() {
      try { return !!(env.matchMedia && env.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
    }
    function applyGain() {
      if (master && ctx) { try { master.gain.setTargetAtTime(muted ? 0 : vol * vol, ctx.currentTime, 0.02); } catch (e) {} }
    }

    function ensureCtx() {
      if (ctx) return ctx;
      var AC = env.AudioContext || env.webkitAudioContext;
      if (!AC) return null;
      try {
        try { if (env.navigator && env.navigator.audioSession) env.navigator.audioSession.type = 'ambient'; } catch (e) {}
        ctx = new AC();
        master = ctx.createGain();
        var comp = ctx.createDynamicsCompressor ? ctx.createDynamicsCompressor() : null;
        if (comp) { master.connect(comp); comp.connect(ctx.destination); } else master.connect(ctx.destination);
        applyGain();
      } catch (e) { errors++; ctx = null; }
      return ctx;
    }

    function unlock() {
      if (unlocked) return true;
      unlocked = true; // only called from a gesture handler (or explicitly by page code inside a gesture)
      var c = ensureCtx();
      try { if (c && c.state === 'suspended' && c.resume) c.resume(); } catch (e) { errors++; }
      ambRefresh();
      return !!c;
    }
    function listen() {
      if (listening || !env.addEventListener) return;
      listening = true;
      var evs = ['pointerdown', 'touchend', 'click', 'keydown'];
      var h = function () { evs.forEach(function (e) { env.removeEventListener(e, h, true); }); unlock(); };
      evs.forEach(function (e) { env.addEventListener(e, h, true); });
      try { env.addEventListener('storage', function (e) { if (e && e.key === KEY) { load(); ambRefresh(); } }); } catch (e) {}   // Jarvis's settings switch, from another frame
      if (env.document && env.document.addEventListener) {
        env.document.addEventListener('visibilitychange', function () {
          if (!ctx) return;
          try { if (env.document.hidden) { ctx.suspend && ctx.suspend(); } else if (unlocked) { ctx.resume && ctx.resume(); } } catch (e) {}
          ambRefresh();
        });
      }
    }

    /* ---- synthesis helpers ---- */
    function osc(type, f0, f1, t, dur, peak, dest, att) {
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.type = type; o.frequency.setValueAtTime(f0, t);
      if (f1 && f1 !== f0) o.frequency.exponentialRampToValueAtTime(f1, t + dur);
      att = att || 0.005;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.linearRampToValueAtTime(peak, t + att);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g); g.connect(dest || master);
      o.start(t); o.stop(t + dur + 0.05); scheduled++;
    }
    function noise(t, dur, peak, filt, f0, f1, q, dest) {
      var n = Math.max(1, Math.floor(ctx.sampleRate * dur)), buf = ctx.createBuffer(1, n, ctx.sampleRate), d = buf.getChannelData(0);
      var s = 1234567;
      for (var i = 0; i < n; i++) { s = (s * 1664525 + 1013904223) >>> 0; d[i] = (s / 4294967296) * 2 - 1; }
      var src = ctx.createBufferSource(); src.buffer = buf;
      var f = ctx.createBiquadFilter(); f.type = filt; f.frequency.setValueAtTime(f0, t);
      if (f1) f.frequency.exponentialRampToValueAtTime(f1, t + dur);
      f.Q.value = q || 0.7;
      var g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t);
      g.gain.linearRampToValueAtTime(peak, t + Math.min(0.3, dur * 0.35));
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      src.connect(f); f.connect(g); g.connect(dest || master);
      src.start(t); src.stop(t + dur + 0.05); scheduled++;
    }

    var S = {
      tick: function (t) { // marble tick: tiny bright knock
        osc('triangle', 2200, 1500, t, 0.05, 0.22); osc('sine', 880, 700, t, 0.07, 0.12);
      },
      tap: function (t) { // gold tap: soft two-partial chime
        osc('sine', 1318, 1318, t, 0.28, 0.2); osc('sine', 1976, 1976, t, 0.22, 0.1); osc('triangle', 330, 300, t, 0.09, 0.12);
      },
      portal: function (t) { // rising filtered whoosh + shimmer
        noise(t, 1.1, 0.5, 'bandpass', 250, 3800, 1.4);
        osc('sine', 180, 900, t, 1.0, 0.12, null, 0.4); osc('sine', 1200, 2400, t + 0.5, 0.7, 0.06, null, 0.2);
      },
      thunder: function (t) { // crack + low rumble with long tail
        var long = reduced() ? 1.6 : 3.2;
        noise(t, 0.12, 0.9, 'highpass', 1500, 600, 0.7);
        noise(t + 0.05, long, 0.9, 'lowpass', 420, 60, 0.8);
        osc('sine', 62, 34, t + 0.05, long, 0.5, null, 0.15); osc('sawtooth', 48, 30, t + 0.2, long * 0.8, 0.12, null, 0.3);
      },
      rankup: function (t) { // gold arpeggio C-E-G-C then shimmering chord
        [523.25, 659.25, 783.99, 1046.5].forEach(function (f, i) {
          var s = t + i * 0.13;
          osc('sawtooth', f, f, s, 0.9 - i * 0.05, 0.1); osc('sine', f * 2, f * 2, s, 0.8, 0.07);
        });
        var e = t + 0.55;
        [1046.5, 1318.5, 1568].forEach(function (f) { osc('triangle', f, f, e, 1.4, 0.09, null, 0.03); });
        noise(e, 1.2, 0.08, 'highpass', 6000, 9000, 0.5);
      }
    };

    function startPad(t) {
      if (padNode || reduced()) return;
      var g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(0.16, t + 3);
      var lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 900;
      lp.connect(g); g.connect(master);
      var oscs = [110, 164.81, 220, 329.63].map(function (f, i) {
        var o = ctx.createOscillator(); o.type = i % 2 ? 'sine' : 'triangle'; o.frequency.value = f; o.detune.value = (i - 1.5) * 6;
        var og = ctx.createGain(); og.gain.value = 0.25; o.connect(og); og.connect(lp); o.start(t); scheduled++; return o;
      });
      var lfo = ctx.createOscillator(), lg = ctx.createGain();
      lfo.frequency.value = 0.07; lg.gain.value = 300; lfo.connect(lg); lg.connect(lp.frequency); lfo.start(t);
      padNode = { g: g, oscs: oscs.concat([lfo]) };
    }
    function stopPad() {
      if (!padNode || !ctx) return;
      var p = padNode, t = ctx.currentTime; padNode = null;
      try {
        p.g.gain.cancelScheduledValues(t); p.g.gain.setValueAtTime(0.1, t); p.g.gain.linearRampToValueAtTime(0.0001, t + 1.5);
        p.oscs.forEach(function (o) { o.stop(t + 1.6); });
      } catch (e) { errors++; }
    }

    /* ---- ambience: low synthesised beds. One shared noise loop; each bed = a few filters + slow LFOs (+ sparse events on a timer). ---- */
    function batterySaver() { try { var O = env.OLYMPUS; return !!(O && O.saver && O.saver()); } catch (e) { return false; } }
    function ambAllowed() { return !muted && (ambOn === null ? !batterySaver() : ambOn); }   // owner's switch wins; auto = on unless battery saver
    function noiseLoop() {
      if (noiseBuf) return noiseBuf;
      var n = Math.max(2, Math.floor(ctx.sampleRate * 2)), b = ctx.createBuffer(1, n, ctx.sampleRate), d = b.getChannelData(0), s = 987654321, last = 0;
      for (var i = 0; i < n; i++) { s = (s * 1664525 + 1013904223) >>> 0; var w = (s / 4294967296) * 2 - 1; last = (last + 0.06 * w) / 1.06; d[i] = last * 3.2 + w * 0.15; }   // soft pink-ish
      return (noiseBuf = b);
    }
    function ambNoise(bus, type, f, q, gain) {            // a looping noise -> filter -> gain -> bus
      var src = ctx.createBufferSource(); src.buffer = noiseLoop(); src.loop = true;
      var fl = ctx.createBiquadFilter(); fl.type = type; fl.frequency.value = f; fl.Q.value = q || 0.7;
      var g = ctx.createGain(); g.gain.value = gain;
      src.connect(fl); fl.connect(g); g.connect(bus); src.start(0); scheduled++;
      return { g: g, f: fl, src: src };
    }
    function lfo(rate, depth, target, base) {             // a slow sine on an AudioParam
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = rate; g.gain.value = depth; o.connect(g); g.connect(target); if (base !== undefined) target.value = base;
      o.start(0); scheduled++; return o;
    }
    function drone(bus, f, gain, detune) {
      var o = ctx.createOscillator(), g = ctx.createGain(); o.type = 'sine'; o.frequency.value = f; if (detune) o.detune.value = detune;
      g.gain.value = gain; o.connect(g); g.connect(bus); o.start(0); scheduled++; return o;
    }
    function every(min, max, fn) {                        // a self-rescheduling random timer; { on, id }
      var h = { id: 0, on: true };
      (function next() { h.id = setTimeout(function () { if (!h.on) return; try { fn(); } catch (e) { errors++; } next(); }, min + Math.random() * (max - min)); })();
      return h;
    }
    // each bed returns { osc, src, timers } (what a stop has to end); T collects the sparse-event timers
    var BEDS = {
      wind: function (bus) {                              // temple wind: band-passed noise breathing slowly
        var a = ambNoise(bus, 'bandpass', 420, 0.8, 0.5);
        return { osc: [lfo(0.07, 0.35, a.g.gain, 0.5), lfo(0.05, 160, a.f.frequency, 420)], src: [a.src], timers: [] };
      },
      forge: function (bus, T) {                          // low furnace roar + random crackles
        var a = ambNoise(bus, 'lowpass', 160, 0.7, 0.9);
        T.push(every(90, 420, function () { noise(ctx.currentTime + 0.01, 0.05 + Math.random() * 0.06, 0.05 + Math.random() * 0.07, 'highpass', 2500 + Math.random() * 3000, 0, 1, bus); }));
        return { osc: [lfo(0.11, 0.25, a.g.gain, 0.8)], src: [a.src], timers: T };
      },
      sea: function (bus) {                               // waves: two slow swells over a soft wash
        var a = ambNoise(bus, 'lowpass', 520, 0.6, 0.35), b = ambNoise(bus, 'bandpass', 900, 0.5, 0.12);
        return { osc: [lfo(0.12, 0.3, a.g.gain, 0.4), lfo(0.17, 0.1, b.g.gain, 0.14), lfo(0.12, 220, a.f.frequency, 520)], src: [a.src, b.src], timers: [] };
      },
      city: function (bus) {                              // distant city hum: mains-ish drones + a dull noise floor
        var a = ambNoise(bus, 'lowpass', 280, 0.5, 0.25);
        return { osc: [drone(bus, 55, 0.12), drone(bus, 110.4, 0.06, 3), drone(bus, 164.5, 0.025, -4), lfo(0.04, 0.08, a.g.gain, 0.25)], src: [a.src], timers: [] };
      },
      forest: function (bus, T) {                         // leaves + now and then a bird
        var a = ambNoise(bus, 'highpass', 3200, 0.5, 0.13);
        T.push(every(2500, 8000, function () { var t = ctx.currentTime + 0.02, f = 2600 + Math.random() * 1800; osc('sine', f, f * 1.25, t, 0.12, 0.05, bus); osc('sine', f * 1.1, f * 1.4, t + 0.16, 0.1, 0.04, bus); }));
        return { osc: [lfo(0.09, 0.06, a.g.gain, 0.13)], src: [a.src], timers: T };
      },
      crowd: function (bus, T) {                          // a far crowd: murmur that swells now and then
        var a = ambNoise(bus, 'bandpass', 700, 0.5, 0.4), b = ambNoise(bus, 'bandpass', 1400, 0.7, 0.15);
        T.push(every(3000, 9000, function () { var g = a.g.gain, t = ctx.currentTime; g.cancelScheduledValues(t); g.setValueAtTime(0.4, t); g.linearRampToValueAtTime(0.65, t + 0.8); g.linearRampToValueAtTime(0.4, t + 3); }));
        return { osc: [lfo(0.23, 0.12, b.g.gain, 0.15)], src: [a.src, b.src], timers: T };
      },
      chimes: function (bus, T) {                         // wind chimes: sparse pentatonic pings with long tails, a breath of air
        var a = ambNoise(bus, 'bandpass', 600, 0.9, 0.12), P = [659.25, 783.99, 880, 1174.66, 1318.5];
        T.push(every(1500, 5000, function () { var t = ctx.currentTime + 0.02, f = P[Math.floor(Math.random() * P.length)]; osc('sine', f, 0, t, 2.6, 0.06, bus, 0.004); osc('sine', f * 2.01, 0, t, 1.4, 0.02, bus, 0.004); }));
        return { osc: [lfo(0.06, 0.08, a.g.gain, 0.12)], src: [a.src], timers: T };
      },
      space: function (bus) {                             // deep space: sub drones beating slowly + a hiss
        var a = ambNoise(bus, 'highpass', 5000, 0.5, 0.03);
        return { osc: [drone(bus, 41.2, 0.16), drone(bus, 41.9, 0.12), drone(bus, 62, 0.05, 6), lfo(0.03, 0.02, a.g.gain, 0.03)], src: [a.src], timers: [] };
      }
    };
    function ambStop() {
      var p = ambPlay; ambPlay = null;
      if (!p || !ctx) return;
      try {
        p.timers.forEach(function (h) { h.on = false; clearTimeout(h.id); });
        var t = ctx.currentTime;
        p.bus.gain.cancelScheduledValues(t); p.bus.gain.setValueAtTime(p.bus.gain.value || AMB_LEVEL, t); p.bus.gain.linearRampToValueAtTime(0.0001, t + 0.8);
        setTimeout(function () { try { p.osc.forEach(function (o) { o.stop(); }); p.src.forEach(function (s) { s.stop(); }); if (p.bus.disconnect) p.bus.disconnect(); } catch (e) {} }, 900);
      } catch (e) { errors++; }
    }
    function ambRefresh() {                               // start / stop so that what plays matches: wanted bed, gesture, setting, saver, visible
      try {
        var hidden = !!(env.document && env.document.hidden);
        var want = ambWant && ambAllowed() && unlocked && !hidden ? ambWant : '';
        if (ambPlay && ambPlay.name !== want) ambStop();
        if (!want || ambPlay || !ensureCtx() || !BEDS[want]) return;
        var bus = ctx.createGain(), t = ctx.currentTime;
        bus.gain.setValueAtTime(0.0001, t); bus.gain.linearRampToValueAtTime(AMB_LEVEL, t + 2.5); bus.connect(master);
        var bed = BEDS[want](bus, []);
        ambPlay = { name: want, bus: bus, osc: bed.osc, src: bed.src, timers: bed.timers };
      } catch (e) { errors++; ambStop(); }
    }
    /** ambient('sea'): the bed this page wants. Starts after the first gesture (and while the setting allows it); ambient('') or ambientStop() ends it. */
    function ambient(name) {
      name = String(name || '');
      if (name && AMBIENTS.indexOf(name) < 0) return false;
      ambWant = name;
      if (!name) { ambStop(); return true; }
      listen(); ambRefresh(); return true;
    }
    function ambientStop() { ambWant = ''; ambStop(); }
    /** ambience(true | false): the owner's switch (stored, shared with every OLYMPUS page); ambience() = whether a bed may play now */
    function ambience(on) {
      if (on === undefined) return ambAllowed();
      ambOn = !!on; save(); ambRefresh(); return ambAllowed();
    }
    function ambientState() { return { want: ambWant, playing: ambPlay ? ambPlay.name : '', allowed: ambAllowed(), setting: ambOn, saver: batterySaver(), names: AMBIENTS.slice() }; }

    function haptic(name) {
      try {
        if (muted || reduced() || !HAPTIC[name]) return false;
        var n = env.navigator;
        if (!n || typeof n.vibrate !== 'function') return false; // iOS Safari: absent -> no-op
        return !!n.vibrate(HAPTIC[name]);
      } catch (e) { return false; }
    }

    function play(name) {
      try {
        if (NAMES.indexOf(name) < 0) return false;
        if (muted) return false;
        if (!unlocked || !ctx) return false; // nothing before a user gesture
        if (ctx.state === 'suspended' && ctx.resume) ctx.resume();
        var t = ctx.currentTime + 0.01;
        if (name === 'pad') { startPad(t); return true; }
        S[name](t); haptic(name); return true;
      } catch (e) { errors++; return false; }
    }
    function stop(name) { if (!name || name === 'pad') stopPad(); }
    function mute(on) {
      muted = (on === undefined) ? !muted : !!on; save();
      if (muted) { stopPad(); ambStop(); } else ambRefresh();
      applyGain(); return muted;
    }
    function setVolume(v) { vol = clamp(v); save(); applyGain(); return vol; }
    function state() {
      return {
        unlocked: unlocked, muted: muted, volume: vol, reducedMotion: reduced(), errors: errors, scheduled: scheduled,
        haptics: !!(env.navigator && typeof env.navigator.vibrate === 'function'), padOn: !!padNode, ctxState: ctx ? ctx.state : 'none'
      };
    }

    load(); listen();
    return { play: play, stop: stop, mute: mute, setVolume: setVolume, unlock: unlock, state: state, names: NAMES.slice(),
             ambient: ambient, ambientStop: ambientStop, ambience: ambience, ambientState: ambientState, ambients: AMBIENTS.slice() };
  }
  return { create: create };
});
