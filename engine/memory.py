"""Persistent trade memory: every completed paper / live trade (and, on request, backtest trades) in data/memory.db.

The Engine re-derives everything from bars on every run, so without this nothing learned in paper during the week
survives a restart. The memory keeps:
  trades             - one row per completed trade with its features / checklist / exit-signal log
  exit_signal_gains  - the counterfactual "what if we had left here" value of every warning sign that fired
                       (this is what the walk-forward exit learner in engine.model consumes: see Engine.run seeding)
  learner_state      - small key -> json blobs (last seed, import markers)
  notes              - the operator's notes per trade (dashboard Memory page)

Sources: 'paper' (paper / demo adapters), 'live' (real broker), 'backtest' (only with memory_write_backtest=True).
The exit learner is only ever seeded from paper + live rows, never from backtest rows.

CLI:  python -m engine.memory --import-live-state [path]   # backfill from data/live_state.json ledger as 'paper'
      python -m engine.memory --stats
      python -m engine.memory --export out.csv
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import os
import sqlite3
import sys
import threading
import time

from .data import DATA_DIR
from .instruments import INSTRUMENTS

DB_PATH = os.environ.get("LE_MEMORY_DB") or os.path.join(DATA_DIR, "memory.db")   # LE_MEMORY_DB: tests (tests/__init__.py) use a temp db
REAL_SOURCES = ("paper", "live")

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT    NOT NULL,
    sym           TEXT    NOT NULL,
    tf            TEXT,
    day           TEXT,
    entry_t       INTEGER NOT NULL,
    exit_t        INTEGER,
    dir           INTEGER NOT NULL,
    qty           INTEGER,
    entry         REAL,
    exit_price    REAL,
    stop0         REAL,
    target        REAL,
    risk_pts      REAL,
    pnl           REAL,
    pnl_r         REAL,
    mae           REAL,
    mfe           REAL,
    exit_reason   TEXT,
    exit_signal   TEXT,
    "trigger"     TEXT,
    grade         TEXT,
    grade_points  INTEGER,
    regime        TEXT,
    features_json  TEXT,
    checklist_json TEXT,
    xsig_json      TEXT,
    extra_json     TEXT,
    params_hash   TEXT,
    created_at    INTEGER NOT NULL,
    UNIQUE (source, sym, entry_t, dir)
);
CREATE INDEX IF NOT EXISTS ix_trades_source ON trades (source, exit_t);
CREATE TABLE IF NOT EXISTS exit_signal_gains (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id  INTEGER NOT NULL REFERENCES trades (id) ON DELETE CASCADE,
    signal    TEXT    NOT NULL,
    k         INTEGER,
    r_then    REAL,
    gain      REAL    NOT NULL,
    source    TEXT    NOT NULL,
    UNIQUE (trade_id, signal)
);
CREATE INDEX IF NOT EXISTS ix_gains_signal ON exit_signal_gains (source, signal);
CREATE TABLE IF NOT EXISTS learner_state (
    key        TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id   INTEGER NOT NULL REFERENCES trades (id) ON DELETE CASCADE,
    text       TEXT    NOT NULL,
    created_at INTEGER NOT NULL
);
"""

TRADE_COLS = ["source", "sym", "tf", "day", "entry_t", "exit_t", "dir", "qty", "entry", "exit_price", "stop0", "target",
              "risk_pts", "pnl", "pnl_r", "mae", "mfe", "exit_reason", "exit_signal", "trigger", "grade", "grade_points",
              "regime", "features_json", "checklist_json", "xsig_json", "extra_json", "params_hash", "created_at"]
EXTRA_KEYS = ("target_label", "pools", "conf_tags", "qty_label", "model", "score", "bars_held", "gross", "comm", "rr", "exits", "memory_note")
VOLATILE_PARAMS = {"days_from", "days_to", "live", "memory_seed", "memory_write_backtest"}


def _py(o):
    """numpy scalars / arrays / sets -> plain Python so both json and sqlite accept them."""
    if hasattr(o, "item") and not isinstance(o, (list, dict, str, bytes)):
        try:
            return o.item()
        except Exception:
            pass
    if hasattr(o, "tolist"):
        return o.tolist()
    if isinstance(o, dict):
        return {str(k): _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_py(v) for v in o]
    return o


def _num(v, cast=float):
    if v is None:
        return None
    try:
        v = _py(v)
        return cast(v)
    except Exception:
        return None


def _js(o):
    return None if o is None else json.dumps(_py(o), separators=(",", ":"), default=str)


def params_hash(params: dict | None) -> str | None:
    if not params:
        return None
    clean = {k: v for k, v in params.items() if k not in VOLATILE_PARAMS}
    return hashlib.md5(json.dumps(_py(clean), sort_keys=True, default=str).encode()).hexdigest()[:12]


def trading_day(ts) -> str | None:
    if ts is None:
        return None
    import datetime as _dt
    from zoneinfo import ZoneInfo
    return (_dt.datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York")) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")


class Memory:
    """SQLite-backed trade memory. One short-lived connection per call under a process lock: safe for the single-process
    FastAPI server plus the LiveBot thread. WAL mode so dashboard reads never block a write from the bot."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._ready = False

    # ------------------------------------------------------------------ plumbing
    @contextlib.contextmanager
    def _conn(self):
        """Locked, short-lived connection: commits on success, rolls back on error, always closes."""
        with self._lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            fresh = not os.path.exists(self.path)
            c = sqlite3.connect(self.path, timeout=15)
            try:
                c.row_factory = sqlite3.Row
                c.execute("PRAGMA foreign_keys = ON")
                if fresh or not self._ready:
                    c.execute("PRAGMA journal_mode = WAL")
                    c.executescript(SCHEMA)
                    self._ready = True
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()

    def _q(self, sql, args=()):
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def count(self, sources=None) -> int:
        if sources:
            ph = ",".join("?" * len(sources))
            r = self._q(f"SELECT COUNT(*) n FROM trades WHERE source IN ({ph})", tuple(sources))
        else:
            r = self._q("SELECT COUNT(*) n FROM trades")
        return int(r[0]["n"]) if r else 0

    # ------------------------------------------------------------------ writes
    def record_trade(self, trade: dict, source: str, sym: str, tf: str | None = None, params: dict | None = None):
        """Insert a completed engine trade. Idempotent on (source, sym, entry_t, dir): returns (trade_id, inserted)."""
        if source not in ("paper", "live", "backtest"):
            raise ValueError(f"bad source {source!r}")
        t = trade
        entry_t = _num(t.get("entry_t"), int)
        d = _num(t.get("dir"), int)
        if entry_t is None or d not in (1, -1):
            raise ValueError("trade needs entry_t and dir")
        xsig = _py(t.get("xsig") or {})
        row = {
            "source": source, "sym": sym, "tf": tf, "day": t.get("day") or trading_day(entry_t),
            "entry_t": entry_t, "exit_t": _num(t.get("exit_t"), int), "dir": d, "qty": _num(t.get("qty"), int),
            "entry": _num(t.get("entry")), "exit_price": _num(t.get("exit_price")), "stop0": _num(t.get("stop0", t.get("stop"))),
            "target": _num(t.get("target")), "risk_pts": _num(t.get("risk_pts")), "pnl": _num(t.get("pnl")), "pnl_r": _num(t.get("pnl_r")),
            "mae": _num(t.get("mae")), "mfe": _num(t.get("mfe")), "exit_reason": t.get("exit_reason"), "exit_signal": t.get("exit_signal"),
            "trigger": t.get("trigger"), "grade": t.get("grade"), "grade_points": _num(t.get("grade_points"), int), "regime": t.get("regime"),
            "features_json": _js(t.get("features")), "checklist_json": _js(t.get("checklist")), "xsig_json": _js(xsig),
            "extra_json": _js({k: t.get(k) for k in EXTRA_KEYS if k in t}), "params_hash": params_hash(params),
            "created_at": int(time.time()),
        }
        cols = ", ".join(f'"{c}"' for c in TRADE_COLS)
        ph = ", ".join("?" * len(TRADE_COLS))
        with self._conn() as c:
            cur = c.execute(f"INSERT OR IGNORE INTO trades ({cols}) VALUES ({ph})", tuple(row[k] for k in TRADE_COLS))
            inserted = cur.rowcount == 1
            tid = cur.lastrowid if inserted else c.execute(
                "SELECT id FROM trades WHERE source=? AND sym=? AND entry_t=? AND dir=?", (source, sym, entry_t, d)).fetchone()["id"]
            if inserted:
                for name, x in xsig.items():
                    if isinstance(x, dict) and x.get("gain") is not None:
                        c.execute("INSERT OR IGNORE INTO exit_signal_gains (trade_id, signal, k, r_then, gain, source) VALUES (?,?,?,?,?,?)",
                                  (tid, name, _num(x.get("k"), int), _num(x.get("r")), float(x["gain"]), source))
        return int(tid), bool(inserted)

    def add_note(self, trade_id: int, text: str) -> dict:
        text = (text or "").strip()
        with self._conn() as c:
            if not c.execute("SELECT 1 FROM trades WHERE id=?", (int(trade_id),)).fetchone():
                return {"ok": False, "error": f"no trade {trade_id}"}
            c.execute("DELETE FROM notes WHERE trade_id=?", (int(trade_id),))     # one live note per trade; empty text clears it
            if text:
                c.execute("INSERT INTO notes (trade_id, text, created_at) VALUES (?,?,?)", (int(trade_id), text[:2000], int(time.time())))
        return {"ok": True, "trade_id": int(trade_id), "text": text}

    def set_state(self, key: str, value):
        with self._conn() as c:
            c.execute("INSERT INTO learner_state (key, value_json, updated_at) VALUES (?,?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
                      (key, _js(value), int(time.time())))

    def get_state(self, key: str, default=None):
        r = self._q("SELECT value_json FROM learner_state WHERE key=?", (key,))
        return json.loads(r[0]["value_json"]) if r else default

    def states(self) -> dict:
        return {r["key"]: {"value": json.loads(r["value_json"]), "updated_at": r["updated_at"]} for r in self._q("SELECT * FROM learner_state")}

    # ------------------------------------------------------------------ reads
    @staticmethod
    def _src_clause(source):
        """source: None -> paper+live ('realised'); 'all' -> everything; str or sequence -> those."""
        if source is None:
            srcs = REAL_SOURCES
        elif source == "all":
            return "", ()
        elif isinstance(source, str):
            srcs = (source,)
        else:
            srcs = tuple(source)
        return f"WHERE t.source IN ({','.join('?' * len(srcs))})", srcs

    def recent(self, n: int = 100, source=None) -> list[dict]:
        where, args = self._src_clause(source)
        rows = self._q(f"""SELECT t.*, (SELECT text FROM notes WHERE trade_id=t.id ORDER BY id DESC LIMIT 1) AS note
                           FROM trades t {where} ORDER BY t.entry_t DESC, t.id DESC LIMIT ?""", args + (int(n),))
        out = []
        for r in rows:
            r["features"] = json.loads(r.pop("features_json") or "null")
            r["checklist"] = json.loads(r.pop("checklist_json") or "null")
            r["xsig"] = json.loads(r.pop("xsig_json") or "null")
            r.update(json.loads(r.pop("extra_json") or "{}") or {})
            out.append(r)
        return out

    def exit_gains(self, sources=REAL_SOURCES, sym: str | None = None, before: int | None = None, with_keys: bool = False):
        """{signal: [gain, ...]} in exit-time order from the given sources (never backtest unless asked).
        sym: only that instrument. before: only trades that closed strictly before this unix time (walk-forward seeding).
        with_keys also returns the set of (sym, entry_t, dir) the gains came from."""
        srcs = tuple(sources)
        if not srcs:
            return ({}, set()) if with_keys else {}
        where = [f"g.source IN ({','.join('?' * len(srcs))})"]
        args = list(srcs)
        if sym:
            where.append("t.sym = ?")
            args.append(sym)
        if before is not None:
            where.append("t.exit_t IS NOT NULL AND t.exit_t < ?")
            args.append(int(before))
        rows = self._q(f"""SELECT g.signal, g.gain, t.sym, t.entry_t, t.dir FROM exit_signal_gains g JOIN trades t ON t.id=g.trade_id
                           WHERE {' AND '.join(where)} ORDER BY t.exit_t, g.id""", tuple(args))
        gains, keys = {}, set()
        for r in rows:
            gains.setdefault(r["signal"], []).append(float(r["gain"]))
            keys.add((r["sym"], int(r["entry_t"]), int(r["dir"])))
        return (gains, keys) if with_keys else gains

    def signal_summary(self, sources=REAL_SOURCES, learn_min: int = 20, threshold: float = 0.2) -> list[dict]:
        gains = self.exit_gains(sources)
        out = []
        for name, g in gains.items():
            n = len(g)
            avg = sum(g) / n
            out.append({"key": name, "n": n, "avg_gain": round(avg, 3), "total_gain": round(sum(g), 2),
                        "helped": round(sum(1 for x in g if x > 0.1) / n, 3), "hurt": round(sum(1 for x in g if x < -0.1) / n, 3),
                        "learned": n >= learn_min and avg >= threshold, "to_go": max(0, learn_min - n)})
        out.sort(key=lambda x: -x["avg_gain"])
        return out

    @staticmethod
    def _agg(rows: list[dict]) -> dict:
        n = len(rows)
        pnl = [float(r["pnl"] or 0) for r in rows]
        rs = [float(r["pnl_r"] or 0) for r in rows]
        wins = [x for x in pnl if x > 0]
        losses = [x for x in pnl if x <= 0]
        gp, gl = sum(wins), -sum(losses)
        return {"trades": n, "wins": len(wins), "win_rate": round(len(wins) / n * 100, 1) if n else 0.0,
                "net": round(sum(pnl), 2), "avg_r": round(sum(rs) / n, 3) if n else 0.0, "total_r": round(sum(rs), 2),
                "profit_factor": round(gp / gl, 2) if gl > 0 else (999.0 if gp > 0 else 0.0),
                "expectancy": round(sum(pnl) / n, 2) if n else 0.0,
                "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0, "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
                "first_day": min((r["day"] for r in rows if r["day"]), default=None),
                "last_day": max((r["day"] for r in rows if r["day"]), default=None)}

    def stats(self, source=None, learn_min: int = 20, threshold: float = 0.2) -> dict:
        """Lifetime statistics. source None = paper+live, 'all' = everything, or a source name / list."""
        where, args = self._src_clause(source)
        rows = self._q(f"SELECT t.id, t.source, t.day, t.pnl, t.pnl_r, t.grade, t.exit_reason, t.exit_signal, t.dir, t.regime FROM trades t {where}", args)
        srcs = args or ("paper", "live", "backtest")
        by = lambda key: {k: self._agg([r for r in rows if (r[key] or "—") == k]) for k in sorted({(r[key] or "—") for r in rows})}
        return {"source": source or "realised", **self._agg(rows), "by_grade": by("grade"), "by_exit": by("exit_reason"),
                "by_regime": by("regime"), "by_dir": {("Long" if k == 1 else "Short"): self._agg([r for r in rows if r["dir"] == k]) for k in (1, -1)},
                "by_signal": self.signal_summary(srcs, learn_min, threshold)}

    def calibration(self) -> dict:
        """Per-grade realised performance (paper + live) for the dashboard to set beside the backtest's expectancy by grade."""
        return {"realised": self.stats(None)["by_grade"], "paper": self.stats("paper")["by_grade"], "live": self.stats("live")["by_grade"]}

    def export_csv(self, path: str | None = None) -> str:
        rows = self._q("""SELECT t.*, (SELECT text FROM notes WHERE trade_id=t.id ORDER BY id DESC LIMIT 1) AS note
                          FROM trades t ORDER BY t.entry_t""")
        buf = io.StringIO()
        cols = ["id", "source", "sym", "tf", "day", "entry_t", "exit_t", "dir", "qty", "entry", "exit_price", "stop0", "target", "risk_pts",
                "pnl", "pnl_r", "mae", "mfe", "exit_reason", "exit_signal", "trigger", "grade", "grade_points", "regime", "params_hash",
                "created_at", "note", "xsig_json", "features_json", "checklist_json"]
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
        text = buf.getvalue()
        if path:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        return text

    # ------------------------------------------------------------------ backfill
    def import_live_state(self, path: str | None = None, source: str = "paper") -> dict:
        """Import completed trades from a live_state.json ledger (buy/sell rows paired with their exit rows by entry_t)."""
        path = path or os.path.join(DATA_DIR, "live_state.json")
        if not os.path.exists(path):
            return {"ok": False, "error": f"{path} not found", "imported": 0}
        with open(path, encoding="utf-8") as fh:
            s = json.load(fh)
        sym, tf = s.get("sym") or "NQ", s.get("tf") or "5m"
        entries = {r.get("entry_t"): r for r in s.get("ledger") or [] if r.get("side") in ("buy", "sell") and r.get("entry_t")}
        imported, seen = 0, 0
        for r in s.get("ledger") or []:
            if r.get("side") != "exit" or not r.get("entry_t") or r.get("pnl") is None:
                continue
            e = entries.get(r["entry_t"], {})
            d = 1 if e.get("side") == "buy" else (-1 if e.get("side") == "sell" else None)
            if d is None:
                continue
            qty = e.get("qty") or r.get("qty")
            entry, stop = e.get("entry"), e.get("stop")
            risk = abs(float(entry) - float(stop)) if entry is not None and stop is not None else None
            pv = float(INSTRUMENTS.get(sym, {}).get("micro_pv", 2.0))      # engine qty is in micros
            tr = {"entry_t": r["entry_t"], "exit_t": r.get("exit_t") or r.get("t"), "dir": d, "qty": qty, "entry": entry, "stop0": stop,
                  "target": e.get("target"), "risk_pts": risk, "pnl": r.get("pnl"), "exit_reason": r.get("reason"),
                  "pnl_r": round(float(r["pnl"]) / (risk * float(qty) * pv), 3) if risk and qty else None}
            tid, ins = self.record_trade(tr, source, sym, tf)
            seen += 1
            imported += int(ins)
        self.set_state("import_live_state", {"path": path, "day": s.get("day"), "seen": seen, "imported": imported, "t": int(time.time())})
        return {"ok": True, "path": path, "day": s.get("day"), "ledger_rows": len(s.get("ledger") or []), "completed": seen, "imported": imported}


MEMORY = Memory()


def _main(argv):
    m = MEMORY
    if "--import-live-state" in argv:
        i = argv.index("--import-live-state")
        path = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else None
        r = m.import_live_state(path)
        print(json.dumps(r, indent=1))
        return 0 if r.get("ok") else 1
    if "--export" in argv:
        i = argv.index("--export")
        out = argv[i + 1] if i + 1 < len(argv) else "memory_export.csv"
        m.export_csv(out)
        print(f"wrote {out} ({m.count()} trades)")
        return 0
    st = m.stats("all")
    print(f"memory.db: {m.count()} trades ({m.count(('paper',))} paper / {m.count(('live',))} live / {m.count(('backtest',))} backtest)")
    print(json.dumps({k: st[k] for k in ("trades", "win_rate", "avg_r", "profit_factor", "net", "by_grade", "by_signal")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
