// OLYMPUS Mind: sounds, only through the OLYMPUS kit (OLYMPUS.sfx(name): tick | tap | portal | thunder | rankup | pad). Without the kit,
// with the sound switched off, or while Jarvis is talking (the kit checks), nothing plays. Never throws, never blocks a tap.
//   const s = createSound(OLYMPUS, on); s.play('tap'); s.on; s.set(false)
export function createSound(kit, on = true) {
  let enabled = !!on;
  return {
    get on() { return enabled; },
    get available() { return !!(kit && typeof kit.sfx === 'function'); },
    set(v) { enabled = !!v; },
    play(name) {
      if (!enabled || !kit || typeof kit.sfx !== 'function') return false;
      try { return !!kit.sfx(name); } catch (_) { return false; }
    },
  };
}
