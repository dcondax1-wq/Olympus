// LE_TickRec - READ-ONLY tick recorder for NinjaTrader 8 (NinjaScript AddOn, day-orderflow 2026-11-23). RED-TEAM FIRST.
//
// Writes every trade (Last) of NQ / ES with its size and the bid / ask in force at that moment, for order-flow research:
//     Documents\NinjaTrader 8\le_ticks\<ROOT>_<YYYY-MM-DD>.csv     header t_ms,price,size,bid,ask   (t_ms = UTC milliseconds,
//                                                                  file date = US Eastern calendar date of the trade)
//     Documents\NinjaTrader 8\le_ticks\le_tickrec_status.txt       one line every 15 s: time,on=0|1,instruments=..,rows=N
// Python (engine/tickrec.py ingest) turns the CSVs into data/ticks/YYYY-MM-DD.parquet and computes the aggressor side.
//
// OFF UNLESS ENABLED: records only while le_ticks\enabled.txt exists (`python -m engine.tickrec enable` writes it, `disable`
// deletes it; checked every 15 s). Instruments: le_ticks\instruments.txt, one NinjaTrader name per line ("NQ 12-26").
//
// READ-ONLY: no Account, no Order, no ATI file: it never places, changes or cancels an order and never touches incoming\.
// Every NinjaTrader call sits in try/catch. Buffered: lines are appended once a second, so no disk write per tick.
// C# 5 syntax only (no $"..." strings, no ?., no => members), same as LE_Feed.cs.
//
// IMPORTANT before installing: a NinjaScript file that does not compile blocks F5 for ALL scripts (LE_Feed included).
// Install it only after review, on a quiet evening: copy to Documents\NinjaTrader 8\bin\Custom\AddOns\, NinjaScript Editor, F5.
// If F5 shows a red error in this file: delete the file from AddOns\ and press F5 again; nothing else changes.
//
// BACKFILL (day-ofprogram 2026-11-23, zero clicks): while enabled, the add-on also asks NinjaTrader's historical data server for
// past TICKS of each root (front contract of that date, e.g. "NQ 09-26"), one ET calendar day at a time, newest first, back to
// 365 days or until the server has stopped giving data (7 weekdays in a row empty). Same BarsRequest API LE_Feed.cs uses,
// with BarsPeriodType.Tick / Value 1. Each day is written whole to le_ticks\bf_<ROOT>_<YYYY-MM-DD>.csv (same columns), via a
// .tmp file and a rename, so a half-written day never looks finished. A day is skipped when bf_..csv, bf_..done (Python has
// ingested it and deleted the csv) or bf_..none (the server had no ticks) exists; bf_<ROOT>_end.txt remembers where the
// server's history ended, so later passes never go older than that (delete it to probe again).
//   When: a pass starts when the flag file appears (enable) and every day at 17:15 ET; requests go out only OUTSIDE
//   02:00-16:05 ET on weekdays (the bot trades then), any time on Saturday / Sunday. One request at a time, 5 s apart;
//   a request that takes over 10 min is dropped and retried on the next pass.
//   Disk guard: nothing is written (live or backfill) while the le_ticks drive has under 10 GB free.
//   Status line adds: backfill=idle|running|waiting_window|low_disk|done,backfill_days=N,oldest=YYYY-MM-DD,bf_errors=N.
//
// UNVERIFIED (written without NinjaTrader; same API surface as LE_Feed.cs plus three fields):
//  1. MarketDataEventArgs.Volume (long), .Bid and .Ask (double: the best bid / ask when the Last event fires). If Bid / Ask
//     are 0 the recorder falls back to the last Bid / Ask events it saw; Python then uses the tick rule.
//  2. MarketDataEventArgs.Time in NinjaTrader's display time zone (same assumption as LE_Feed.SafeMarketData).
//  3. Backfill: a Tick BarsRequest returns one bar per trade (GetClose = price, GetVolume = size, GetTime = trade time in the
//     display time zone) and Bars.GetBid(i) / GetAsk(i) give the quote at that trade (NT8 Help: Bars.GetBid / GetAsk). If
//     they come back 0 Python falls back to the tick rule. How far back the server goes and whether it serves expired
//     contracts ("NQ 09-25") through Instrument.GetInstrument are NinjaTrader's choice: the add-on simply stops where it ends.
// DAY-OFMAX (2026-11-25):
//  * ROLL FIX: the backfill asked for the front contract of each date; at the September 2026 roll the expired "NQ 09-26" came back
//    unknown / empty and those days counted toward "7 empty weekdays = end of history", so every pass stopped at 2026-09-14.
//    Now an UNKNOWN contract never counts toward the end (it is marked and skipped); an empty answer first tries the other
//    quarterly contract alive that day (the expiring one in its last week); the end marker is bf_<ROOT>_end2.txt (the old
//    bf_<ROOT>_end.txt is ignored) and an old-format .none (before this version) is asked once more. Status adds bf_unknown=N.
//  * DEPTH (market depth, forward only: NinjaTrader keeps no depth history): for the roots in le_ticks\depth.txt (default NQ;
//    le_ticks\depth_off.txt turns it off) the add-on subscribes NinjaTrader's MarketDepth for the recorded contract and writes
//    the top 10 levels each side, ON CHANGE, at most 4 snapshots a second, to le_ticks\depth\<ROOT>_<YYYY-MM-DD>.csv:
//        t_ms,bp,bd1..bd10,bs1..bs10,ad1..ad10,as1..as10
//    bp = best bid price; bdN / adN = ticks below / above bp of bid / ask level N; bsN / asN = size at that level (0 = no level).
//    Every MarketDepth call goes through REFLECTION (type found by name, event bound with Delegate.CreateDelegate): if this
//    NinjaTrader build has other member names, depth is simply "unavailable" in the status line and the add-on still COMPILES
//    (a compile error would block F5 for every script). Status adds depth=on|off|unavailable,depth_rows=N.
#region Using declarations
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    public class LE_TickRec : AddOnBase
    {
        private static readonly object RunLock = new object();
        private static LE_TickRec running;
        private static readonly long EpochTicks = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc).Ticks;

        private class RecInst
        {
            public LE_TickRec Rec;
            public string Name;
            public string Root;
            public MarketData Md;
            public double Bid;
            public double Ask;
            public void OnMarketData(object sender, MarketDataEventArgs e)
            {
                Rec.SafeTick(this, e);
            }
            // depth (day-ofmax): all through reflection, see the header
            public object DepthObj;
            public System.Reflection.EventInfo DepthEvent;
            public Delegate DepthHandler;
            public double TickSize = 0.25;
            public DateTime LastSnap = DateTime.MinValue;
            public bool DepthDirty;
            public string LastBook = "";
            public readonly object DepthLock = new object();
            public void OnDepthRaw(object sender, EventArgs e)
            {
                Rec.SafeDepth(this, false);
            }
        }

        private readonly object BufLock = new object();
        private readonly Dictionary<string, StringBuilder> buf = new Dictionary<string, StringBuilder>();   // file path -> lines
        private readonly List<RecInst> insts = new List<RecInst>();
        private string folder;
        private string flagPath;
        private string listPath;
        private string statusPath;
        private System.Threading.Timer flushTimer;
        private System.Threading.Timer checkTimer;
        private bool started;
        private volatile bool terminated;
        private volatile bool on;
        private long rows;
        private TimeZoneInfo eastern;
        private volatile bool lowDisk;

        // ---------------------------------------------------------------- backfill state (all touched under BfLock)
        private static long MinFreeBytes = 10L * 1024 * 1024 * 1024;           // 10 GB free-disk guard
        private static Func<DateTime> UtcNow = delegate { return DateTime.UtcNow; };   // the clock (a test driver swaps it)
        private const int BfMaxDays = 365;
        private const int BfEmptyStop = 7;                                      // weekdays in a row with no ticks = end of history
        private readonly object BfLock = new object();
        private readonly object InstLock = new object();                        // Subscribe / Unsubscribe: the 15 s timer vs Stop
        private bool bfPass;
        private DateTime bfCursor;                                              // ET date being worked on
        private DateTime bfLastPassDay = DateTime.MinValue;
        private DateTime bfLastSent = DateTime.MinValue;
        private BarsRequest bfReq;
        private DateTime bfReqStarted;
        private string bfReqRoot;
        private DateTime bfReqDay;
        private readonly Dictionary<string, int> bfEmpty = new Dictionary<string, int>();
        private readonly Dictionary<string, DateTime> bfEnd = new Dictionary<string, DateTime>();   // root -> server history ends here
        private string bfState = "idle";
        private bool bfWriting;                                                 // SafeBackfilled is reading the Bars: never dispose them
        private int bfErrors;
        private int bfUnknown;                                                  // days whose contract NinjaTrader did not know
        private int bfReqTry;                                                   // 0 = first contract of the day, 1 = the other one
        private string bfReqName = "";
        // depth (day-ofmax)
        private const int DepthLevels = 10;
        private const int DepthMinMs = 250;                                     // at most 4 snapshots a second per instrument
        private string depthState = "off";
        private long depthRows;
        private static Type depthType;                                          // NinjaTrader.Data.MarketDepth`1[MarketDepthRow]
        private static bool depthLooked;

        protected override void OnStateChange()
        {
            try
            {
                if (State == State.SetDefaults)
                {
                    Name = "LE_TickRec";
                    Description = "Liquidity Engine tick recorder: writes NQ/ES trades with bid/ask to Documents\\NinjaTrader 8\\le_ticks while le_ticks\\enabled.txt exists. Read-only.";
                }
                else if (State == State.Active)
                {
                    Start();
                }
                else if (State == State.Terminated)
                {
                    Stop();
                }
            }
            catch (Exception)
            {
            }
        }

        protected override void OnWindowCreated(System.Windows.Window window)
        {
            try
            {
                if (!terminated)
                    Start();
            }
            catch (Exception)
            {
            }
        }

        private void Start()
        {
            lock (RunLock)
            {
                if (started || terminated)
                    return;
                if (running != null && running != this)
                    return;
                running = this;
                started = true;
            }
            try
            {
                eastern = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            }
            catch (Exception)
            {
                try { eastern = TimeZoneInfo.FindSystemTimeZoneById("America/New_York"); } catch (Exception) { eastern = TimeZoneInfo.Utc; }
            }
            folder = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "le_ticks");
            try
            {
                Directory.CreateDirectory(folder);
            }
            catch (Exception)
            {
                return;
            }
            flagPath = Path.Combine(folder, "enabled.txt");
            listPath = Path.Combine(folder, "instruments.txt");
            statusPath = Path.Combine(folder, "le_tickrec_status.txt");
            checkTimer = new System.Threading.Timer(Check, null, 2000, 15000);
            flushTimer = new System.Threading.Timer(Flush, null, 1000, 1000);
        }

        private void Stop()
        {
            terminated = true;
            try { if (checkTimer != null) checkTimer.Dispose(); } catch (Exception) { }
            try { if (flushTimer != null) flushTimer.Dispose(); } catch (Exception) { }
            Unsubscribe();
            lock (BfLock)
            {
                DropRequest();
            }
            Flush(null);
            lock (RunLock)
            {
                if (running == this)
                    running = null;
            }
        }

        // every 15 s: on/off from the flag file, (re)subscribe when the instrument list changes, status line
        private string listText = "";
        private void Check(object state)
        {
            try
            {
                if (terminated)
                    return;
                bool want = File.Exists(flagPath);
                string lt = "";
                if (want && File.Exists(listPath))
                    lt = File.ReadAllText(listPath).Trim();
                if (want && lt.Length == 0)
                    lt = "NQ 12-26\nES 12-26";
                if (!want && on)
                {
                    Unsubscribe();
                    on = false;
                }
                else if (want && (!on || lt != listText) && !terminated)
                {
                    bool wasOn = on;
                    Unsubscribe();
                    listText = lt;
                    Subscribe(lt);
                    on = true;
                    if (!wasOn)
                        StartPass();                                            // enable = start a backfill pass
                }
                lowDisk = FreeBytes() < MinFreeBytes;
                if (on)
                    BackfillStep();
                string names = "";
                lock (InstLock)
                {
                    foreach (RecInst i in insts)
                        names += (names.Length > 0 ? ";" : "") + i.Name;
                }
                File.WriteAllText(statusPath, DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture)
                    + ",on=" + (on ? "1" : "0") + ",instruments=" + names + ",rows=" + rows.ToString(CultureInfo.InvariantCulture)
                    + BackfillStatus() + "\n");
            }
            catch (Exception)
            {
            }
        }

        private void Subscribe(string lt)
        {
            lock (InstLock)
                SubscribeLocked(lt);
        }

        private void SubscribeLocked(string lt)
        {
            foreach (string raw in lt.Split('\n'))
            {
                string n = raw.Trim();
                if (n.Length == 0)
                    continue;
                try
                {
                    NinjaTrader.Cbi.Instrument ins = NinjaTrader.Cbi.Instrument.GetInstrument(n);
                    if (ins == null)
                        continue;
                    RecInst i = new RecInst();
                    i.Rec = this;
                    i.Name = n;
                    i.Root = n.Split(' ')[0].ToUpperInvariant();
                    i.Md = new MarketData(ins);
                    i.Md.Update += i.OnMarketData;
                    insts.Add(i);
                    if (DepthWanted(i.Root))
                        DepthSubscribe(i, ins);
                }
                catch (Exception)
                {
                }
            }
        }

        private void Unsubscribe()
        {
            lock (InstLock)
                UnsubscribeLocked();
        }

        private void UnsubscribeLocked()
        {
            foreach (RecInst i in insts)
            {
                try
                {
                    if (i.Md != null)
                    {
                        i.Md.Update -= i.OnMarketData;
                        IDisposable d = i.Md as IDisposable;
                        if (d != null)
                            d.Dispose();
                    }
                    DepthUnsubscribe(i);
                }
                catch (Exception)
                {
                }
            }
            insts.Clear();
        }

        private void SafeTick(RecInst i, MarketDataEventArgs e)
        {
            try
            {
                if (!on || terminated)
                    return;
                if (e.MarketDataType == MarketDataType.Bid) { i.Bid = e.Price; return; }
                if (e.MarketDataType == MarketDataType.Ask) { i.Ask = e.Price; return; }
                if (e.MarketDataType != MarketDataType.Last || e.Volume <= 0)
                    return;
                double bid = e.Bid > 0 ? e.Bid : i.Bid;
                double ask = e.Ask > 0 ? e.Ask : i.Ask;
                DateTime utc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(e.Time, DateTimeKind.Unspecified),
                                                             NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);
                long ms = (utc.Ticks - EpochTicks) / TimeSpan.TicksPerMillisecond;
                string day = TimeZoneInfo.ConvertTimeFromUtc(utc, eastern).ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
                string path = Path.Combine(folder, i.Root + "_" + day + ".csv");
                string line = ms.ToString(CultureInfo.InvariantCulture) + "," + e.Price.ToString("0.########", CultureInfo.InvariantCulture)
                    + "," + e.Volume.ToString(CultureInfo.InvariantCulture) + "," + bid.ToString("0.########", CultureInfo.InvariantCulture)
                    + "," + ask.ToString("0.########", CultureInfo.InvariantCulture) + "\n";
                lock (BufLock)
                {
                    StringBuilder sb;
                    if (!buf.TryGetValue(path, out sb))
                    {
                        sb = new StringBuilder();
                        buf[path] = sb;
                    }
                    sb.Append(line);
                    rows++;
                }
            }
            catch (Exception)
            {
            }
        }

        // ================================================================================================ backfill
        private long FreeBytes()
        {
            try
            {
                return new DriveInfo(Path.GetPathRoot(Path.GetFullPath(folder))).AvailableFreeSpace;
            }
            catch (Exception)
            {
                return long.MaxValue;                                           // unknown drive: never block on the guard alone
            }
        }

        private DateTime EtNow()
        {
            return TimeZoneInfo.ConvertTimeFromUtc(UtcNow(), eastern);
        }

        // requests may go out: weekdays outside 02:00-16:05 ET, any time on Saturday / Sunday
        public static bool InWindow(DateTime et)
        {
            if (et.DayOfWeek == DayOfWeek.Saturday || et.DayOfWeek == DayOfWeek.Sunday)
                return true;
            int m = et.Hour * 60 + et.Minute;
            return m < 120 || m >= 16 * 60 + 5;
        }

        // a NEW request only until 01:40 ET on a weekday (red team 2026-11-23): a request may take up to 10 min and its whole day
        // is then written, so all of it ends before 02:00 ET, when the bot trades
        public static bool SendWindow(DateTime et)
        {
            if (!InWindow(et))
                return false;
            if (et.DayOfWeek == DayOfWeek.Saturday || et.DayOfWeek == DayOfWeek.Sunday)
                return true;
            int m = et.Hour * 60 + et.Minute;
            return !(m >= 100 && m < 120);
        }

        // NinjaTrader name of the front quarterly contract on an ET date ("NQ 12-26"); rolls 8 days before the 3rd Friday
        // (the same rule as engine/tickrec.front_names)
        public static string FrontName(string root, DateTime d)
        {
            int y = d.Year, m = d.Month;
            for (int k = 0; k < 5; k++)
            {
                if (m % 3 == 0)
                {
                    DateTime first = new DateTime(y, m, 1);
                    DateTime fri3 = first.AddDays(((int)DayOfWeek.Friday - (int)first.DayOfWeek + 7) % 7 + 14);
                    if (d.Date <= fri3.AddDays(-8))
                        break;
                }
                if (m == 12) { m = 1; y++; } else m++;
            }
            return root + " " + m.ToString("00", CultureInfo.InvariantCulture) + "-" + (y % 100).ToString("00", CultureInfo.InvariantCulture);
        }

        private string BfBase(string root, DateTime day)
        {
            return Path.Combine(folder, "bf_" + root + "_" + day.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
        }

        private bool BfHave(string root, DateTime day)
        {
            string b = BfBase(root, day);
            if (File.Exists(b + ".csv") || File.Exists(b + ".done"))
                return true;
            try
            {
                return File.Exists(b + ".none") && File.ReadAllText(b + ".none").StartsWith("v2 ");     // older .none: ask once more
            }
            catch (Exception)
            {
                return false;
            }
        }

        private List<string> Roots()
        {
            List<string> r = new List<string>();
            foreach (string raw in listText.Split('\n'))
            {
                string n = raw.Trim();
                if (n.Length == 0)
                    continue;
                string root = n.Split(' ')[0].ToUpperInvariant();
                if (!r.Contains(root))
                    r.Add(root);
            }
            return r;
        }

        private void StartPass()
        {
            lock (BfLock)
            {
                DateTime et = EtNow();
                bfPass = true;
                bfCursor = et.Date.AddDays(-1);
                bfLastPassDay = et.Date;
                bfEmpty.Clear();
                bfEnd.Clear();
                foreach (string root in Roots())                                // bf_<ROOT>_end.txt: where an earlier pass found the end
                {
                    try
                    {
                        string p = Path.Combine(folder, "bf_" + root + "_end2.txt");   // day-ofmax: end.txt (roll bug) ignored
                        if (File.Exists(p))
                            bfEnd[root] = DateTime.ParseExact(File.ReadAllText(p).Trim().Substring(0, 10), "yyyy-MM-dd", CultureInfo.InvariantCulture);
                    }
                    catch (Exception)
                    {
                    }
                }
                bfState = "running";
            }
        }

        private void DropRequest()
        {
            if (bfReq == null || bfWriting)
                return;                                                         // writing: SafeBackfilled drops it once done
            try { bfReq.Dispose(); } catch (Exception) { }
            bfReq = null;
        }

        // every 15 s (from Check, while on): start the nightly pass, then at most one request in flight
        private void BackfillStep()
        {
            DateTime et = EtNow();
            if (et.Hour * 60 + et.Minute >= 17 * 60 + 15 && bfLastPassDay != et.Date)
                StartPass();
            lock (BfLock)
            {
                if (bfReq != null)
                {
                    if (!bfWriting && (UtcNow() - bfReqStarted).TotalMinutes > 10)
                    {
                        DropRequest();                                          // stuck: forget it, a later pass retries the day
                        bfErrors++;
                        bfCursor = bfCursor.AddDays(-1);
                    }
                    return;
                }
                if (!bfPass)
                    return;
                if (!SendWindow(et)) { bfState = "waiting_window"; return; }
                if (lowDisk) { bfState = "low_disk"; return; }
                if ((UtcNow() - bfLastSent).TotalSeconds < 5)
                    return;
                bfState = "running";
                List<string> roots = Roots();
                DateTime stop = bfLastPassDay.AddDays(-BfMaxDays);
                for (int guard = 0; guard < 2 * BfMaxDays && bfCursor >= stop; guard++)
                {
                    if (bfCursor.DayOfWeek != DayOfWeek.Saturday)
                    {
                        foreach (string root in roots)
                        {
                            int e;
                            DateTime end;
                            if (bfEmpty.TryGetValue(root, out e) && e >= BfEmptyStop)
                                continue;                                       // this root's history has ended
                            if (bfEnd.TryGetValue(root, out end) && bfCursor <= end)
                                continue;                                       // ... found on an earlier pass
                            if (BfHave(root, bfCursor))
                                continue;
                            if (Send(root, bfCursor, 0))
                                return;                                         // a request went out (or failed): next tick
                            continue;                                           // unknown contract: marked, try the next day now
                        }
                    }
                    bfCursor = bfCursor.AddDays(-1);
                }
                bfPass = false;
                bfState = "done";
            }
        }

        // called under BfLock
        // tryIx = which of Candidates(root, day) to ask
        private bool Send(string root, DateTime day, int tryIx)
        {
            List<string> cands = Candidates(root, day);
            NinjaTrader.Cbi.Instrument ins = null;
            string name = "";
            while (tryIx < cands.Count && ins == null)
            {
                name = cands[tryIx];
                try { ins = NinjaTrader.Cbi.Instrument.GetInstrument(name); } catch (Exception) { }
                if (ins == null)
                    tryIx++;
            }
            bfLastSent = UtcNow();
            if (ins == null)
            {
                Unknown(root, day, cands[0]);                                    // NinjaTrader knows none of them: skip, not "end"
                return false;
            }
            bfReqTry = tryIx;
            bfReqName = name;
            TimeZoneInfo disp = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo;
            DateTime fromUtc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(day, DateTimeKind.Unspecified), eastern);
            DateTime toUtc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(day.AddDays(1), DateTimeKind.Unspecified), eastern);
            BarsRequest req;
            try
            {
                req = new BarsRequest(ins, TimeZoneInfo.ConvertTimeFromUtc(fromUtc, disp), TimeZoneInfo.ConvertTimeFromUtc(toUtc, disp));
                BarsPeriod bp = new BarsPeriod();
                bp.BarsPeriodType = BarsPeriodType.Tick;
                bp.Value = 1;
                req.BarsPeriod = bp;
            }
            catch (Exception)
            {
                bfErrors++;
                bfCursor = bfCursor.AddDays(-1);
                return true;
            }
            bfReq = req;
            bfReqStarted = UtcNow();
            bfReqRoot = root;
            bfReqDay = day;
            try
            {
                req.Request(new Action<BarsRequest, ErrorCode, string>(delegate(BarsRequest b, ErrorCode code, string msg)
                {
                    SafeBackfilled(req, b, code);
                }));
            }
            catch (Exception)
            {
                bfReq = null;
                bfErrors++;
                bfCursor = bfCursor.AddDays(-1);
            }
            return true;
        }

        // the contracts to try for a day: the front one, then (in the expiring contract's last 8 days) the expiring one
        public static List<string> Candidates(string root, DateTime d)
        {
            List<string> c = new List<string>();
            c.Add(FrontName(root, d));
            string exp = FrontName(root, d.AddDays(-9));                         // 9 days earlier the front was still the old one
            if (!c.Contains(exp) && ExpiryOf(exp) >= d.Date)
                c.Add(exp);
            return c;
        }

        public static DateTime ExpiryOf(string name)
        {
            try
            {
                string mmyy = name.Split(' ')[1];
                int m = int.Parse(mmyy.Substring(0, 2), CultureInfo.InvariantCulture);
                int y = 2000 + int.Parse(mmyy.Substring(3, 2), CultureInfo.InvariantCulture);
                DateTime first = new DateTime(y, m, 1);
                return first.AddDays(((int)DayOfWeek.Friday - (int)first.DayOfWeek + 7) % 7 + 14);
            }
            catch (Exception)
            {
                return DateTime.MinValue;
            }
        }

        // a day whose contract NinjaTrader does not know: marked, NEVER counted toward the end of history (the roll bug)
        private void Unknown(string root, DateTime day, string name)
        {
            bfUnknown++;
            try { File.WriteAllText(BfBase(root, day) + ".none", "v2 unknown contract " + name + " " + UtcNow().ToString("u", CultureInfo.InvariantCulture) + "\n"); } catch (Exception) { }
        }

        private void NoTicks(string root, DateTime day)
        {
            try { File.WriteAllText(BfBase(root, day) + ".none", "v2 no ticks from the server " + bfReqName + " " + UtcNow().ToString("u", CultureInfo.InvariantCulture) + "\n"); } catch (Exception) { }
            if (day.DayOfWeek != DayOfWeek.Sunday)
            {
                int e;
                bfEmpty.TryGetValue(root, out e);
                bfEmpty[root] = e + 1;
                if (e + 1 >= BfEmptyStop)
                {
                    try { File.WriteAllText(Path.Combine(folder, "bf_" + root + "_end2.txt"), day.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) + "\n"); } catch (Exception) { }
                }
            }
        }

        private void SafeBackfilled(BarsRequest req, BarsRequest b, ErrorCode code)
        {
            string root;
            DateTime day;
            bool late;
            lock (BfLock)
            {
                if (req != bfReq)
                    return;                                                     // dropped (timeout / stop) meanwhile
                root = bfReqRoot;
                day = bfReqDay;
                late = !InWindow(EtNow());                                       // the answer came in trading hours: no write now
                bfWriting = !late;
            }
            int n = 0;
            bool ok = false;
            try
            {
                if (!late && code == ErrorCode.NoError && b != null && b.Bars != null && !terminated && !lowDisk)
                {
                    n = WriteDay(b.Bars, root, day);
                    ok = true;
                }
            }
            catch (Exception)
            {
                ok = false;
            }
            lock (BfLock)
            {
                bfWriting = false;
                if (req != bfReq)
                    return;
                DropRequest();
                if (late || terminated)
                    return;                                                     // no marker: the day is asked again on a later pass
                if (!ok)
                    bfErrors++;                                                 // an error is retried on the next pass
                else if (n == 0 && bfReqTry + 1 < Candidates(root, day).Count)
                {
                    Send(root, day, bfReqTry + 1);                              // empty: the other contract alive that day
                    return;
                }
                else if (n == 0)
                    NoTicks(root, day);
                else
                    bfEmpty[root] = 0;
            }
        }

        // the whole ET day into bf_<ROOT>_<day>.csv (via .tmp + rename); returns the number of trades written
        private int WriteDay(Bars bars, string root, DateTime day)
        {
            TimeZoneInfo disp = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo;
            string bfile = BfBase(root, day) + ".csv";
            string tmp = bfile + ".tmp";
            int n = 0;
            // Bars.GetBid / GetAsk through reflection (red team 2026-11-23): if this NinjaTrader build has no such method the add-on
            // still COMPILES (a missing member would block F5 for every script, LE_Feed included); the quote is then 0 and Python
            // uses the tick rule
            System.Reflection.MethodInfo getBid = null, getAsk = null;
            try
            {
                getBid = bars.GetType().GetMethod("GetBid", new Type[] { typeof(int) });
                getAsk = bars.GetType().GetMethod("GetAsk", new Type[] { typeof(int) });
            }
            catch (Exception)
            {
            }
            using (StreamWriter w = new StreamWriter(tmp, false, new UTF8Encoding(false)))
            {
                w.Write("t_ms,price,size,bid,ask\n");
                int count = bars.Count;
                for (int i = 0; i < count; i++)
                {
                    long vol = bars.GetVolume(i);
                    double px = bars.GetClose(i);
                    if (vol <= 0 || px <= 0)
                        continue;
                    DateTime utc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(bars.GetTime(i), DateTimeKind.Unspecified), disp);
                    if (TimeZoneInfo.ConvertTimeFromUtc(utc, eastern).Date != day.Date)
                        continue;
                    double bid = 0, ask = 0;
                    if (getBid != null && getAsk != null)
                    {
                        try
                        {
                            object[] ix = new object[] { i };
                            bid = Convert.ToDouble(getBid.Invoke(bars, ix), CultureInfo.InvariantCulture);
                            ask = Convert.ToDouble(getAsk.Invoke(bars, ix), CultureInfo.InvariantCulture);
                        }
                        catch (Exception)
                        {
                            bid = 0;
                            ask = 0;
                        }
                    }
                    long ms = (utc.Ticks - EpochTicks) / TimeSpan.TicksPerMillisecond;
                    w.Write(ms.ToString(CultureInfo.InvariantCulture) + "," + px.ToString("0.########", CultureInfo.InvariantCulture) + ","
                        + vol.ToString(CultureInfo.InvariantCulture) + "," + bid.ToString("0.########", CultureInfo.InvariantCulture) + ","
                        + ask.ToString("0.########", CultureInfo.InvariantCulture) + "\n");
                    n++;
                }
            }
            if (n == 0)
            {
                try { File.Delete(tmp); } catch (Exception) { }
                return 0;
            }
            if (File.Exists(bfile))
                File.Delete(bfile);
            File.Move(tmp, bfile);
            return n;
        }

        private string BackfillStatus()
        {
            int have = 0;
            string oldest = "";
            try
            {
                foreach (string f in Directory.GetFiles(folder, "bf_NQ_*"))           // NQ days: the ones the study needs
                {
                    string nm = Path.GetFileName(f);
                    if (nm.Length != "bf_NQ_2026-01-01.csv".Length && nm.Length != "bf_NQ_2026-01-01.done".Length)
                        continue;
                    if (!(nm.EndsWith(".csv") || nm.EndsWith(".done")))
                        continue;
                    have++;
                    string d = nm.Substring(6, 10);
                    if (oldest.Length == 0 || string.CompareOrdinal(d, oldest) < 0)
                        oldest = d;
                }
            }
            catch (Exception)
            {
            }
            string st;
            int err;
            lock (BfLock)
            {
                st = bfState;
                err = bfErrors;
            }
            return ",backfill=" + st + ",backfill_days=" + have.ToString(CultureInfo.InvariantCulture) + ",oldest=" + oldest
                + ",bf_errors=" + err.ToString(CultureInfo.InvariantCulture) + ",low_disk=" + (lowDisk ? "1" : "0")
                + ",bf_unknown=" + bfUnknown.ToString(CultureInfo.InvariantCulture)
                + ",depth=" + depthState + ",depth_rows=" + depthRows.ToString(CultureInfo.InvariantCulture);
        }

        // ================================================================================================ depth (day-ofmax)
        private bool DepthWanted(string root)
        {
            try
            {
                if (File.Exists(Path.Combine(folder, "depth_off.txt")))
                    return false;
                string p = Path.Combine(folder, "depth.txt");
                string list = File.Exists(p) ? File.ReadAllText(p) : "NQ";
                foreach (string raw in list.Split(new char[] { '\n', ',', ';' }))
                    if (raw.Trim().ToUpperInvariant() == root)
                        return true;
            }
            catch (Exception)
            {
            }
            return false;
        }

        private static Type FindType(string fullName)
        {
            foreach (System.Reflection.Assembly a in AppDomain.CurrentDomain.GetAssemblies())
            {
                try
                {
                    Type t = a.GetType(fullName, false);
                    if (t != null)
                        return t;
                }
                catch (Exception)
                {
                }
            }
            return null;
        }

        private static Type DepthType()
        {
            if (depthLooked)
                return depthType;
            depthLooked = true;
            try
            {
                Type gen = FindType("NinjaTrader.Data.MarketDepth`1");
                Type row = FindType("NinjaTrader.Data.MarketDepthRow");
                if (gen != null && row != null)
                    depthType = gen.MakeGenericType(row);
            }
            catch (Exception)
            {
                depthType = null;
            }
            return depthType;
        }

        private void DepthSubscribe(RecInst i, NinjaTrader.Cbi.Instrument ins)
        {
            try
            {
                Type t = DepthType();
                if (t == null) { depthState = "unavailable"; return; }
                try
                {
                    object ts = Member(Member(ins, "MasterInstrument"), "TickSize");
                    if (ts != null)
                        i.TickSize = Convert.ToDouble(ts, CultureInfo.InvariantCulture);
                }
                catch (Exception)
                {
                }
                if (!(i.TickSize > 0))
                    i.TickSize = 0.25;
                object md = Activator.CreateInstance(t, new object[] { ins });
                System.Reflection.EventInfo ev = t.GetEvent("Update");
                if (md == null || ev == null) { depthState = "unavailable"; return; }
                Delegate h = Delegate.CreateDelegate(ev.EventHandlerType, i, typeof(RecInst).GetMethod("OnDepthRaw"));
                ev.AddEventHandler(md, h);
                i.DepthObj = md;
                i.DepthEvent = ev;
                i.DepthHandler = h;
                depthState = "on";
            }
            catch (Exception)
            {
                depthState = "unavailable";
                i.DepthObj = null;
            }
        }

        private void DepthUnsubscribe(RecInst i)
        {
            try
            {
                if (i.DepthObj != null && i.DepthEvent != null && i.DepthHandler != null)
                    i.DepthEvent.RemoveEventHandler(i.DepthObj, i.DepthHandler);
                IDisposable d = i.DepthObj as IDisposable;
                if (d != null)
                    d.Dispose();
            }
            catch (Exception)
            {
            }
            i.DepthObj = null;
        }

        public static string DepthHeader()
        {
            StringBuilder h = new StringBuilder("t_ms,bp");
            string[] grp = new string[] { "bd", "bs", "ad", "as" };
            foreach (string g in grp)
                for (int k = 1; k <= DepthLevels; k++)
                    h.Append("," + g + k.ToString(CultureInfo.InvariantCulture));
            return h.Append("\n").ToString();
        }

        // a property OR a field by name (NinjaTrader's builds differ; null when neither exists)
        private static object Member(object o, string name)
        {
            if (o == null)
                return null;
            System.Reflection.PropertyInfo p = o.GetType().GetProperty(name);
            if (p != null)
                return p.GetValue(o, null);
            System.Reflection.FieldInfo f = o.GetType().GetField(name);
            return f == null ? null : f.GetValue(o);
        }

        // the first DepthLevels rows of MarketDepth.Bids / .Asks (each row: .Price, .Volume) through reflection
        private static List<double[]> Side(object md, string name)
        {
            List<double[]> res = new List<double[]>();
            System.Collections.IEnumerable en = Member(md, name) as System.Collections.IEnumerable;
            if (en == null)
                return res;
            foreach (object r in en)
            {
                if (r == null)
                    continue;
                object op = Member(r, "Price"), ov = Member(r, "Volume");
                if (op == null || ov == null)
                    continue;
                double px = Convert.ToDouble(op, CultureInfo.InvariantCulture);
                double v = Convert.ToDouble(ov, CultureInfo.InvariantCulture);
                if (px > 0 && v > 0)
                    res.Add(new double[] { px, v });
                if (res.Count >= DepthLevels)
                    break;
            }
            return res;
        }

        // one top-10 snapshot as the CSV tail after t_ms ("" when a side is empty); public for the test driver
        public static string BookLine(List<double[]> b, List<double[]> a, double tick)
        {
            if (b.Count == 0 || a.Count == 0 || !(tick > 0))
                return "";
            double bp = b[0][0];
            StringBuilder sb = new StringBuilder();
            sb.Append(bp.ToString("0.########", CultureInfo.InvariantCulture));
            for (int s2 = 0; s2 < 2; s2++)
            {
                List<double[]> lv = s2 == 0 ? b : a;
                for (int k = 0; k < DepthLevels; k++)                           // offsets in ticks from bp ("" = no level)
                    sb.Append(",").Append(k < lv.Count ? Math.Round((s2 == 0 ? bp - lv[k][0] : lv[k][0] - bp) / tick).ToString("0", CultureInfo.InvariantCulture) : "");
                for (int k = 0; k < DepthLevels; k++)                           // sizes (0 = no level)
                    sb.Append(",").Append(k < lv.Count ? lv[k][1].ToString("0", CultureInfo.InvariantCulture) : "0");
            }
            return sb.ToString();
        }

        // a depth event (or the 1 s timer for a change inside the 250 ms gap): one snapshot line when the top 10 changed
        private void SafeDepth(RecInst i, bool fromTimer)
        {
            try
            {
                if (!on || terminated || lowDisk || i.DepthObj == null)
                    return;
                DateTime now = UtcNow();
                lock (i.DepthLock)
                {
                    if ((now - i.LastSnap).TotalMilliseconds < DepthMinMs)
                    {
                        i.DepthDirty = true;
                        return;
                    }
                    i.DepthDirty = false;
                    string book = BookLine(Side(i.DepthObj, "Bids"), Side(i.DepthObj, "Asks"), i.TickSize);
                    if (book.Length == 0 || book == i.LastBook)
                        return;                                                 // empty or nothing changed in the top 10
                    i.LastBook = book;
                    i.LastSnap = now;
                    long ms = (now.Ticks - EpochTicks) / TimeSpan.TicksPerMillisecond;
                    string day = TimeZoneInfo.ConvertTimeFromUtc(now, eastern).ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
                    string path = Path.Combine(Path.Combine(folder, "depth"), i.Root + "_" + day + ".csv");
                    string line = ms.ToString(CultureInfo.InvariantCulture) + "," + book + "\n";
                    lock (BufLock)
                    {
                        StringBuilder w;
                        if (!buf.TryGetValue(path, out w))
                        {
                            w = new StringBuilder();
                            buf[path] = w;
                        }
                        w.Append(line);
                        depthRows++;
                    }
                }
            }
            catch (Exception)
            {
            }
        }

        private void Flush(object state)
        {
            List<RecInst> snap = new List<RecInst>();
            lock (InstLock)
            {
                foreach (RecInst i in insts)
                    if (i.DepthObj != null && i.DepthDirty)
                        snap.Add(i);
            }
            foreach (RecInst i in snap)
                SafeDepth(i, true);                                             // a change that came inside the 250 ms gap
            Dictionary<string, string> todo = new Dictionary<string, string>();
            lock (BufLock)
            {
                foreach (KeyValuePair<string, StringBuilder> kv in buf)
                    if (kv.Value.Length > 0)
                        todo[kv.Key] = kv.Value.ToString();
                buf.Clear();
            }
            if (lowDisk)
                return;                                                         // under 10 GB free: drop, never fill the disk
            foreach (KeyValuePair<string, string> kv in todo)
            {
                try
                {
                    bool fresh = !File.Exists(kv.Key);
                    bool depth = Path.GetFileName(Path.GetDirectoryName(kv.Key)) == "depth";
                    if (depth && fresh)
                        Directory.CreateDirectory(Path.GetDirectoryName(kv.Key));
                    File.AppendAllText(kv.Key, (fresh ? (depth ? DepthHeader() : "t_ms,price,size,bid,ask\n") : "") + kv.Value);
                }
                catch (Exception)
                {
                }
            }
        }
    }
}
