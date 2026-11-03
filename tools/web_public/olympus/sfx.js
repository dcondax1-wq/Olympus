/* OLYMPUS sensory layer: synthesized WebAudio sounds + haptics. No files, no CDN.
   window.OLYMPUS_SFX = { play(name), stop(name), mute(on?), setVolume(v), unlock(), state(), names }
   Sounds: tick, tap, portal, thunder, rankup, pad.  Silent until the first user gesture.
   Settings in localStorage 'olympus.sfx' = {"v":0.35,"m":false}.
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
  var HAPTIC = { tick: 4, tap: 8, portal: [10, 30, 18], thunder: [30, 40, 60, 40, 90], rankup: [15, 40, 15, 40, 40] };

  function create(env) {
    env = env || {};
    var ctx = null, master = null, padNode = null, unlocked = false, listening = false;
    var vol = 0.35, muted = false, errors = 0, scheduled = 0;

    function ls() { try { return env.localStorage || null; } catch (e) { return null; } }
    function load() {
      try {
        var s = ls(); var o = s && JSON.parse(s.getItem(KEY) || 'null');
        if (o && typeof o.v === 'number') vol = clamp(o.v);
        if (o && typeof o.m === 'boolean') muted = o.m;
      } catch (e) {}
    }
    function save() { try { var s = ls(); if (s) s.setItem(KEY, JSON.stringify({ v: vol, m: muted })); } catch (e) {} }
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
      return !!c;
    }
    function listen() {
      if (listening || !env.addEventListener) return;
      listening = true;
      var evs = ['pointerdown', 'touchend', 'click', 'keydown'];
      var h = function () { evs.forEach(function (e) { env.removeEventListener(e, h, true); }); unlock(); };
      evs.forEach(function (e) { env.addEventListener(e, h, true); });
      if (env.document && env.document.addEventListener) {
        env.document.addEventListener('visibilitychange', function () {
          if (!ctx) return;
          try { if (env.document.hidden) { ctx.suspend && ctx.suspend(); } else if (unlocked) { ctx.resume && ctx.resume(); } } catch (e) {}
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
      if (muted) stopPad();
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
    return { play: play, stop: stop, mute: mute, setVolume: setVolume, unlock: unlock, state: state, names: NAMES.slice() };
  }
  return { create: create };
});
