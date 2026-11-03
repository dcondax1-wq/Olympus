"""python -X utf8 -m tools.pantheon [--offline] [--out <dir>] [--no-research] [--no-web] [--fixture-json]"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.pantheon import build  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.pantheon", description="PANTHEON: the gods of free market data")
    ap.add_argument("--offline", action="store_true", help="no network: the cache, then the repo's own files")
    ap.add_argument("--fixtures", default=None, help="read recorded responses from this folder (tests)")
    ap.add_argument("--out", default=None, help="also write pantheon.json, states.json, jarvis.json here (CRONOS)")
    ap.add_argument("--no-research", action="store_true", help="do not write research/pantheon/")
    ap.add_argument("--no-web", action="store_true", help="do not write tools/web_public/pantheon/")
    ap.add_argument("--fixture-json", action="store_true", help="also refresh the page's demo copy (fixture.json)")
    a = ap.parse_args(argv)
    build.run(offline=a.offline, fixtures=a.fixtures, out=a.out, research=None if a.no_research else build.RESEARCH,
              web=None if a.no_web else build.WEB, fixture_json=a.fixture_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
