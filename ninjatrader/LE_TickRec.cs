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
// UNVERIFIED (written without NinjaTrader; same API surface as LE_Feed.cs plus three fields):
//  1. MarketDataEventArgs.Volume (long), .Bid and .Ask (double: the best bid / ask when the Last event fires). If Bid / Ask
//     are 0 the recorder falls back to the last Bid / Ask events it saw; Python then uses the tick rule.
//  2. MarketDataEventArgs.Time in NinjaTrader's display time zone (same assumption as LE_Feed.SafeMarketData).
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
                else if (want && (!on || lt != listText))
                {
                    Unsubscribe();
                    listText = lt;
                    Subscribe(lt);
                    on = true;
                }
                string names = "";
                foreach (RecInst i in insts)
                    names += (names.Length > 0 ? ";" : "") + i.Name;
                File.WriteAllText(statusPath, DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture)
                    + ",on=" + (on ? "1" : "0") + ",instruments=" + names + ",rows=" + rows.ToString(CultureInfo.InvariantCulture) + "\n");
            }
            catch (Exception)
            {
            }
        }

        private void Subscribe(string lt)
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
                }
                catch (Exception)
                {
                }
            }
        }

        private void Unsubscribe()
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

        private void Flush(object state)
        {
            Dictionary<string, string> todo = new Dictionary<string, string>();
            lock (BufLock)
            {
                foreach (KeyValuePair<string, StringBuilder> kv in buf)
                    if (kv.Value.Length > 0)
                        todo[kv.Key] = kv.Value.ToString();
                buf.Clear();
            }
            foreach (KeyValuePair<string, string> kv in todo)
            {
                try
                {
                    bool fresh = !File.Exists(kv.Key);
                    File.AppendAllText(kv.Key, (fresh ? "t_ms,price,size,bid,ask\n" : "") + kv.Value);
                }
                catch (Exception)
                {
                }
            }
        }
    }
}
