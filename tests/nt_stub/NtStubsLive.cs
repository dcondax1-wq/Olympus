// Behaving stubs + a driver: runs LE_Feed's logic under mono (history, live bars, status, takeover). Not the real API.
using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;

namespace System.Windows { public class Window { } }

namespace NinjaTrader.Core
{
    public class GeneralOptionsStub { public TimeZoneInfo TimeZoneInfo { get { return TimeZoneInfo.Local; } } }
    public static class Globals
    {
        public static string UserDataDir = (Environment.GetEnvironmentVariable("LE_NTSTUB_DIR") ?? "/tmp/le_ntstub") + "/";
        public static GeneralOptionsStub GeneralOptions = new GeneralOptionsStub();
    }
}

namespace NinjaTrader.Code
{
    public static class Output
    {
        public static List<string> Lines = new List<string>();
        public static void Process(string message, NinjaTrader.NinjaScript.PrintTo printTo) { lock (Lines) Lines.Add(message); Console.WriteLine("OUTPUT> " + message); }
    }
}

namespace NinjaTrader.Cbi
{
    public enum ConnectionStatus { Connected, Connecting, ConnectionLost, Disconnected, Disconnecting }
    public enum ErrorCode { NoError, UserAbort, Panic, LogOnFailed }
    public enum Currency { UsDollar, Euro }
    public enum AccountItem { CashValue, RealizedProfitLoss, UnrealizedProfitLoss, NetLiquidation }
    public class MasterInstrument { public string Name { get; set; } public NinjaTrader.Data.TradingHours TradingHours { get; set; } }
    public class Instrument
    {
        public MasterInstrument MasterInstrument { get; set; }
        public string FullName { get; set; }
        public static Instrument GetInstrument(string name)
        {
            string[] p = name.Split(' ');
            return new Instrument { FullName = name, MasterInstrument = new MasterInstrument { Name = p[0] } };
        }
    }
    public class ConnectionStatusEventArgs : EventArgs
    {
        public ConnectionStatus PriceStatus { get; set; }
        public ConnectionStatus PreviousPriceStatus { get; set; }
    }
    public class Connection
    {
        public static List<Connection> Connections = new List<Connection> { new Connection { PriceStatus = ConnectionStatus.Connected } };
        public ConnectionStatus PriceStatus { get; set; }
        public static event EventHandler<ConnectionStatusEventArgs> ConnectionStatusUpdate;
        public static int Subscribers { get { return ConnectionStatusUpdate == null ? 0 : ConnectionStatusUpdate.GetInvocationList().Length; } }
    }
    public class AccountItemEventArgs : EventArgs { }
    public class Account
    {
        public static List<Account> All = new List<Account> { new Account { Name = "Sim101" }, new Account { Name = "MFFUEVAL123" } };
        public string Name { get; set; }
        public event EventHandler<AccountItemEventArgs> AccountItemUpdate;
        public double Get(AccountItem item, Currency c) { if (AccountItemUpdate != null) { } return 50000; }
    }
}

namespace NinjaTrader.Data
{
    public enum BarsPeriodType { Tick, Minute, Day }
    public enum MarketDataType { Ask, Bid, Last }
    public class BarsPeriod { public BarsPeriodType BarsPeriodType { get; set; } public int Value { get; set; } }
    public class TradingHours { public static TradingHours Get(string name) { return new TradingHours(); } }
    public class Bars
    {
        public List<DateTime> T = new List<DateTime>();
        public int Count { get { return T.Count; } }
        public DateTime GetTime(int i) { return T[i]; }
        public double GetOpen(int i) { return 100 + i; }
        public double GetHigh(int i) { return 101 + i; }
        public double GetLow(int i) { return 99 + i; }
        public double GetClose(int i) { return 100.25 + i; }
        public long GetVolume(int i) { return 10; }
    }
    public class BarsUpdateEventArgs : EventArgs { }
    public class BarsRequest : IDisposable
    {
        public static List<BarsRequest> All = new List<BarsRequest>();
        public BarsRequest(NinjaTrader.Cbi.Instrument instrument, DateTime fromLocal, DateTime toLocal) { }
        public BarsPeriod BarsPeriod { get; set; }
        public TradingHours TradingHours { get; set; }
        private readonly Bars bars = new Bars();
        public Bars Bars { get { return bars; } }
        public event EventHandler<BarsUpdateEventArgs> Update;
        public bool Disposed;
        public void Request(Action<BarsRequest, NinjaTrader.Cbi.ErrorCode, string> callback)
        {
            lock (All) All.Add(this);
            int m = BarsPeriod.Value;
            DateTime now = DateTime.Now;
            now = new DateTime(now.Year, now.Month, now.Day, now.Hour, now.Minute, 0);
            DateTime cur = now.AddMinutes(-(now.Minute % m));          // open of the forming bar
            for (int k = 10; k >= 0; k--)
                bars.T.Add(cur.AddMinutes(-m * k + m));                  // stamped with the CLOSE time
            callback(this, NinjaTrader.Cbi.ErrorCode.NoError, "");
        }
        public void AddBar()
        {
            bars.T.Add(bars.T[bars.T.Count - 1].AddMinutes(BarsPeriod.Value));
            if (Update != null) Update(this, new BarsUpdateEventArgs());
        }
        public void Dispose() { Disposed = true; }
    }
    public class MarketDataEventArgs : EventArgs
    {
        public MarketDataType MarketDataType { get; set; }
        public double Price { get; set; }
        public DateTime Time { get; set; }
    }
    public class MarketData
    {
        public static List<MarketData> All = new List<MarketData>();
        public MarketData(NinjaTrader.Cbi.Instrument instrument) { lock (All) All.Add(this); }
        public event EventHandler<MarketDataEventArgs> Update;
        public void Tick(double px) { if (Update != null) Update(this, new MarketDataEventArgs { MarketDataType = MarketDataType.Last, Price = px, Time = DateTime.Now }); }
    }
}

namespace NinjaTrader.NinjaScript
{
    public enum State { SetDefaults, Configure, Active, DataLoaded, Historical, Transition, Realtime, Terminated, Finalized }
    public enum PrintTo { OutputTab1, OutputTab2 }
    public class Series<T> { }
    public abstract class NinjaScriptBase
    {
        public string Name { get; set; }
        public string Description { get; set; }
        public State State { get; set; }
        public NinjaTrader.Cbi.Instrument Instrument { get; set; }
        public NinjaTrader.Data.Bars Bars { get; set; }
        public NinjaTrader.Data.TradingHours TradingHours { get; set; }
        public NinjaTrader.Cbi.Account Account { get; set; }
        public void Print(object value) { Console.WriteLine(value); }
        protected virtual void OnStateChange() { }
        public void Drive(State s) { State = s; OnStateChange(); }
    }
    public abstract class AddOnBase : NinjaScriptBase
    {
        protected virtual void OnWindowCreated(System.Windows.Window window) { }
        public void Window() { OnWindowCreated(new System.Windows.Window()); }
    }
}

public static class Driver
{
    static int fails;
    static void Check(string what, bool ok) { Console.WriteLine((ok ? "PASS " : "FAIL ") + what); if (!ok) fails++; }
    static string Dir { get { return Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "le_feed"); } }
    static string Read(string n) { string p = Path.Combine(Dir, n); return File.Exists(p) ? File.ReadAllText(p) : ""; }

    public static int Main()
    {
        if (Directory.Exists(Dir)) Directory.Delete(Dir, true);
        var a = new NinjaTrader.NinjaScript.AddOns.LE_Feed();
        a.Drive(NinjaTrader.NinjaScript.State.SetDefaults);
        Check("SetDefaults alone starts nothing", !File.Exists(Path.Combine(Dir, "le_feed_status.txt")));
        a.Window();                                    // the Control Center window event: no State.Active needed
        string st = Read("le_feed_status.txt");
        Check("status written at once on start: " + st.Trim(), st.Contains("source=addon") && st.Contains("started="));
        Check("Output window says started", NinjaTrader.Code.Output.Lines.Exists(l => l.Contains("LE_Feed: started")));
        Check("owner token written", Read("le_feed_owner.txt").Trim().Length == 32);
        a.Drive(NinjaTrader.NinjaScript.State.Active);  // a second start path: no second feed
        Thread.Sleep(2500);                            // first timer tick at 1 s: list, subscribe, history
        string m1 = Read("MNQ_1m.csv"), m5 = Read("MNQ_5m.csv");
        int n1 = m1.Trim().Split('\n').Length;
        Check("MNQ_1m.csv history written (" + n1 + " lines)", m1.StartsWith("time,open,high,low,close,volume") && n1 >= 10);
        Check("MNQ_5m.csv history written", m5.StartsWith("time,open") && m5.Trim().Split('\n').Length >= 10);
        Check("instrument file = MNQ 12-26", Read("MNQ_instrument.txt") == "MNQ 12-26");
        Check("one request per series (no double start)", NinjaTrader.Data.BarsRequest.All.Count == 2);
        Check("hub covers MNQ", NinjaTrader.NinjaScript.AddOns.LE_FeedHub.Covers("MNQ"));
        Check("accounts.csv lists both accounts", Read("accounts.csv").Contains("MFFUEVAL123,") && Read("accounts.csv").Contains("Sim101,"));
        // a live bar: the request gets one more bar -> the previous (now closed) bar is appended
        NinjaTrader.Data.BarsRequest r1 = NinjaTrader.Data.BarsRequest.All.Find(r => r.BarsPeriod.Value == 1);
        r1.AddBar();
        int n1b = Read("MNQ_1m.csv").Trim().Split('\n').Length;
        Check("a live 1m bar appended (" + n1 + " -> " + n1b + ")", n1b == n1 + 1);
        string[] lines = Read("MNQ_1m.csv").Trim().Split('\n');
        long t1 = long.Parse(lines[lines.Length - 1].Split(',')[0]), t0 = long.Parse(lines[lines.Length - 2].Split(',')[0]);
        Check("1m bar times step 60 s and are bar OPENs (" + t0 + " -> " + t1 + ")", t1 - t0 == 60 && t1 % 60 == 0);
        NinjaTrader.Data.MarketData.All[0].Tick(21000.25);
        Check("1m open written: " + Read("MNQ_1m_open.csv").Trim(), Read("MNQ_1m_open.csv").Contains(",21000.25"));
        // takeover: a newer copy (the assembly after F5) writes its own token; the old one stops on its next tick
        File.WriteAllText(Path.Combine(Dir, "le_feed_owner.txt"), Guid.NewGuid().ToString("N") + "\n");
        Thread.Sleep(16000);
        Check("older copy stopped after the takeover", NinjaTrader.Code.Output.Lines.Exists(l => l.Contains("took over")));
        Check("its bar requests disposed", NinjaTrader.Data.BarsRequest.All.TrueForAll(r => r.Disposed));
        Check("connection event unsubscribed", NinjaTrader.Cbi.Connection.Subscribers == 0);
        a.Drive(NinjaTrader.NinjaScript.State.Terminated);  // terminate after a takeover: harmless
        var b = new NinjaTrader.NinjaScript.AddOns.LE_Feed();
        b.Drive(NinjaTrader.NinjaScript.State.SetDefaults);
        b.Drive(NinjaTrader.NinjaScript.State.Active);
        Check("a new copy starts after the old one stopped", Read("le_feed_status.txt").Contains("source=addon"));
        b.Drive(NinjaTrader.NinjaScript.State.Terminated);
        Check("terminated cleanly", NinjaTrader.Code.Output.Lines.FindAll(l => l.Contains("LE_Feed: stopped")).Count == 2);
        // day-ops2: SHADOW mode (the hands-free roll): bars to le_feed\shadow, no hub cover, the chart's files untouched; then live
        string sh = Path.Combine(Dir, "shadow");
        File.WriteAllText(Path.Combine(Dir, "le_feed_mode.txt"), "shadow\n");
        File.WriteAllText(Path.Combine(Dir, "MNQ_1m.csv"), "time,open,high,low,close,volume\nCHART\n");
        File.WriteAllText(Path.Combine(Dir, "accounts.csv"), "CHART\n");
        var c = new NinjaTrader.NinjaScript.AddOns.LE_Feed();
        c.Drive(NinjaTrader.NinjaScript.State.SetDefaults);
        c.Drive(NinjaTrader.NinjaScript.State.Active);
        Thread.Sleep(2500);
        string ss = File.Exists(Path.Combine(sh, "le_feed_status.txt")) ? File.ReadAllText(Path.Combine(sh, "le_feed_status.txt")) : "";
        Check("shadow: status in le_feed\\shadow with mode=shadow and the build id: " + ss.Trim(), ss.Contains("mode=shadow") && ss.Contains(",v="));
        Check("shadow: bars written to le_feed\\shadow", File.Exists(Path.Combine(sh, "MNQ_1m.csv")) && File.ReadAllText(Path.Combine(sh, "MNQ_1m.csv")).Trim().Split('\n').Length >= 10);
        Check("shadow: the chart's MNQ_1m.csv and accounts.csv untouched", Read("MNQ_1m.csv").Contains("CHART") && Read("accounts.csv") == "CHART\n");
        Check("shadow: the hub covers nothing (LE_BarFeed keeps writing)", !NinjaTrader.NinjaScript.AddOns.LE_FeedHub.Covers("MNQ"));
        File.WriteAllText(Path.Combine(Dir, "le_feed_mode.txt"), "live\n");
        Thread.Sleep(16000);
        Check("live: the add-on now writes le_feed\\MNQ_1m.csv itself", !Read("MNQ_1m.csv").Contains("CHART") && Read("MNQ_1m.csv").Trim().Split('\n').Length >= 10);
        Check("live: the hub covers MNQ (the chart defers)", NinjaTrader.NinjaScript.AddOns.LE_FeedHub.Covers("MNQ"));
        Check("live: status back in le_feed with mode=live", Read("le_feed_status.txt").Contains("mode=live"));
        c.Drive(NinjaTrader.NinjaScript.State.Terminated);
        Console.WriteLine(fails == 0 ? "ALL PASS" : fails + " FAILED");
        return fails == 0 ? 0 : 1;
    }
}
