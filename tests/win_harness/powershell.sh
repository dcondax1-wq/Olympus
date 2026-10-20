#!/usr/bin/env bash
# Fake powershell.exe for tests/test_win_scripts.py: takes Windows PowerShell 5.1 command-line flags and runs pwsh with
# the sandbox profile (tests/win_harness/profile.ps1 = the Windows stub layer). Unknown flags fail loudly.
printf 'powershell' >> "$LE_T_LOG"; for a in "$@"; do printf '\t%s' "$a" >> "$LE_T_LOG"; done; printf '\n' >> "$LE_T_LOG"
while [ $# -gt 0 ]; do
  case "${1,,}" in
    -noprofile|-nologo|-noninteractive) shift ;;
    -executionpolicy|-windowstyle) [ $# -ge 2 ] || { echo "fake powershell: $1 needs a value" >&2; exit 64; }; shift 2 ;;
    -file) break ;;
    *) echo "fake powershell: unsupported flag '$1' before -File" >&2; exit 64 ;;
  esac
done
[ "${1,,}" = "-file" ] || { echo "fake powershell: no -File" >&2; exit 64; }
exec "$LE_T_PWSH" -NoLogo -File "${@:2}"
