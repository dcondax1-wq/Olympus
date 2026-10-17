// LE_BarFeed - Liquidity Engine bar feed for NinjaTrader 8 (NinjaScript indicator)
//
// Writes every CLOSED bar of the chart it runs on to
//     Documents\NinjaTrader 8\le_feed\<ROOT>_<N>m.csv          e.g. MNQ_5m.csv, MNQ_1m.csv
// one line per bar:  time,open,high,low,close,volume   with time = the bar's OPEN time in unix seconds (UTC).
// The Python bot (engine/ninjatrader.py, data_source "ninjatrader") reads these files instead of Yahoo, so it trades on
// the same real CME bars NinjaTrader shows.
//
// Cheap on a low-end PC: the chart's history is written ONCE when the chart has finished loading (one file write);
// after that each closed bar is ONE short appended line; the file is rewritten (trimmed to "Max bars in file") only
// after "Trim every N bars" extra bars (1000 by default: every ~3.5 days on a 5-minute chart).
//
// Install: copy this file to Documents\NinjaTrader 8\bin\Custom\Indicators\, open the NinjaScript Editor, press F5.
// Use: an MNQ 5-minute chart (optionally a 1-minute one), Trading hours "CME US Index Futures ETH", 30 days loaded.
// Only standard NinjaScript: OnStateChange / OnBarUpdate, Calculate.OnBarClose, File.AppendAllText.

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Text;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class LE_BarFeed : Indicator
    {
        private const string Header = "time,open,high,low,close,volume";
        private static readonly long EpochTicks = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc).Ticks;
        private string filePath;
        private bool active;                  // a minute chart and the le_feed folder exists
        private long lastOpen = long.MinValue;
        private int linesInFile;
        private Queue<string> history;        // bars seen while the chart loads; written in one go at State.Realtime, then null
        private int problems;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Liquidity Engine bar feed: writes each closed bar to Documents\\NinjaTrader 8\\le_feed for the Python bot";
                Name = "LE_BarFeed";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = false;
                DrawOnPricePanel = false;
                PaintPriceMarkers = false;
                IsSuspendedWhileInactive = false;   // keep writing when the chart is minimized or sits in a hidden tab
                MaxBars = 8000;                     // 8000 five-minute bars = about 29 trading days
                TrimEvery = 1000;
            }
            else if (State == State.DataLoaded)
            {
                active = BarsPeriod.BarsPeriodType == BarsPeriodType.Minute && BarsPeriod.Value >= 1;
                if (!active)
                {
                    Print("LE_BarFeed: only minute charts are supported (this chart: " + BarsPeriod.ToString() + "). Nothing is written.");
                    return;
                }
                string folder = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "le_feed");
                filePath = Path.Combine(folder, Instrument.MasterInstrument.Name + "_" + BarsPeriod.Value.ToString(CultureInfo.InvariantCulture) + "m.csv");
                history = new Queue<string>();
                try
                {
                    Directory.CreateDirectory(folder);
                }
                catch (Exception e)
                {
                    active = false;
                    Report("cannot create the folder " + folder + ": " + e.Message);
                }
            }
            else if (State == State.Realtime)
            {
                if (active && history != null)
                    WriteHistory();
            }
        }

        protected override void OnBarUpdate()
        {
            if (!active)
                return;
            long open;
            try
            {
                open = OpenUnix();
            }
            catch (Exception e)
            {
                Report("bar time conversion failed (" + e.Message + "); bar skipped");
                return;
            }
            if (open <= lastOpen)
                return;                             // the same bar again, or out of order
            lastOpen = open;
            string line = Line(open);
            if (history != null)                    // still loading (Historical / Transition): written in one go at Realtime
            {
                history.Enqueue(line);
                while (history.Count > MaxBars)
                    history.Dequeue();
                return;
            }
            try
            {
                File.AppendAllText(filePath, line + "\n");
                linesInFile++;
                if (linesInFile > MaxBars + TrimEvery)
                    Trim();
            }
            catch (Exception e)
            {
                Report("append failed (" + e.Message + "); this bar is missing from the feed");
            }
        }

        // NinjaTrader stamps minute bars with their CLOSE time in its display time zone (Tools > Options > General >
        // Preferences > Time zone; Help Guide "Application TimeZoneInfo"). Convert the close to UTC first (always a
        // valid local time), then step back one bar to the OPEN.
        private long OpenUnix()
        {
            DateTime closeLocal = DateTime.SpecifyKind(Time[0], DateTimeKind.Unspecified);
            DateTime closeUtc = TimeZoneInfo.ConvertTimeToUtc(closeLocal, NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);
            return (closeUtc.Ticks - EpochTicks) / TimeSpan.TicksPerSecond - 60L * BarsPeriod.Value;
        }

        private string Line(long open)
        {
            CultureInfo c = CultureInfo.InvariantCulture;
            return open.ToString(c) + "," + Open[0].ToString("0.########", c) + "," + High[0].ToString("0.########", c) + ","
                 + Low[0].ToString("0.########", c) + "," + Close[0].ToString("0.########", c) + ","
                 + Volume[0].ToString("0.########", c);
        }

        private void WriteHistory()
        {
            StringBuilder sb = new StringBuilder(history.Count * 48 + 64);
            sb.Append(Header).Append('\n');
            foreach (string l in history)
                sb.Append(l).Append('\n');
            int n = history.Count;
            history.Clear();
            history = null;
            if (Swap(sb.ToString()))
                linesInFile = n;
            Print("LE_BarFeed: " + n + " bars written to " + filePath + "; appending each new bar");
        }

        private void Trim()
        {
            try
            {
                string[] lines = File.ReadAllLines(filePath);
                int keep = Math.Min(MaxBars, lines.Length);
                StringBuilder sb = new StringBuilder(keep * 48 + 64);
                sb.Append(Header).Append('\n');
                for (int i = lines.Length - keep; i < lines.Length; i++)
                    if (lines[i].Length > 0 && lines[i] != Header)
                        sb.Append(lines[i]).Append('\n');
                if (Swap(sb.ToString()))
                    linesInFile = keep;
                else
                    linesInFile = MaxBars;          // try again after another TrimEvery bars
            }
            catch (Exception e)
            {
                Report("trim failed (" + e.Message + "); will try again later");
                linesInFile = MaxBars;
            }
        }

        // Write next to the feed file, then swap it in, so the bot never reads a half-written file.
        private bool Swap(string text)
        {
            string tmp = filePath + ".tmp";
            try
            {
                File.WriteAllText(tmp, text);
                if (File.Exists(filePath))
                    File.Replace(tmp, filePath, null);
                else
                    File.Move(tmp, filePath);
                return true;
            }
            catch (Exception)
            {
                try
                {
                    File.Copy(tmp, filePath, true);  // the bot had the file open for reading: overwrite in place instead
                    File.Delete(tmp);
                    return true;
                }
                catch (Exception e2)
                {
                    Report("could not write the feed file: " + e2.Message);
                    return false;
                }
            }
        }

        private void Report(string text)
        {
            problems++;
            if (problems <= 5)                      // never flood the log: the first five problems only
            {
                Print("LE_BarFeed " + (filePath ?? "") + ": " + text);
                Log("LE_BarFeed: " + text, LogLevel.Warning);
            }
        }

        #region Properties
        [Range(500, 100000)]
        [Display(Name = "Max bars in file", Description = "Bars kept in the CSV (8000 five-minute bars = about 29 trading days)", Order = 1, GroupName = "LE_BarFeed")]
        public int MaxBars { get; set; }

        [Range(50, 20000)]
        [Display(Name = "Trim every N bars", Description = "The file is rewritten (trimmed) only after this many extra bars", Order = 2, GroupName = "LE_BarFeed")]
        public int TrimEvery { get; set; }
        #endregion
    }
}
