#!/usr/bin/env bash
# Fake git for tests/test_win_scripts.py (no real repository is touched): branch / dirty state from files in LE_T_GIT.
printf 'git' >> "$LE_T_LOG"; for a in "$@"; do printf '\t%s' "$a" >> "$LE_T_LOG"; done; printf '\n' >> "$LE_T_LOG"
[ "$1" = "-C" ] && shift 2
case "$1" in
  --version) echo "git version 2.47.0.windows.1" ;;
  rev-parse) cat "$LE_T_GIT/branch" ;;
  status) cat "$LE_T_GIT/dirty" 2>/dev/null ;;
  checkout) [ -s "$LE_T_GIT/dirty" ] && exit 1; echo "$2" > "$LE_T_GIT/branch"; echo "Switched to branch '$2'" >&2 ;;
  fetch) echo "From https://github.com/x/y" >&2 ;;
  pull) echo "From https://github.com/x/y" >&2; echo "Already up to date."; exit "${LE_T_PULL_RC:-0}" ;;
  push) echo "To https://github.com/x/y" >&2 ;;
  *) echo "fake git: $1 not stubbed" >&2; exit 1 ;;
esac
