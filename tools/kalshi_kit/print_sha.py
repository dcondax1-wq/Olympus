"""The SHA-256 of the public script, for the owner's paste line (SETUP.md step 1 checks it and stops on a mismatch).

The site serves tools/kalshi_kit/public/kalshi_status_vm.py byte for byte (built on Linux: LF line ends), so the hash is
taken over the file with CRLF turned into LF: the same number on a Windows checkout. Run it on the merged main, after
the site published it; --live also downloads the served file and says whether it matches.

    python tools/kalshi_kit/print_sha.py            the hash and the owner's paste line
    python tools/kalshi_kit/print_sha.py --live     ... and the hash of the file the site serves now
"""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "public", "kalshi_status_vm.py")
SITE = "https://dcondax1-wq.github.io/kalshi/"
LINE = "Set up Jarvis for my Kalshi bot by following {site}SETUP.md (sha256 {sha})"


def sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def file_sha(path: str = SCRIPT) -> str:
    with open(path, "rb") as fh:
        return sha(fh.read())


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    h = file_sha()
    print(h)
    print("paste line: " + LINE.format(site=SITE, sha=h))
    if "--live" in argv:
        try:
            with urllib.request.urlopen(SITE + "kalshi_status_vm.py", timeout=30) as r:
                live = sha(r.read())
        except Exception as e:
            print(f"live: could not download it ({e.__class__.__name__})")
            return 1
        print(f"live: {live} " + ("MATCH" if live == h else "DIFFERENT (the site has not published this version yet)"))
        return 0 if live == h else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
