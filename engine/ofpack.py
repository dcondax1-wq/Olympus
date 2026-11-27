"""OF PACK (night-of-backfill 2026-11-27): the order-flow summaries of many tick days in ONE small, lossless, verified blob, so one
ntfy attachment (<= 1.85 MB, engine/datafeed) carries about twice the days a gzip page does.

Why: ntfy.sh's free tier counts MESSAGES (250 a UTC day per IP, measured GET /v1/account 2026-11-27: messages 250, attachment
2 MiB a file, 20 MiB in flight, kept 3 h, 350 MiB bandwidth a day) and the PC's status + alerts already use ~210-230 of them on a
weekday. Each page is one message, so more days per page = more of the year per night.

How (stdlib only: gzip, lzma, json, hashlib):
  every .gz file is gunzipped; a CSV (header + plain comma rows, engine/ofsum's NQ_bars5m / NQ_fp5m / NQ_depth5m) is split into
  its columns; an integer column (bar index, price level, volume) is stored as deltas, a plain decimal column (prices) as
  fixed-point deltas, anything else as its text; every column is decoded again HERE and must give back the same tokens, else that
  column stays text (lossless by construction). All files of the page then go through ONE xz stream (preset 6e: days repeat the
  same structure, so a solid stream beats one gzip per file).
  The page lists every file's sha256 + size of the ORIGINAL uncompressed content; unpack() checks each one and rebuilds the same
  file names (.gz files gzipped again with mtime 0: same content, the cloud's readers read the content). A broken / foreign /
  oversize blob raises ValueError and nothing is returned.
Measured 2026-11-27 on the 53 REAL tick-summary days (branch of-days): gzip 7,045,000 B -> 2,597,184 B = 0.37, lossless:
~38 days a 1.85 MB page instead of ~14 (synthetic days: ~0.53). Every page's meta carries its real ratio ("ratio").

    python -X utf8 -m engine.ofpack selftest
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import lzma
import re
import sys

MAGIC = b"OFP1"
MAX_FILE = 30_000_000          # one unpacked file (same guard as engine/datafeed.MAX_UNPACKED)
MAX_TOTAL = 400_000_000        # the whole unpacked page (xz bomb guard)
_INT = re.compile(rb"^-?(?:0|[1-9][0-9]*)$")
_DEC = re.compile(rb"^-?(?:0|[1-9][0-9]*)\.[0-9]{1,8}$")
_PATH = re.compile(r"^[A-Za-z0-9_./-]{1,200}$")


# ------------------------------------------------------------------------------------------------ one column
def _enc_int(tok: list) -> bytes:
    prev, out = 0, []
    for t in tok:
        v = int(t)
        out.append(str(v - prev))
        prev = v
    return "\n".join(out).encode("ascii")


def _dec_int(b: bytes, n: int) -> list:
    if n == 0:
        return []
    prev, out = 0, []
    for d in b.split(b"\n"):
        prev += int(d)
        out.append(str(prev).encode("ascii"))
    return out


def _enc_dec(tok: list) -> bytes:
    """Fixed point: each token = digits without the dot + its own number of decimals (one stream each, deltas on the digits)."""
    ints, fr = [], []
    for t in tok:
        neg = t.startswith(b"-")
        a, b = t.lstrip(b"-").split(b".")
        v = int(a + b)
        ints.append(-v if neg else v)
        fr.append(str(len(b)) if not (neg and v == 0) else "n" + str(len(b)))   # "-0.0": its sign kept apart
    prev, d = 0, []
    for v in ints:
        d.append(str(v - prev))
        prev = v
    return ("\n".join(d) + "\x00" + "\n".join(fr)).encode("ascii")


def _dec_dec(b: bytes, n: int) -> list:
    if n == 0:
        return []
    d, fr = b.split(b"\x00")
    prev, out = 0, []
    for dd, f in zip(d.split(b"\n"), fr.split(b"\n")):
        prev += int(dd)
        neg0 = f.startswith(b"n")
        k = int(f[1:] if neg0 else f)
        s = str(abs(prev)).rjust(k + 1, "0")
        txt = s[:-k] + "." + s[-k:]
        out.append((("-" if prev < 0 or neg0 else "") + txt).encode("ascii"))
    return out


def _enc_col(tok: list) -> tuple:
    """(kind, bytes): 'i' int deltas, 'f' fixed-point deltas, 't' text. Verified by decoding (else 't')."""
    n = len(tok)
    if n and all(_INT.match(t) for t in tok):
        b = _enc_int(tok)
        if _dec_int(b, n) == tok:
            return "i", b
    if n and all(_DEC.match(t) for t in tok):
        b = _enc_dec(tok)
        if _dec_dec(b, n) == tok:
            return "f", b
    return "t", b"\n".join(tok)


def _dec_col(kind: str, b: bytes, n: int) -> list:
    if kind == "i":
        return _dec_int(b, n)
    if kind == "f":
        return _dec_dec(b, n)
    return b.split(b"\n") if n else []


# ------------------------------------------------------------------------------------------------ one CSV
def enc_csv(raw: bytes) -> tuple | None:
    """raw CSV -> (meta, [column streams]) or None when it is not a plain CSV (then it travels as text). Lossless: checked."""
    try:
        if b"\r" in raw or b'"' in raw or not raw.endswith(b"\n"):
            return None
        lines = raw[:-1].split(b"\n")
        if len(lines) < 2:
            return None
        header, rows = lines[0], lines[1:]
        nc = header.count(b",") + 1
        cols = [[] for _ in range(nc)]
        for r in rows:
            f = r.split(b",")
            if len(f) != nc:
                return None
            for i, v in enumerate(f):
                cols[i].append(v)
        kinds, streams = [], []
        for c in cols:
            k, b = _enc_col(c)
            kinds.append(k)
            streams.append(b)
        meta = {"h": header.decode("utf-8"), "n": len(rows), "k": "".join(kinds), "l": [len(s) for s in streams]}
        if dec_csv(meta, b"".join(streams)) != raw:
            return None
        return meta, streams
    except Exception:  # noqa: BLE001
        return None


def dec_csv(meta: dict, body: bytes) -> bytes:
    n, kinds, lens = int(meta["n"]), str(meta["k"]), [int(x) for x in meta["l"]]
    if len(kinds) != len(lens) or sum(lens) != len(body):
        raise ValueError("column sizes do not add up")
    cols, at = [], 0
    for k, ln in zip(kinds, lens):
        c = _dec_col(k, body[at:at + ln], n)
        at += ln
        if len(c) != n:
            raise ValueError("a column has the wrong row count")
        cols.append(c)
    out = [str(meta["h"]).encode("utf-8")]
    out.extend(b",".join(r) for r in zip(*cols)) if cols else None
    return b"\n".join(out) + b"\n"


# ------------------------------------------------------------------------------------------------ the page
def pack(files: dict) -> bytes:
    """{path: file bytes as on disk} -> one blob (MAGIC + xz). Paths are kept as given (e.g. days/2026-10-01/of/NQ_fp5m.csv.gz)."""
    entries, body = [], []
    for p in sorted(files):
        if not _PATH.match(p) or ".." in p:
            raise ValueError(f"bad path {p!r}")
        b = files[p]
        gz = p.endswith(".gz")
        raw = gzip.decompress(b) if gz else b
        e = {"p": p, "gz": gz, "sha": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
        enc = enc_csv(raw) if (p.endswith(".csv.gz") or p.endswith(".csv")) else None
        if enc:
            m, streams = enc
            e.update(enc="col", col=m)
            chunk = b"".join(streams)
        else:
            e["enc"] = "raw"
            chunk = raw
        e["len"] = len(chunk)
        entries.append(e)
        body.append(chunk)
    head = json.dumps({"v": 1, "files": entries}, separators=(",", ":")).encode("utf-8")
    inner = len(head).to_bytes(4, "big") + head + b"".join(body)
    return MAGIC + lzma.compress(inner, format=lzma.FORMAT_XZ, preset=6 | lzma.PRESET_EXTREME)   # ~94 MB RAM (9e: ~670 MB beside NinjaTrader), same size


def _inflate(blob: bytes) -> bytes:
    if not isinstance(blob, (bytes, bytearray)) or not blob.startswith(MAGIC):
        raise ValueError("not an OF pack")
    d = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    try:
        out = d.decompress(bytes(blob[len(MAGIC):]), max_length=MAX_TOTAL + 1)
    except lzma.LZMAError as e:
        raise ValueError(f"broken xz: {e}") from None
    if len(out) > MAX_TOTAL or not d.eof:
        raise ValueError("pack too large or cut short")
    return out


def unpack(blob: bytes) -> dict:
    """blob -> {path: file bytes} (each original content sha256-checked; .gz paths gzipped again). Raises ValueError."""
    inner = _inflate(blob)
    hl = int.from_bytes(inner[:4], "big")
    try:
        head = json.loads(inner[4:4 + hl].decode("utf-8"))
    except ValueError:
        raise ValueError("bad pack header") from None
    at, out = 4 + hl, {}
    for e in head.get("files") or []:
        p = str(e.get("p") or "")
        if not _PATH.match(p) or ".." in p or p in out:
            raise ValueError(f"bad path {p!r}")
        ln = int(e.get("len") or 0)
        chunk = inner[at:at + ln]
        at += ln
        if len(chunk) != ln:
            raise ValueError("pack cut short")
        raw = dec_csv(e["col"], chunk) if e.get("enc") == "col" else chunk
        if len(raw) > MAX_FILE or len(raw) != int(e.get("size") or -1) or hashlib.sha256(raw).hexdigest() != e.get("sha"):
            raise ValueError(f"{p}: content check failed")
        out[p] = gzip.compress(raw, compresslevel=6, mtime=0) if e.get("gz") else raw
    if at != len(inner):
        raise ValueError("extra bytes in the pack")
    return out


def contents(blob: bytes) -> dict:
    """{path: original uncompressed content} (for checks / tests)."""
    return {p: (gzip.decompress(b) if p.endswith(".gz") else b) for p, b in unpack(blob).items()}


# ------------------------------------------------------------------------------------------------ selftest
def selftest() -> bool:
    import random
    rnd = random.Random(7)
    rows = ["t,o,h,l,c,vol,x,s"]
    px = 25000.0
    for i in range(300):
        px += rnd.choice((-0.25, 0, 0.25, 0.5))
        rows.append(f"{1793595600 + 300 * i},{px:.2f},{px + 1.25},{px - 0.5},{px:.1f},{rnd.randint(0, 9000)},,{rnd.random():.4f}")
    rows.append("-5,-0.0,-0.25,0.0,1e5,007,a b,NaN")
    csv = ("\n".join(rows) + "\n").encode()
    files = {"days/2026-10-01/of/NQ_bars5m.csv.gz": gzip.compress(csv), "days/2026-10-01/of/NQ_meta.json": b'{"v":1}',
             "days/2026-10-01/of/odd.csv.gz": gzip.compress(b"a,b\n1,\"x,y\"\n")}
    blob = pack(files)
    back = contents(blob)
    ok = back["days/2026-10-01/of/NQ_bars5m.csv.gz"] == csv and back["days/2026-10-01/of/NQ_meta.json"] == b'{"v":1}' \
        and back["days/2026-10-01/of/odd.csv.gz"] == b"a,b\n1,\"x,y\"\n"
    bad = bytearray(blob)
    bad[-30] ^= 0xFF
    try:
        unpack(bytes(bad))
        ok = False
    except ValueError:
        pass
    print("ofpack selftest", "OK" if ok else "FAILED", f"({len(blob)} B for {sum(len(v) for v in files.values())} B gz)")
    return ok


if __name__ == "__main__":
    if sys.argv[1:2] == ["selftest"]:
        sys.exit(0 if selftest() else 1)
    print(__doc__)
