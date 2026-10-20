// LE_BarFeed - Liquidity Engine bar feed for NinjaTrader 8 (NinjaScript indicator)
//
// Writes every CLOSED bar of the chart it runs on to
//     Documents\NinjaTrader 8\le_feed\<ROOT>_<N>m.csv          e.g. MNQ_5m.csv
// and, on a chart of more than 1 minute with "Also write 1-minute bars" on (the default), every closed 1-minute bar of the
// same instrument to a second file in the same folder and format:
//     Documents\NinjaTrader 8\le_feed\<ROOT>_1m.csv            e.g. MNQ_1m.csv   (LIT enters on 1-minute bars)
// one line per bar:  time,open,high,low,close,volume   with time = the bar's OPEN time in unix seconds (UTC).
// It also keeps ONE line in <ROOT>_1m_open.csv: "time,open" of the minute that has just started (its first trade), rewritten
// once a minute. LIT decides an entry when its 1-minute CISD candle closes and sends a market order at once; the bot sizes
// that order from this open, the price the backtest fills at (research/writeups/lit-live-fills.md).
// The Python bot (engine/ninjatrader.py, data_source "ninjatrader") reads these files instead of Yahoo, so it trades on
// the same real CME bars NinjaTrader shows.
//
// Cheap on a low-end PC: the chart's history is written ONCE when the chart has finished loading (one file write);
// after that each closed bar is ONE short appended line; the file is rewritten (trimmed to "Max bars in file") only
// after "Trim every N bars" extra bars (1000 by default: every ~3.5 days on a 5-minute chart, every ~17 hours for the
// 1-minute file).
//
// Install: copy this file to Documents\NinjaTrader 8\bin\Custom\Indicators\, open the NinjaScript Editor, press F5.
// Use: ONE MNQ 5-minute chart, Trading hours "CME US Index Futures ETH", 30 days loaded: it writes MNQ_5m.csv and
// MNQ_1m.csv (the 1-minute series is added by the indicator itself). Do not also run it on a separate 1-minute chart of
// the same instrument (two writers on MNQ_1m.csv), or switch "Also write 1-minute bars" off there.
// Only standard NinjaScript: OnStateChange / OnBarUpdate / OnMarketData, Calculate.OnBarClose, File.AppendAllText; C# 5 syntax only
// (no $"..." strings, no ?. or =>), so it compiles on every NinjaTrader 8 version.

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class LE_BarFeed : Indicator
    {
        private const string Header = "time,open,high,low,close,volume";
        private static readonly object FileLock = new object();   // one writer at a time, across every LE_BarFeed in NinjaTrader
        private static readonly long EpochTicks = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc).Ticks;

        // One output file per bar series: [0] = the chart's own bars, [1] = the added 1-minute series (when there is one).
        private class Feed
        {
            public string FilePath;
            public int Minutes;
            public int MaxBars;
            public long LastOpen = long.MinValue;
            public int LinesInFile;
            public Queue<string> History = new Queue<string>();   // bars seen while the chart loads; written at State.Realtime
        }

        private Feed[] feeds;
        private bool active;                  // a minute chart and the le_feed folder exists
        private bool addOneMinute;            // the chart is > 1 minute and the 1-minute file is wanted: series 1 is written
        private int problems;
        private string openPath;              // <ROOT>_1m_open.csv: "time,open" of the minute that has just started
        private long lastOpenMinute = long.MinValue;
        private bool realtime;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Liquidity Engine bar feed: writes each closed bar (and each closed 1-minute bar) to Documents\\NinjaTrader 8\\le_feed for the Python bot";
                Name = "LE_BarFeed";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = false;
                DrawOnPricePanel = false;
                PaintPriceMarkers = false;
                IsSuspendedWhileInactive = false;   // keep writing when the chart is minimized or sits in a hidden tab
                MaxBars = 8000;                     // 8000 five-minute bars = about 29 trading days
                MaxBars1m = 20000;                  // 20000 one-minute bars = about 14 trading days
                TrimEvery = 1000;
                WriteOneMinute = true;
            }
            else if (State == State.Configure)
            {
                // Always added, with fixed arguments: the Help Guide says AddDataSeries() must not depend on run-time values
                // (chart period, inputs). Whether series 1 is written is decided at State.DataLoaded.
                AddDataSeries(BarsPeriodType.Minute, 1);       // same instrument and trading hours as the chart
            }
            else if (State == State.DataLoaded)
            {
                active = BarsPeriod.BarsPeriodType == BarsPeriodType.Minute && BarsPeriod.Value >= 1;
                addOneMinute = active && WriteOneMinute && BarsPeriod.Value > 1 && BarsArray.Length > 1;
                if (!active)
                {
                    Print("LE_BarFeed: only minute charts are supported (this chart: " + BarsPeriod.ToString() + "). Nothing is written.");
                    return;
                }
                string folder = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "le_feed");
                string root = Instrument.MasterInstrument.Name;
                feeds = new Feed[addOneMinute ? 2 : 1];
                feeds[0] = new Feed { Minutes = BarsPeriod.Value, MaxBars = BarsPeriod.Value == 1 ? Math.Max(MaxBars, MaxBars1m) : MaxBars };
                feeds[0].FilePath = Path.Combine(folder, root + "_" + feeds[0].Minutes.ToString(CultureInfo.InvariantCulture) + "m.csv");
                if (addOneMinute)
                {
                    feeds[1] = new Feed { Minutes = 1, MaxBars = MaxBars1m };
                    feeds[1].FilePath = Path.Combine(folder, root + "_1m.csv");
                }
                if (addOneMinute || BarsPeriod.Value == 1)
                    openPath = Path.Combine(folder, root + "_1m_open.csv");
                try
                {
                    Directory.CreateDirectory(folder);
                }
                catch (Exception e)
                {
                    active = false;
                    Report(null, "cannot create the folder " + folder + ": " + e.Message);
                }
                // <ROOT>_instrument.txt: the chart's contract ("MNQ 12-26"). The bot refuses an entry when its order contract
                // differs (the chart left on the old contract after the roll: December prices on a March order)
                if (active)
                {
                    try
                    {
                        File.WriteAllText(Path.Combine(folder, root + "_instrument.txt"), Instrument.FullName);
                    }
                    catch (Exception e)
                    {
                        Report(null, "cannot write " + root + "_instrument.txt: " + e.Message);
                    }
                }
            }
            else if (State == State.Realtime)
            {
                realtime = true;
                if (active && feeds != null)
                    foreach (Feed f in feeds)
                        if (f.History != null)
                            WriteHistory(f);
            }
        }

        protected override void OnBarUpdate()
        {
            if (!active || feeds == null || BarsInProgress >= feeds.Length)
                return;
            int s = BarsInProgress;
            if (CurrentBars[s] < 0)
                return;
            Feed f = feeds[s];
            long open;
            try
            {
                open = OpenUnix(s, f.Minutes);
            }
            catch (Exception e)
            {
                Report(f, "bar time conversion failed (" + e.Message + "); bar skipped");
                return;
            }
            if (open <= f.LastOpen)
                return;                             // the same bar again, or out of order
            f.LastOpen = open;
            string line = Line(s, open);
            if (f.History != null)                  // still loading (Historical / Transition): written in one go at Realtime
            {
                f.History.Enqueue(line);
                while (f.History.Count > f.MaxBars)
                    f.History.Dequeue();
                return;
            }
            lock (FileLock)
            {
                try
                {
                    File.AppendAllText(f.FilePath, line + "\n");
                    f.LinesInFile++;
                }
                catch (Exception e)
                {
                    Report(f, "append failed (" + e.Message + "); this bar is missing from the feed");
                    return;
                }
                if (f.LinesInFile > f.MaxBars + TrimEvery)
                    Trim(f);
            }
        }

        // The first trade of every new minute = that 1-minute bar's open: one line "time,open" (time = the minute's start in
        // unix seconds, UTC) replaces <ROOT>_1m_open.csv. It arrives with the tick that closes the previous bar (OnBarClose),
        // so the bot reads the closed bar and the new bar's open in the same poll. Realtime only; one tiny write a minute.
        protected override void OnMarketData(MarketDataEventArgs marketDataUpdate)
        {
            if (!active || !realtime || openPath == null || BarsInProgress != 0 || marketDataUpdate.MarketDataType != MarketDataType.Last)
                return;
            long minute;
            try
            {
                DateTime local = DateTime.SpecifyKind(marketDataUpdate.Time, DateTimeKind.Unspecified);
                DateTime utc = TimeZoneInfo.ConvertTimeToUtc(local, NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);
                long secs = (utc.Ticks - EpochTicks) / TimeSpan.TicksPerSecond;
                minute = secs - secs % 60;
            }
            catch (Exception)
            {
                return;
            }
            if (minute <= lastOpenMinute)
                return;
            lastOpenMinute = minute;
            string line = minute.ToString(CultureInfo.InvariantCulture) + "," + marketDataUpdate.Price.ToString("0.########", CultureInfo.InvariantCulture) + "\n";
            string tmp = openPath + ".tmp";
            lock (FileLock)
            {
                try
                {
                    File.WriteAllText(tmp, line);
                    if (File.Exists(openPath))
                        File.Replace(tmp, openPath, null);   // one atomic swap: the bot never reads half a line
                    else
                        File.Move(tmp, openPath);
                }
                catch (Exception)
                {
                    try
                    {
                        File.Copy(tmp, openPath, true);
                    }
                    catch (Exception e2)
                    {
                        Report(null, "could not write " + openPath + ": " + e2.Message);
                    }
                }
            }
        }

        // NinjaTrader stamps minute bars with their CLOSE time in its display time zone (Tools > Options > General >
        // Preferences > Time zone; Help Guide "Application TimeZoneInfo"). Convert the close to UTC first (always a
        // valid local time), then step back one bar to the OPEN.
        private long OpenUnix(int s, int minutes)
        {
            DateTime closeLocal = DateTime.SpecifyKind(Times[s][0], DateTimeKind.Unspecified);
            DateTime closeUtc = TimeZoneInfo.ConvertTimeToUtc(closeLocal, NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);
            return (closeUtc.Ticks - EpochTicks) / TimeSpan.TicksPerSecond - 60L * minutes;
        }

        private string Line(int s, long open)
        {
            CultureInfo c = CultureInfo.InvariantCulture;
            return open.ToString(c) + "," + Opens[s][0].ToString("0.########", c) + "," + Highs[s][0].ToString("0.########", c) + ","
                 + Lows[s][0].ToString("0.########", c) + "," + Closes[s][0].ToString("0.########", c) + ","
                 + Volumes[s][0].ToString("0.########", c);
        }

        private void WriteHistory(Feed f)
        {
            StringBuilder sb = new StringBuilder(f.History.Count * 48 + 64);
            sb.Append(Header).Append('\n');
            foreach (string l in f.History)
                sb.Append(l).Append('\n');
            int n = f.History.Count;
            f.History.Clear();
            f.History = null;
            bool ok;
            lock (FileLock)
                ok = Swap(f, sb.ToString());
            if (ok)
            {
                f.LinesInFile = n;
                Print("LE_BarFeed: " + n + " bars written to " + f.FilePath + "; appending each new bar");
            }
        }

        private void Trim(Feed f)
        {
            try
            {
                string[] lines = File.ReadAllLines(f.FilePath);
                int keep = Math.Min(f.MaxBars, lines.Length);
                StringBuilder sb = new StringBuilder(keep * 48 + 64);
                sb.Append(Header).Append('\n');
                for (int i = lines.Length - keep; i < lines.Length; i++)
                    if (lines[i].Length > 0 && lines[i] != Header)
                        sb.Append(lines[i]).Append('\n');
                if (Swap(f, sb.ToString()))
                    f.LinesInFile = keep;
                else
                    f.LinesInFile = f.MaxBars;      // try again after another TrimEvery bars
            }
            catch (Exception e)
            {
                Report(f, "trim failed (" + e.Message + "); will try again later");
                f.LinesInFile = f.MaxBars;
            }
        }

        // Write next to the feed file, then swap it in, so the bot never reads a half-written file.
        private bool Swap(Feed f, string text)
        {
            string tmp = f.FilePath + ".tmp";
            try
            {
                File.WriteAllText(tmp, text);
                if (File.Exists(f.FilePath))
                    File.Replace(tmp, f.FilePath, null);
                else
                    File.Move(tmp, f.FilePath);
                return true;
            }
            catch (Exception)
            {
                try
                {
                    File.Copy(tmp, f.FilePath, true);  // the bot had the file open for reading: overwrite in place instead
                    File.Delete(tmp);
                    return true;
                }
                catch (Exception e2)
                {
                    Report(f, "could not write the feed file: " + e2.Message);
                    return false;
                }
            }
        }

        private void Report(Feed f, string text)
        {
            problems++;
            if (problems <= 5)                      // never flood the log: the first five problems only
            {
                Print("LE_BarFeed " + (f != null ? f.FilePath : "") + ": " + text);
                Log("LE_BarFeed: " + text, LogLevel.Warning);
            }
        }

        #region Properties
        [Range(500, 100000)]
        [Display(Name = "Max bars in file", Description = "Bars of the chart kept in its CSV (8000 five-minute bars = about 29 trading days)", Order = 1, GroupName = "LE_BarFeed")]
        public int MaxBars { get; set; }

        [Range(500, 200000)]
        [Display(Name = "Max 1-minute bars in file", Description = "Bars kept in the 1-minute CSV (20000 = about 14 trading days)", Order = 2, GroupName = "LE_BarFeed")]
        public int MaxBars1m { get; set; }

        [Range(50, 20000)]
        [Display(Name = "Trim every N bars", Description = "A file is rewritten (trimmed) only after this many extra bars", Order = 3, GroupName = "LE_BarFeed")]
        public int TrimEvery { get; set; }

        [Display(Name = "Also write 1-minute bars", Description = "On a 5-minute chart, also write <ROOT>_1m.csv from an added 1-minute series (LIT needs it)", Order = 4, GroupName = "LE_BarFeed")]
        public bool WriteOneMinute { get; set; }
        #endregion
    }
}
