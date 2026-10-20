#!/usr/bin/env bash
# Fake python.exe for tests/test_win_scripts.py: the engine commands that would touch NinjaTrader, pip, git or the clock
# are recorded and answered from LE_T_* variables; everything else (server.py, --wait-server) runs the real python.
printf 'python' >> "$LE_T_LOG"; for a in "$@"; do printf '\t%s' "$a" >> "$LE_T_LOG"; done; printf '\n' >> "$LE_T_LOG"
all=" $* "
case "$all" in
  *"print(sys.executable)"*) echo "$0"; exit 0 ;;          # Find-Python asks for the real exe: this fake is it
  *" -m pip "*) exit 0 ;;
  *" -m engine.autoupdate "*) exit 0 ;;
  *" -m engine.ninjatrader "*" --start "*) echo "fake: bot started"; exit "${LE_T_START_RC:-0}" ;;
  *" -m engine.ninjatrader "*) exit 0 ;;
  *" -m engine.ops_checks --update-guard "*) echo "fake update guard"; exit "${LE_T_GUARD:-0}" ;;
  *" -m engine.ops_checks --wait-server "*) exec "$LE_T_PYREAL" "$@" ;;
  *" -m engine.ops_checks"*) echo "fake health check: all green"; exit "${LE_T_HEALTH_RC:-0}" ;;
  " --version ") echo "Python 3.12.7"; exit 0 ;;
esac
exec "$LE_T_PYREAL" "$@"
