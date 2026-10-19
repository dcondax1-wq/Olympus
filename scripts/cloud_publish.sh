#!/usr/bin/env bash
# Publish the cloud monitor's output (tools/lit_watch.py calls this after a run it triggers; same commands as the
# workflow's "Publish dashboard branch" and "Publish web dashboard" steps).
#   bash scripts/cloud_publish.sh <dash dir> [all|dash]
# env: GH_TOKEN + GITHUB_REPOSITORY (dashboard branch), DASH_DEPLOY_KEY or DASH_KEY (web dashboard; skipped when unset).
# Never prints a secret; a failed push never fails the caller.
dir="${1:-dash}"
what="${2:-all}"
root="$(cd "$(dirname "$0")/.." && pwd)"
if [ -z "${GH_TOKEN:-}" ] || [ -z "${GITHUB_REPOSITORY:-}" ]; then
  echo "publish: no GH_TOKEN / GITHUB_REPOSITORY (dry run), skipped"
  exit 0
fi
(
  cd "$dir" || exit 0
  git init -q -b dashboard 2>/dev/null
  git config user.name "liquidity-engine-monitor"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add -A
  git commit -q -m "dashboard $(TZ=America/New_York date '+%Y-%m-%d %H:%M:%S ET') (watch)" || true
  git push -q -f "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" dashboard || echo "publish: dashboard push failed"
)
key="${DASH_KEY:-${DASH_DEPLOY_KEY:-}}"
if [ "$what" = "all" ] && [ -n "$key" ]; then
  (
    cd "$root" || exit 0
    python tools/build_web_dashboard.py --state "$dir/state.json" --chart "$dir/chart.png" --out site || exit 0
    mkdir -p ~/.ssh && printf '%s\n' "$key" > ~/.ssh/dash_key && chmod 600 ~/.ssh/dash_key
    ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null
    cd site || exit 0
    git init -q -b main 2>/dev/null
    git config user.name "liquidity-engine-monitor"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    git add -A
    git commit -q -m "dashboard $(TZ=America/New_York date '+%Y-%m-%d %H:%M:%S ET') (watch)" || true
    GIT_SSH_COMMAND="ssh -i ~/.ssh/dash_key -o IdentitiesOnly=yes" git push -q -f git@github.com:demetrades2000-coder/nq-dashboard.git main \
      || echo "publish: web dashboard push failed"
  )
  rm -f ~/.ssh/dash_key
fi
exit 0
