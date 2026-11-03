// LE_Feed - Liquidity Engine bar feed for NinjaTrader 8 WITHOUT a chart (NinjaScript AddOn, 2026-11-02)
//
// The headless twin of LE_BarFeed.cs (the chart indicator). It runs inside NinjaTrader from the moment NinjaTrader starts,
// with no chart and no workspace, and writes exactly the files LE_BarFeed writes, in the same format:
//     Documents\NinjaTrader 8\le_feed\<ROOT>_5m.csv          time,open,high,low,close,volume   (time = bar OPEN, unix s UTC)
//     Documents\NinjaTrader 8\le_feed\<ROOT>_1m.csv          same, 1-minute bars (LIT enters on them)
//     Documents\NinjaTrader 8\le_feed\<ROOT>_1m_open.csv     one line "time,open": the first trade of the minute just started
//     Documents\NinjaTrader 8\le_feed\<ROOT>_instrument.txt  the contract it reads ("MNQ 12-26"): the bot's roll guard
//     Documents\NinjaTrader 8\le_feed\accounts.csv           name,time,cash,realized,unrealized,netliq (once a minute)
// plus two files of its own:
//     le_feed\le_feed_status.txt   one line a minute: time,source=addon,instruments=A;B,last_1m=<unix>,resubs=N,connected=0|1
//     le_feed\le_feed_log.txt      every (re)subscribe and problem, one line each, trimmed to the last 300 lines
//
// Which instruments: le_feed\feed_instruments.txt, one NinjaTrader name per line ("MNQ 12-26"); the Python bot writes it
// (engine/ninjatrader.py sync_feed_instruments: the contract it orders, plus NQ with signal_root "NQ"), so the quarterly
// roll needs no click. Missing or empty file = "MNQ 12-26". Re-read every 3 minutes. One contract per root (the files are
// named by root): the first line of a root wins.
//
// SELF-HEAL (the reason this exists): the chart feed went stale overnight after "Connection lost to the NinjaTrader
// Historical Data Server" and stayed stale until someone re-added the indicator. Here, while a price connection is
// Connected and CME should be trading, a 1-minute series with no new closed bar for 3 minutes is thrown away and requested
// again (at most once every 2 minutes per instrument); a connection that comes back (ConnectionStatusUpdate -> Connected)
// re-requests everything. Each re-request rewrites the history files, which also fills any hole the outage left.
//
// NO DOUBLE WRITER: LE_FeedHub (below) tells LE_BarFeed which roots this add-on writes; an LE_BarFeed chart of such a root
// writes nothing (bars, 1m open, instrument, accounts), so the owner may keep the old chart open. LE_BarFeed finds the hub
// by reflection, so LE_BarFeed.cs still compiles and behaves exactly as before when this file is not installed.
//
// READ-ONLY: it never places, changes or cancels an order. Every NinjaTrader call sits in try/catch: a failure is written
// to le_feed_log.txt and can never take NinjaTrader down. C# 5 syntax only (no $"..." strings, no ?., no => members).
//
// Install: copy this file to Documents\NinjaTrader 8\bin\Custom\AddOns\, NinjaScript Editor, F5. Nothing else: no chart.
//
// PROOF OF LIFE (2026-11-03): the moment it starts it writes le_feed\le_feed_status.txt and prints
// "LE_Feed: started ..." in NinjaTrader's Output window (New > NinjaScript Output) and le_feed\le_feed_log.txt.
// No such line a minute after F5 = it did not start (look for a red error at the bottom of the NinjaScript Editor).
// START: whichever comes first of State.Active, OnWindowCreated (the Control Center window: NinjaTrader calls this for
// every add-on, also right after F5) and a 10 s timer from State.Configure; only one LE_Feed ever runs.
// ONE WRITER ACROSS RECOMPILES: each start writes a fresh token to le_feed\le_feed_owner.txt; an older copy (the assembly
// before an F5, if NinjaTrader did not terminate it) sees the new token on its next 15 s tick and stops itself.
//
// UNVERIFIED (written without a NinjaTrader install; only compiled with mono mcs -langversion:5 against hand-made stubs
// of the NinjaTrader types below, which checks the C# 5 syntax but not the real API; check these first if F5 shows an error):
//  1. AddOnBase.OnStateChange / OnWindowCreated(System.Windows.Window). Three start paths, see START above.
//  2. new BarsRequest(Instrument, DateTime from, DateTime to); .BarsPeriod, .TradingHours, .Update (+= a method
//     (object, BarsUpdateEventArgs)), .Request(Action<BarsRequest, ErrorCode, string>), .Bars (Count, GetTime/GetOpen/
//     GetHigh/GetLow/GetClose/GetVolume(i)). Dispose is called through IDisposable only if BarsRequest implements it.
//  3. Bars.GetTime(i) of a BarsRequest = the bar's CLOSE time in NinjaTrader's display time zone, as Times[] on a chart
//     (the same conversion as LE_BarFeed). If the bot says "bars stamped 17:00-17:59 ET", this is wrong.
//  4. new MarketData(Instrument) + .Update (object, MarketDataEventArgs); disposed through IDisposable if it has it.
//     MarketDataEventArgs.Time assumed in the display time zone, as in an indicator's OnMarketData.
//  5. Connection.Connections (lockable collection), Connection.PriceStatus, the static Connection.ConnectionStatusUpdate
//     event with ConnectionStatusEventArgs.PriceStatus / PreviousPriceStatus.
//  6. NinjaTrader.Code.Output.Process(text, PrintTo.OutputTab1) for the Output window lines (start, stop, re-subscribes,
//     first history written), each inside try/catch.
// NinjaTrader's own types are named in full where an AddOn property of the same name could hide them (Instrument,
// TradingHours, Account, Connection); the nested helper classes are FeedSeries / FeedInst (never NinjaScript's Series<T>).
//  7. Live bars arrive through BarsRequest.Update after Request() (a bar is written once the NEXT bar exists, the same
//     "closed" rule as Calculate.OnBarClose on the chart).

#region Using declarations
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    // Shared with LE_BarFeed (NinjaScript compiles every file into one assembly). LE_BarFeed reads it by reflection:
    // keep the names Covers(string) and WritesAccounts().
    public static class LE_FeedHub
    {
        public static volatile bool HeadlessOn;       // the LE_Feed add-on is running
        public static volatile bool AccountsOn;       // ... and writes accounts.csv
        private static readonly object Sync = new object();
        private static readonly HashSet<string> roots = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        // A root stays covered while the add-on runs (it re-requests a stale series itself; a chart would only add a writer).
        public static void Cover(string root)
        {
            if (string.IsNullOrEmpty(root))
                return;
            lock (Sync)
                roots.Add(root);
        }

        public static void Clear()
        {
            HeadlessOn = false;
            AccountsOn = false;
            lock (Sync)
                roots.Clear();
        }

        public static bool Covers(string root)
        {
            if (!HeadlessOn || string.IsNullOrEmpty(root))
                return false;
            lock (Sync)
                return roots.Contains(root);
        }

        public static bool WritesAccounts()
        {
            return HeadlessOn && AccountsOn;
        }
    }

    public class LE_Feed : AddOnBase
    {
        private const string Header = "time,open,high,low,close,volume";
        private const string DefaultInstrument = "MNQ 12-26";
        private const string TradingHoursName = "CME US Index Futures ETH";   // the chart's trading hours (SETUP.md step 4)
        private const int TickMs = 15000;                  // the housekeeping timer
        private const int Days5m = 30;                     // as the chart: Days to load 30
        private const int Days1m = 21;                     // enough for the 20000 1-minute bars kept (about 14 trading days)
        private const int MaxBars5m = 8000;                // LE_BarFeed's defaults
        private const int MaxBars1m = 20000;
        private const int TrimEvery = 1000;
        private const int StaleSeconds = 180;              // no new closed 1-minute bar for 3 minutes -> re-request
        private const int ResubGapSeconds = 120;           // at most one re-request every 2 minutes per instrument
        private const int ListEverySeconds = 180;          // re-read feed_instruments.txt
        private const int MaxInstruments = 4;
        private static readonly long EpochTicks = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc).Ticks;
        private static readonly object FileLock = new object();
        private static readonly object RunLock = new object();
        private static LE_Feed running;                    // one feed per NinjaTrader

        // one bar file (5m or 1m) of one instrument, fed by its own BarsRequest
        private class FeedSeries
        {
            public LE_Feed Feed;
            public FeedInst Owner;
            public int Minutes;
            public int Days;
            public int MaxBars;
            public string FilePath;
            public BarsRequest Req;
            public int Gen;                                // bumped on every (re)request: late callbacks of an old one are ignored
            public bool Ready;                             // history written: live updates append
            public bool Failed;
            public long LastOpen = long.MinValue;
            public int LinesInFile;
            public int NextIndex;                          // first bar index not yet written
            public readonly object Sync = new object();

            public void OnUpdate(object sender, BarsUpdateEventArgs e)
            {
                Feed.SafeUpdate(this);
            }
        }

        private class FeedInst
        {
            public LE_Feed Feed;
            public string Name;
            public string Root;
            public Instrument Instrument;
            public FeedSeries S5;
            public FeedSeries S1;
            public string OpenPath;
            public string InstPath;
            public MarketData Md;
            public long LastOpenMinute = long.MinValue;
            public DateTime LastNew1mUtc = DateTime.UtcNow;   // wall clock of the last new closed 1-minute bar (or request)
            public DateTime LastResubUtc = DateTime.MinValue;
            public DateTime LastLiveBarUtc = DateTime.MinValue; // wall clock of the last LIVE closed 1-minute bar (not history)
            public int StaleStreak;                        // stale re-requests in a row without a live bar since (backoff)
            public bool Subscribed;

            public void OnMarketData(object sender, MarketDataEventArgs e)
            {
                Feed.SafeMarketData(this, e);
            }
        }

        private string folder;
        private string listPath;
        private string statusPath;
        private string logPath;
        private string accountsPath;
        private string ownerPath;
        private readonly string ownerToken = Guid.NewGuid().ToString("N");
        private DateTime startedUtc = DateTime.MinValue;
        private bool historyAnnounced;
        private readonly List<FeedInst> insts = new List<FeedInst>();
        private readonly object Gate = new object();       // one housekeeping pass at a time
        private System.Threading.Timer timer;
        private System.Threading.Timer startTimer;
        private bool started;
        private volatile bool terminated;
        private bool stopped;
        private volatile bool reconnectPending;
        private volatile bool acctDue;
        private bool connSubscribed;
        private string listText;                           // feed_instruments.txt as last read
        private DateTime lastListRead = DateTime.MinValue;
        private DateTime lastStatus = DateTime.MinValue;
        private DateTime lastAcctWrite = DateTime.MinValue;
        private DateTime lastReconnectResub = DateTime.MinValue;
        private int resubs;
        private int logLines;
        private TimeZoneInfo eastern;
        private readonly HashSet<Account> acctSubscribed = new HashSet<Account>();

        protected override void OnStateChange()
        {
            try
            {
                if (State == State.SetDefaults)
                {
                    Name = "LE_Feed";
                    Description = "Liquidity Engine bar feed without a chart: writes closed 5m / 1m bars, the 1m open, the contract and account balances to Documents\\NinjaTrader 8\\le_feed for the Python bot. Read-only.";
                }
                else if (State == State.Configure)
                {
                    // fallback in case State.Active never comes for an AddOn on this NinjaTrader version (see the top)
                    if (startTimer == null)
                        startTimer = new System.Threading.Timer(DelayedStart, null, 10000, System.Threading.Timeout.Infinite);
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
            catch (Exception e)
            {
                Say("LE_Feed: state " + State + " failed: " + e.Message);
            }
        }

        // NinjaTrader calls this for every open NinjaTrader window, the Control Center included, on every running add-on
        // (also right after F5): the start path that does not depend on which States an AddOn goes through.
        protected override void OnWindowCreated(System.Windows.Window window)
        {
            try
            {
                if (!terminated)
                    Start();
            }
            catch (Exception e)
            {
                Say("LE_Feed: start from the window event failed: " + e.Message);
            }
        }

        private void DelayedStart(object state)
        {
            try
            {
                if (!terminated)
                    Start();
            }
            catch (Exception e)
            {
                LogLine("delayed start failed: " + e.Message);
            }
        }

        private void Start()
        {
            lock (RunLock)
            {
                if (started || terminated)
                    return;
                if (running != null && running != this)
                    return;                                // another LE_Feed instance already feeds
                running = this;
                started = true;
            }
            startedUtc = DateTime.UtcNow;
            try
            {
                folder = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "le_feed");
                Directory.CreateDirectory(folder);
            }
            catch (Exception e)
            {
                // no folder = nothing can be written: say so in the Output window and let a later start path try again
                Say("LE_Feed: NOT started, cannot create the le_feed folder (" + e.Message + ")");
                lock (RunLock)
                {
                    started = false;
                    if (running == this)
                        running = null;
                }
                return;
            }
            listPath = Path.Combine(folder, "feed_instruments.txt");
            statusPath = Path.Combine(folder, "le_feed_status.txt");
            logPath = Path.Combine(folder, "le_feed_log.txt");
            accountsPath = Path.Combine(folder, "accounts.csv");
            ownerPath = Path.Combine(folder, "le_feed_owner.txt");
            lock (FileLock)
                SwapSmall(ownerPath, ownerToken + "\n");
            try
            {
                eastern = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            }
            catch (Exception)
            {
                eastern = null;                            // then every minute counts as "market open" for the self-heal
            }
            LE_FeedHub.HeadlessOn = true;
            LE_FeedHub.AccountsOn = true;
            try
            {
                NinjaTrader.Cbi.Connection.ConnectionStatusUpdate += OnConnectionStatus;
                connSubscribed = true;
            }
            catch (Exception e)
            {
                LogLine("connection events not available (" + e.Message + "): the 3-minute self-heal still runs");
            }
            Say("LE_Feed: started, writing bars to " + folder + " (no chart needed)");
            WriteStatus(DateTime.UtcNow, PriceConnected());    // proof of life at once, before the first bar
            lastStatus = DateTime.UtcNow;
            timer = new System.Threading.Timer(OnTimer, null, 1000, TickMs);
        }

        // a line in NinjaTrader's Output window (New > NinjaScript Output) and in le_feed_log.txt; never throws
        private void Say(string text)
        {
            LogLine(text);
            try
            {
                NinjaTrader.Code.Output.Process(text, PrintTo.OutputTab1);
            }
            catch (Exception)
            {
            }
        }

        // a newer LE_Feed (the assembly after an F5) wrote its own token: this older copy stops writing
        private bool Superseded()
        {
            try
            {
                if (ownerPath == null || !File.Exists(ownerPath))
                    return false;
                string t = File.ReadAllText(ownerPath).Trim();
                return t.Length > 0 && t != ownerToken;
            }
            catch (Exception)
            {
                return false;                              // unreadable for a moment: keep going
            }
        }

        private void Stop()
        {
            lock (RunLock)
            {
                if (stopped)
                    return;                                // a takeover stop, then State.Terminated: once is enough
                stopped = true;
            }
            terminated = true;
            try
            {
                if (startTimer != null)
                {
                    startTimer.Dispose();
                    startTimer = null;
                }
            }
            catch (Exception)
            {
            }
            if (!started)
                return;
            try
            {
                if (timer != null)
                {
                    timer.Dispose();
                    timer = null;
                }
            }
            catch (Exception)
            {
            }
            try
            {
                if (connSubscribed)
                    NinjaTrader.Cbi.Connection.ConnectionStatusUpdate -= OnConnectionStatus;
            }
            catch (Exception)
            {
            }
            lock (Gate)
            {
                foreach (FeedInst i in insts)
                    Unsubscribe(i);
                insts.Clear();
                try
                {
                    foreach (Account a in acctSubscribed)
                    {
                        try
                        {
                            a.AccountItemUpdate -= OnAccountItemUpdate;
                        }
                        catch (Exception)
                        {
                        }
                    }
                    acctSubscribed.Clear();
                }
                catch (Exception)
                {
                }
            }
            lock (RunLock)
            {
                if (running == this)
                {
                    running = null;
                    LE_FeedHub.Clear();
                }
            }
            Say("LE_Feed: stopped");
        }

        // ------------------------------------------------------------------ housekeeping (a pool thread, every 15 s)
        private void OnTimer(object state)
        {
            if (terminated || !System.Threading.Monitor.TryEnter(Gate))
                return;
            try
            {
                DateTime now = DateTime.UtcNow;
                if (Superseded())
                {
                    Say("LE_Feed: a newer LE_Feed took over (NinjaScript recompiled): this older copy stops");
                    Stop();
                    return;
                }
                if ((now - lastListRead).TotalSeconds >= ListEverySeconds || listText == null)
                {
                    lastListRead = now;
                    ReadInstruments();
                }
                bool connected = PriceConnected();
                bool reconnect = reconnectPending && (now - lastReconnectResub).TotalSeconds >= 30;
                if (reconnect)
                {
                    reconnectPending = false;
                    lastReconnectResub = now;
                }
                bool open = MarketShouldBeOpen(now) && MarketShouldBeOpen(now.AddSeconds(-StaleSeconds - 60));
                foreach (FeedInst i in insts)
                {
                    try
                    {
                        if (!connected)
                            continue;
                        if (!i.Subscribed)
                        {
                            if ((now - i.LastResubUtc).TotalSeconds >= ResubGapSeconds || i.LastResubUtc == DateTime.MinValue)
                                Subscribe(i, i.LastResubUtc == DateTime.MinValue ? "start" : "retry");
                        }
                        else if (reconnect)
                        {
                            Resubscribe(i, "connection back");
                        }
                        else if (Failed(i) && (now - i.LastResubUtc).TotalSeconds >= ResubGapSeconds)
                        {
                            Resubscribe(i, "the last request failed");
                        }
                        else if (open && (now - i.LastNew1mUtc).TotalSeconds >= StaleSeconds
                                 && (now - i.LastResubUtc).TotalSeconds >= StaleGap(i))
                        {
                            i.StaleStreak++;
                            Resubscribe(i, "no new 1-minute bar for " + (int)(now - i.LastNew1mUtc).TotalMinutes + " min");
                        }
                    }
                    catch (Exception e)
                    {
                        LogLine(i.Name + ": " + e.Message);
                    }
                }
                if ((now - lastStatus).TotalSeconds >= 60)
                {
                    lastStatus = now;
                    WriteStatus(now, connected);
                }
                if ((now - lastAcctWrite).TotalSeconds >= 60 || (acctDue && (now - lastAcctWrite).TotalSeconds >= 5))
                {
                    acctDue = false;
                    lastAcctWrite = now;
                    WriteAccountsFile();
                }
            }
            catch (Exception e)
            {
                LogLine("timer: " + e.Message);
            }
            finally
            {
                System.Threading.Monitor.Exit(Gate);
            }
        }

        // 2, 4, 8, 16, then 30 minutes between stale re-requests while no live bar comes in between (a holiday or an early
        // close the market hours below do not know): a live bar resets it to 2 minutes
        private static int StaleGap(FeedInst i)
        {
            if (i.LastLiveBarUtc > i.LastResubUtc)
                i.StaleStreak = 0;
            int gap = ResubGapSeconds << Math.Min(i.StaleStreak, 4);
            return Math.Min(gap, 1800);
        }

        private static bool Failed(FeedInst i)
        {
            return (i.S5 != null && i.S5.Failed) || (i.S1 != null && i.S1.Failed);
        }

        // CME index futures: Sunday 18:00 ET to Friday 17:00 ET, a break 17:00-18:00 ET every day (holidays not modelled:
        // at worst one harmless re-request every 2 minutes on a holiday)
        private bool MarketShouldBeOpen(DateTime utc)
        {
            if (eastern == null)
                return true;
            DateTime et = TimeZoneInfo.ConvertTimeFromUtc(utc, eastern);
            int mod = et.Hour * 60 + et.Minute;
            switch (et.DayOfWeek)
            {
                case DayOfWeek.Saturday:
                    return false;
                case DayOfWeek.Sunday:
                    return mod >= 18 * 60;
                case DayOfWeek.Friday:
                    return mod < 17 * 60;
                default:
                    return mod < 17 * 60 || mod >= 18 * 60;
            }
        }

        private static bool PriceConnected()
        {
            try
            {
                lock (NinjaTrader.Cbi.Connection.Connections)
                {
                    foreach (Connection c in NinjaTrader.Cbi.Connection.Connections)
                        if (c.PriceStatus == ConnectionStatus.Connected)
                            return true;
                }
            }
            catch (Exception)
            {
            }
            return false;
        }

        private void OnConnectionStatus(object sender, ConnectionStatusEventArgs e)
        {
            try
            {
                // never request on NinjaTrader's event thread: flag it and wake the timer
                if (e.PriceStatus == ConnectionStatus.Connected && e.PreviousPriceStatus != ConnectionStatus.Connected)
                {
                    reconnectPending = true;
                    System.Threading.Timer t = timer;
                    if (t != null)
                        t.Change(3000, TickMs);
                }
            }
            catch (Exception)
            {
            }
        }

        // ------------------------------------------------------------------ the instrument list
        private void ReadInstruments()
        {
            string text = "";
            try
            {
                if (File.Exists(listPath))
                    text = File.ReadAllText(listPath);
            }
            catch (Exception e)
            {
                LogLine("cannot read feed_instruments.txt (" + e.Message + "): keeping the current list");
                if (listText != null)
                    return;
            }
            List<string> names = new List<string>();
            foreach (string raw in text.Replace("\r", "").Split('\n'))
            {
                string n = raw.Trim();
                if (n.Length == 0 || n.StartsWith("#") || n.IndexOf(',') >= 0 || n.IndexOf(';') >= 0)
                    continue;
                if (!names.Contains(n, StringComparer.OrdinalIgnoreCase))
                    names.Add(n);
                if (names.Count >= MaxInstruments)
                    break;
            }
            if (names.Count == 0)
                names.Add(DefaultInstrument);
            string key = string.Join("\n", names.ToArray());
            if (key == listText)
                return;
            listText = key;
            LogLine("instruments: " + string.Join(", ", names.ToArray()));
            // drop the ones no longer listed (or replaced by another contract of the same root: the roll)
            for (int k = insts.Count - 1; k >= 0; k--)
            {
                if (!names.Contains(insts[k].Name, StringComparer.OrdinalIgnoreCase))
                {
                    LogLine(insts[k].Name + ": no longer listed, stopped");
                    Unsubscribe(insts[k]);
                    insts.RemoveAt(k);
                }
            }
            foreach (string n in names)
            {
                bool have = false;
                foreach (FeedInst i in insts)
                    if (string.Equals(i.Name, n, StringComparison.OrdinalIgnoreCase))
                        have = true;
                if (have)
                    continue;
                Instrument ins = null;
                try
                {
                    ins = NinjaTrader.Cbi.Instrument.GetInstrument(n);
                }
                catch (Exception e)
                {
                    LogLine(n + ": instrument lookup failed: " + e.Message);
                }
                if (ins == null)
                {
                    LogLine(n + ": NinjaTrader does not know this instrument (check the name, e.g. MNQ 12-26)");
                    continue;
                }
                string root = ins.MasterInstrument.Name;
                bool clash = false;
                foreach (FeedInst i in insts)
                    if (string.Equals(i.Root, root, StringComparison.OrdinalIgnoreCase))
                        clash = true;
                if (clash)
                {
                    LogLine(n + ": another " + root + " contract is listed first; one contract per root, " + n + " skipped");
                    continue;
                }
                FeedInst it = new FeedInst { Feed = this, Name = n, Root = root, Instrument = ins };
                it.S5 = new FeedSeries { Feed = this, Owner = it, Minutes = 5, Days = Days5m, MaxBars = MaxBars5m };
                it.S5.FilePath = Path.Combine(folder, root + "_5m.csv");
                it.S1 = new FeedSeries { Feed = this, Owner = it, Minutes = 1, Days = Days1m, MaxBars = MaxBars1m };
                it.S1.FilePath = Path.Combine(folder, root + "_1m.csv");
                it.OpenPath = Path.Combine(folder, root + "_1m_open.csv");
                it.InstPath = Path.Combine(folder, root + "_instrument.txt");
                insts.Add(it);
            }
        }

        // ------------------------------------------------------------------ subscribe / re-subscribe
        private void Subscribe(FeedInst i, string why)
        {
            i.LastResubUtc = DateTime.UtcNow;
            i.LastNew1mUtc = DateTime.UtcNow;              // the stale clock starts at the request
            DropSeries(i.S5);                              // a half-done earlier attempt never leaves a request behind
            DropSeries(i.S1);
            try
            {
                File.WriteAllText(i.InstPath, i.Instrument.FullName);
            }
            catch (Exception e)
            {
                LogLine("cannot write " + i.Root + "_instrument.txt: " + e.Message);
            }
            Request(i.S5);
            Request(i.S1);
            if (i.Md == null)
            {
                try
                {
                    i.Md = new MarketData(i.Instrument);
                    i.Md.Update += i.OnMarketData;
                }
                catch (Exception e)
                {
                    i.Md = null;
                    LogLine(i.Name + ": market data subscription failed (" + e.Message + "): no " + i.Root + "_1m_open.csv");
                }
            }
            i.Subscribed = true;
            LogLine(i.Name + ": bars requested (" + why + ")");
        }

        private void Resubscribe(FeedInst i, string why)
        {
            resubs++;
            Say("LE_Feed: " + i.Name + ": RE-SUBSCRIBE #" + resubs + " (" + why + ")");
            DropSeries(i.S5);
            DropSeries(i.S1);
            DropMarketData(i);
            Subscribe(i, "re-subscribe");
        }

        private void Unsubscribe(FeedInst i)
        {
            DropSeries(i.S5);
            DropSeries(i.S1);
            DropMarketData(i);
            i.Subscribed = false;
        }

        private void DropMarketData(FeedInst i)
        {
            MarketData md = i.Md;
            i.Md = null;
            if (md == null)
                return;
            try
            {
                md.Update -= i.OnMarketData;
            }
            catch (Exception)
            {
            }
            try
            {
                IDisposable d = md as IDisposable;
                if (d != null)
                    d.Dispose();
            }
            catch (Exception)
            {
            }
        }

        private void DropSeries(FeedSeries s)
        {
            if (s == null)
                return;
            BarsRequest old;
            lock (s.Sync)
            {
                old = s.Req;
                s.Req = null;
                s.Ready = false;
                s.Gen++;
            }
            if (old == null)
                return;
            try
            {
                old.Update -= s.OnUpdate;
            }
            catch (Exception)
            {
            }
            try
            {
                IDisposable d = old as IDisposable;
                if (d != null)
                    d.Dispose();
            }
            catch (Exception)
            {
            }
        }

        private void Request(FeedSeries s)
        {
            int gen;
            BarsRequest req;
            lock (s.Sync)
            {
                s.Gen++;
                gen = s.Gen;
                s.Ready = false;
                s.Failed = false;
                req = new BarsRequest(s.Owner.Instrument, DateTime.Now.AddDays(-s.Days), DateTime.Now);
                req.BarsPeriod = new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = s.Minutes };
                TradingHours th = null;
                try
                {
                    th = NinjaTrader.Data.TradingHours.Get(TradingHoursName);
                }
                catch (Exception)
                {
                }
                if (th == null)
                    th = s.Owner.Instrument.MasterInstrument.TradingHours;
                req.TradingHours = th;
                s.Req = req;
            }
            req.Update += s.OnUpdate;
            FeedSeries ser = s;
            req.Request(new Action<BarsRequest, ErrorCode, string>(delegate(BarsRequest b, ErrorCode code, string msg)
            {
                SafeLoaded(ser, gen, b, code, msg);
            }));
        }

        // ------------------------------------------------------------------ history (the request's callback)
        private void SafeLoaded(FeedSeries s, int gen, BarsRequest b, ErrorCode code, string msg)
        {
            try
            {
                if (code != ErrorCode.NoError)
                {
                    lock (s.Sync)
                        if (gen == s.Gen)
                            s.Failed = true;
                    Say("LE_Feed: " + s.Owner.Name + " " + s.Minutes + "m: request failed: " + code + " " + msg);
                    return;
                }
                int n = 0;
                bool ok = false;
                lock (s.Sync)
                {
                    if (gen != s.Gen || s.Req == null)
                        return;                            // an old request: a newer one is on its way
                    Bars bars = b.Bars;
                    int count = bars.Count;
                    int lastClosed = count - 2;
                    if (count > 0 && CloseUtc(bars.GetTime(count - 1)) <= DateTime.UtcNow.AddSeconds(-90))
                        lastClosed = count - 1;            // market closed: the last bar is done too
                    int first = Math.Max(0, lastClosed - s.MaxBars + 1);
                    StringBuilder sb = new StringBuilder(Math.Max(0, lastClosed - first + 1) * 48 + 64);
                    sb.Append(Header).Append('\n');
                    long last = long.MinValue;
                    for (int k = first; k <= lastClosed; k++)
                    {
                        long open = OpenUnix(bars.GetTime(k), s.Minutes);
                        if (open <= last)
                            continue;
                        last = open;
                        sb.Append(Line(bars, k, open)).Append('\n');
                        n++;
                    }
                    lock (FileLock)
                        ok = Swap(s.FilePath, sb.ToString());
                    if (ok)
                    {
                        s.LinesInFile = n;
                        s.LastOpen = last;
                        s.NextIndex = Math.Max(0, lastClosed + 1);
                        s.Ready = true;
                        if (s.Minutes == 1)
                            s.Owner.LastNew1mUtc = DateTime.UtcNow;
                        LE_FeedHub.Cover(s.Owner.Root);
                    }
                    else
                        s.Failed = true;
                }
                string done = s.Owner.Name + " " + s.Minutes + "m: " + (ok ? n + " bars written to " + Path.GetFileName(s.FilePath) + "; appending each new bar" : "history NOT written");
                if (!historyAnnounced || !ok)
                {
                    historyAnnounced = historyAnnounced || ok;
                    Say("LE_Feed: " + done);               // the first history (and every failure) also in the Output window
                }
                else
                    LogLine(done);
            }
            catch (Exception e)
            {
                try
                {
                    lock (s.Sync)
                        if (gen == s.Gen)
                            s.Failed = true;
                }
                catch (Exception)
                {
                }
                LogLine(s.Owner.Name + " " + s.Minutes + "m: history failed: " + e.Message);
            }
        }

        // ------------------------------------------------------------------ live bars (every tick: cheap unless a bar closed)
        private void SafeUpdate(FeedSeries s)
        {
            // never wait on NinjaTrader's data thread: while the history is being written (the lock is busy) this tick is
            // skipped; the next one catches up, since the scan starts at NextIndex
            if (!System.Threading.Monitor.TryEnter(s.Sync))
                return;
            try
            {
                {
                    if (!s.Ready || s.Req == null)
                        return;
                    Bars bars = s.Req.Bars;
                    int count = bars.Count;
                    if (count < s.NextIndex)
                        s.NextIndex = 0;                   // the series was rebuilt: the time check below skips bars already written
                    for (int k = s.NextIndex; k < count - 1; k++)     // bar k is closed once bar k+1 exists
                    {
                        long open = OpenUnix(bars.GetTime(k), s.Minutes);
                        if (open <= s.LastOpen)
                            continue;
                        s.LastOpen = open;
                        string line = Line(bars, k, open);
                        lock (FileLock)
                        {
                            try
                            {
                                File.AppendAllText(s.FilePath, line + "\n");
                                s.LinesInFile++;
                            }
                            catch (Exception e)
                            {
                                LogLine(Path.GetFileName(s.FilePath) + ": append failed (" + e.Message + "); this bar is missing");
                                continue;
                            }
                            if (s.LinesInFile > s.MaxBars + TrimEvery)
                                Trim(s);
                        }
                        if (s.Minutes == 1)
                        {
                            s.Owner.LastNew1mUtc = DateTime.UtcNow;
                            s.Owner.LastLiveBarUtc = s.Owner.LastNew1mUtc;
                        }
                    }
                    if (count - 1 > s.NextIndex)
                        s.NextIndex = count - 1;
                }
            }
            catch (Exception e)
            {
                LogLine(s.Owner.Name + " " + s.Minutes + "m update: " + e.Message);
            }
            finally
            {
                System.Threading.Monitor.Exit(s.Sync);
            }
        }

        // the first trade of every new minute -> <ROOT>_1m_open.csv (one line, swapped in whole), as LE_BarFeed.OnMarketData
        private void SafeMarketData(FeedInst i, MarketDataEventArgs e)
        {
            try
            {
                if (e.MarketDataType != MarketDataType.Last)
                    return;
                DateTime utc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(e.Time, DateTimeKind.Unspecified),
                                                             NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);
                long secs = (utc.Ticks - EpochTicks) / TimeSpan.TicksPerSecond;
                long minute = secs - secs % 60;
                if (minute <= i.LastOpenMinute)
                    return;
                i.LastOpenMinute = minute;
                string line = minute.ToString(CultureInfo.InvariantCulture) + "," + e.Price.ToString("0.########", CultureInfo.InvariantCulture) + "\n";
                lock (FileLock)
                    SwapSmall(i.OpenPath, line);
            }
            catch (Exception)
            {
            }
        }

        // ------------------------------------------------------------------ file helpers (as LE_BarFeed)
        private static DateTime CloseUtc(DateTime closeLocal)
        {
            return TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(closeLocal, DateTimeKind.Unspecified),
                                                 NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);
        }

        // NinjaTrader stamps minute bars with their CLOSE time in its display time zone: to UTC, then back one bar to the OPEN
        private static long OpenUnix(DateTime closeLocal, int minutes)
        {
            return (CloseUtc(closeLocal).Ticks - EpochTicks) / TimeSpan.TicksPerSecond - 60L * minutes;
        }

        private static string Line(Bars b, int k, long open)
        {
            CultureInfo c = CultureInfo.InvariantCulture;
            return open.ToString(c) + "," + b.GetOpen(k).ToString("0.########", c) + "," + b.GetHigh(k).ToString("0.########", c) + ","
                 + b.GetLow(k).ToString("0.########", c) + "," + b.GetClose(k).ToString("0.########", c) + ","
                 + ((double)b.GetVolume(k)).ToString("0.########", c);
        }

        private void Trim(FeedSeries s)
        {
            try
            {
                string[] lines = File.ReadAllLines(s.FilePath);
                int keep = Math.Min(s.MaxBars, lines.Length);
                StringBuilder sb = new StringBuilder(keep * 48 + 64);
                sb.Append(Header).Append('\n');
                for (int k = lines.Length - keep; k < lines.Length; k++)
                    if (lines[k].Length > 0 && lines[k] != Header)
                        sb.Append(lines[k]).Append('\n');
                s.LinesInFile = Swap(s.FilePath, sb.ToString()) ? keep : s.MaxBars;
            }
            catch (Exception e)
            {
                LogLine(Path.GetFileName(s.FilePath) + ": trim failed (" + e.Message + "); will try again later");
                s.LinesInFile = s.MaxBars;
            }
        }

        // write next to the file, then swap it in, so the bot never reads a half-written file
        private bool Swap(string path, string text)
        {
            string tmp = path + ".tmp";
            try
            {
                File.WriteAllText(tmp, text);
                if (File.Exists(path))
                    File.Replace(tmp, path, null);
                else
                    File.Move(tmp, path);
                return true;
            }
            catch (Exception)
            {
                try
                {
                    File.Copy(tmp, path, true);            // the bot had the file open for reading: overwrite in place
                    File.Delete(tmp);
                    return true;
                }
                catch (Exception e2)
                {
                    LogLine("could not write " + Path.GetFileName(path) + ": " + e2.Message);
                    return false;
                }
            }
        }

        private void SwapSmall(string path, string text)
        {
            string tmp = path + ".tmp";
            try
            {
                File.WriteAllText(tmp, text);
                if (File.Exists(path))
                    File.Replace(tmp, path, null);
                else
                    File.Move(tmp, path);
            }
            catch (Exception)
            {
                try
                {
                    File.Copy(tmp, path, true);
                    File.Delete(tmp);
                }
                catch (Exception)
                {
                }
            }
        }

        private void WriteStatus(DateTime now, bool connected)
        {
            try
            {
                CultureInfo c = CultureInfo.InvariantCulture;
                long last1 = long.MinValue;
                List<string> names = new List<string>();
                foreach (FeedInst i in insts)
                {
                    names.Add(i.Name);
                    if (i.S1 != null && i.S1.LastOpen > last1)
                        last1 = i.S1.LastOpen;
                }
                string line = ((now.Ticks - EpochTicks) / TimeSpan.TicksPerSecond).ToString(c) + ",source=addon,instruments="
                            + string.Join(";", names.ToArray()) + ",last_1m=" + (last1 == long.MinValue ? "" : last1.ToString(c))
                            + ",resubs=" + resubs.ToString(c) + ",connected=" + (connected ? "1" : "0")
                            + ",started=" + ((startedUtc.Ticks - EpochTicks) / TimeSpan.TicksPerSecond).ToString(c) + "\n";
                lock (FileLock)
                    SwapSmall(statusPath, line);
            }
            catch (Exception e)
            {
                LogLine("status not written: " + e.Message);
            }
        }

        // le_feed_log.txt: one line per event, local PC time; trimmed to the last 300 lines when it passes 200 KB
        private void LogLine(string text)
        {
            try
            {
                if (logPath == null)
                    return;
                string line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture) + " " + text.Replace("\r", " ").Replace("\n", " ") + "\r\n";
                lock (FileLock)
                {
                    File.AppendAllText(logPath, line);
                    logLines++;
                    if (logLines % 50 == 0)
                    {
                        FileInfo fi = new FileInfo(logPath);
                        if (fi.Exists && fi.Length > 200 * 1024)
                        {
                            string[] all = File.ReadAllLines(logPath);
                            int keep = Math.Min(300, all.Length);
                            File.WriteAllLines(logPath, all.Skip(all.Length - keep).ToArray());
                        }
                    }
                }
            }
            catch (Exception)
            {
            }
        }

        // ------------------------------------------------------------------ accounts.csv (as LE_BarFeed, every account)
        private void OnAccountItemUpdate(object sender, AccountItemEventArgs e)
        {
            try
            {
                if (!acctDue)
                {
                    acctDue = true;                        // the timer writes it (at most every 5 s), never this event thread
                    System.Threading.Timer t = timer;
                    if (t != null && (DateTime.UtcNow - lastAcctWrite).TotalSeconds >= 5)
                        t.Change(200, TickMs);
                }
            }
            catch (Exception)
            {
            }
        }

        private static string AcctValue(Account a, AccountItem item)
        {
            try
            {
                double v = a.Get(item, Currency.UsDollar);
                if (double.IsNaN(v) || double.IsInfinity(v))
                    return "";
                return v.ToString("0.00", CultureInfo.InvariantCulture);
            }
            catch (Exception)
            {
                return "";
            }
        }

        private void WriteAccountsFile()
        {
            try
            {
                long now = (DateTime.UtcNow.Ticks - EpochTicks) / TimeSpan.TicksPerSecond;
                StringBuilder sb = new StringBuilder(256);
                sb.Append("name,time,cash,realized,unrealized,netliq\n");
                List<Account> seen = new List<Account>();
                lock (NinjaTrader.Cbi.Account.All)
                {
                    foreach (Account a in NinjaTrader.Cbi.Account.All)
                        seen.Add(a);
                }
                foreach (Account a in seen)
                {
                    string name;
                    try
                    {
                        name = a.Name;
                    }
                    catch (Exception)
                    {
                        continue;
                    }
                    if (string.IsNullOrEmpty(name))
                        continue;
                    if (!acctSubscribed.Contains(a))
                    {
                        try
                        {
                            a.AccountItemUpdate += OnAccountItemUpdate;
                            acctSubscribed.Add(a);
                        }
                        catch (Exception)
                        {
                        }
                    }
                    sb.Append(name.Replace(",", " ")).Append(',').Append(now.ToString(CultureInfo.InvariantCulture)).Append(',')
                      .Append(AcctValue(a, AccountItem.CashValue)).Append(',')
                      .Append(AcctValue(a, AccountItem.RealizedProfitLoss)).Append(',')
                      .Append(AcctValue(a, AccountItem.UnrealizedProfitLoss)).Append(',')
                      .Append(AcctValue(a, AccountItem.NetLiquidation)).Append('\n');
                }
                lock (FileLock)
                    SwapSmall(accountsPath, sb.ToString());
            }
            catch (Exception e)
            {
                LogLine("accounts.csv not written: " + e.Message);
            }
        }
    }
}
