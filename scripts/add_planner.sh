#!/usr/bin/env bash
# Keep the owner's Planner app (a Home Screen app) on the published dashboard site.
# The web dashboard publish force-pushes ONE fresh commit to demetrades2000-coder/nq-dashboard main, which used to erase the
# planner/ folder every time. The planner's source lives on the public branch `planner-backup` of that repo (planner/ only);
# this copies it into the freshly built site folder BEFORE the commit, so every publish contains it.
#   bash scripts/add_planner.sh <site dir>
# Never fails the caller: if the copy is not possible the site publishes without the planner, as before.
#
# Planner add-ons (2026-11-01, owner: "agents working on the planner, making more features"): features built in THIS repo
# as patches on top of planner-backup (tools/planner_patches/*.patch, applied in name order, each committed in the temp
# clone so one failure never undoes another). A patch that no longer applies (planner-backup moved on and a 3-way merge
# fails) is skipped and logged: the Planner then publishes without that add-on, never half-patched.
# planner/addons.json lists what was applied and skipped. PLANNER_REPO / PLANNER_PATCHES override the source (tests).
site="${1:-site}"
root="$(cd "$(dirname "$0")/.." && pwd)"
repo="${PLANNER_REPO:-https://github.com/demetrades2000-coder/nq-dashboard.git}"
patches="${PLANNER_PATCHES:-$root/tools/planner_patches}"
tmp="$(mktemp -d 2>/dev/null || echo /tmp/planner_src)"
if git clone -q --depth 40 -b planner-backup "$repo" "$tmp/src" 2>/dev/null \
   && [ -f "$tmp/src/planner/index.html" ] && [ -f "$tmp/src/planner/sw.js" ]; then
  applied=""; skipped=""
  g() { git -C "$tmp/src" -c user.name=planner-addons -c user.email=addons@liquidity-engine.local "$@"; }
  for p in "$patches"/*.patch; do
    [ -f "$p" ] || continue
    n="$(basename "$p" .patch)"
    if g apply --check "$p" 2>/dev/null && g apply "$p" 2>/dev/null; then
      g add -A && g commit -q -m "add-on $n" && applied="$applied \"$n\","
    elif g apply --3way "$p" >/dev/null 2>&1 && [ -z "$(g diff --name-only --diff-filter=U)" ]; then
      g add -A && g commit -q -m "add-on $n (3-way)" && applied="$applied \"$n\","
    else
      g reset -q --hard && g clean -qfd
      skipped="$skipped \"$n\","
      echo "planner: add-on $n no longer applies to planner-backup, published without it"
    fi
  done
  printf '{"v":1,"applied":[%s],"skipped":[%s]}\n' "${applied%,}" "${skipped%,}" > "$tmp/src/planner/addons.json"
  rm -rf "$site/planner"
  cp -r "$tmp/src/planner" "$site/planner"
  rm -rf "$site/planner/.git"
  echo "planner: added to $site ($(du -sk "$site/planner" | cut -f1) KB; add-ons:${applied%,}${skipped:+; skipped:${skipped%,}})"
else
  echo "planner: could not fetch planner-backup, publishing without it"
fi
rm -rf "$tmp"
exit 0
