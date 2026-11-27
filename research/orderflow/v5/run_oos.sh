#!/usr/bin/env bash
# Score every frozen v5 order-flow family on the days that are NOT in the 51 in-sample days.
# Run after tonight's data pull, from anywhere:  bash research/orderflow/v5/run_oos.sh
# Paper research only. Each family writes its own table; a failure in one does not stop the others.
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/../../.." || exit 1
PY=python; command -v "$PY" >/dev/null 2>&1 || PY=python3
LOG=research/orderflow/v5/oos_run.log
: > "$LOG"
fail=0
for fam in targets combo profile sessions delta trapped exhaustion levels; do
  echo "================ $fam ================" | tee -a "$LOG"
  if "$PY" -X utf8 "research/orderflow/v5/$fam/oos.py" 2>&1 | tee -a "$LOG"; then
    st=ok
  else
    st=FAILED; fail=$((fail+1))
  fi
  echo "---- $fam: $st" | tee -a "$LOG"
done
echo "done: $fail family run(s) failed. Full output in $LOG" | tee -a "$LOG"
exit $fail
