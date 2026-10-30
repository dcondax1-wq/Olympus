#!/usr/bin/env bash
# Keep the owner's Planner app (a Home Screen app) on the published dashboard site.
# The web dashboard publish force-pushes ONE fresh commit to demetrades2000-coder/nq-dashboard main, which used to erase the
# planner/ folder every time. The planner's source lives on the public branch `planner-backup` of that repo (planner/ only);
# this copies it into the freshly built site folder BEFORE the commit, so every publish contains it.
#   bash scripts/add_planner.sh <site dir>
# Never fails the caller: if the copy is not possible the site publishes without the planner, as before.
site="${1:-site}"
tmp="$(mktemp -d 2>/dev/null || echo /tmp/planner_src)"
if git clone -q --depth 1 -b planner-backup https://github.com/demetrades2000-coder/nq-dashboard.git "$tmp/src" 2>/dev/null \
   && [ -f "$tmp/src/planner/index.html" ] && [ -f "$tmp/src/planner/sw.js" ]; then
  rm -rf "$site/planner"
  cp -r "$tmp/src/planner" "$site/planner"
  rm -rf "$site/planner/.git"
  echo "planner: added to $site ($(du -sk "$site/planner" | cut -f1) KB)"
else
  echo "planner: could not fetch planner-backup, publishing without it"
fi
rm -rf "$tmp"
exit 0
