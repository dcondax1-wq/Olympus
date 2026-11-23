// LE_TickRec backfill driver stubs (day-ofprogram 2026-11-23): NtStubs.cs with a WORKING fake history server.
// Hand-made stubs of the NinjaTrader 8 types LE_Feed.cs uses (signatures as in the NT8 Help Guide), for a C# 5 syntax and
// type check with mono mcs. Not the real API: it cannot prove NinjaTrader accepts the calls, only that the code is consistent.
using System;
using System.Collections.Generic;

namespace System.Windows { public class Window { } }

namespace NinjaTrader.Core
{
    public class GeneralOptionsStub { public TimeZoneInfo TimeZoneInfo { get { return TimeZoneInfo.Utc; } } }
    public static class Globals
    {
        public static string UserDataDir { get { return Environment.GetEnvironmentVariable("LE_NTSTUB_DIR") ?? "/tmp/le_ntstub/"; } }
        public static GeneralOptionsStub GeneralOptions = new GeneralOptionsStub();
    }
}

namespace NinjaTrader.Code
{
    public static class Output { public static void Process(string message, NinjaTrader.NinjaScript.PrintTo printTo) { Console.WriteLine(message); } }
}

namespace NinjaTrader.Cbi
{
    public enum ConnectionStatus { Connected, Connecting, ConnectionLost, Disconnected, Disconnecting }
    public enum ErrorCode { NoError, UserAbort, Panic, LogOnFailed }
    public enum Currency { UsDollar, Euro }
    public enum AccountItem { CashValue, RealizedProfitLoss, UnrealizedProfitLoss, NetLiquidation }
    public enum LogLevel { Information, Warning, Error, Alert }
    public class TradingHoursRef { }
    public class MasterInstrument { public string Name { get; set; } public NinjaTrader.Data.TradingHours TradingHours { get; set; } }
    public class Instrument
    {
        public MasterInstrument MasterInstrument { get; set; }
        public string FullName { get; set; }
        public static List<string> Missing = new List<string>();
        public static Instrument GetInstrument(string name) { if (Missing.Contains(name)) return null; Instrument i = new Instrument(); i.FullName = name; return i; }
    }
    public class ConnectionStatusEventArgs : EventArgs
    {
        public ConnectionStatus Status { get; set; }
        public ConnectionStatus PriceStatus { get; set; }
        public ConnectionStatus PreviousStatus { get; set; }
        public ConnectionStatus PreviousPriceStatus { get; set; }
        public Connection Connection { get; set; }
    }
    public class Connection
    {
        public static List<Connection> Connections = new List<Connection>();
        public ConnectionStatus PriceStatus { get; set; }
        public ConnectionStatus Status { get; set; }
        public static event EventHandler<ConnectionStatusEventArgs> ConnectionStatusUpdate;
        public static void Fire() { if (ConnectionStatusUpdate != null) ConnectionStatusUpdate(null, null); }
    }
    public class AccountItemEventArgs : EventArgs { }
    public class Account
    {
        public static List<Account> All = new List<Account>();
        public string Name { get; set; }
        public event EventHandler<AccountItemEventArgs> AccountItemUpdate;
        public double Get(AccountItem item, Currency c) { if (AccountItemUpdate != null) { } return 0; }
    }
}

namespace NinjaTrader.Data
{
    public enum BarsPeriodType { Tick, Minute, Day }
    public enum MarketDataType { Ask, Bid, Last }
    public class BarsPeriod { public BarsPeriodType BarsPeriodType { get; set; } public int Value { get; set; } }
    public class TradingHours { public static TradingHours Get(string name) { return null; } }
    public class Bars
    {
        public List<DateTime> T = new List<DateTime>(); public List<double> P = new List<double>(); public List<long> V = new List<long>();
        public int Count { get { return T.Count; } }
        public DateTime GetTime(int i) { return T[i]; }
        public double GetOpen(int i) { return P[i]; }
        public double GetHigh(int i) { return P[i]; }
        public double GetLow(int i) { return P[i]; }
        public double GetClose(int i) { return P[i]; }
        public long GetVolume(int i) { return V[i]; }
        public double GetBid(int i) { return P[i] - 0.25; }
        public double GetAsk(int i) { return P[i]; }
    }
    public class BarsUpdateEventArgs : EventArgs { public int MinIndex; public int MaxIndex; }
    // fake history server: every weekday / Sunday-evening hour gets ticks; days older than Oldest get none
    public class BarsRequest : IDisposable
    {
        public static List<string> Log = new List<string>();
        public static DateTime Oldest = new DateTime(2000, 1, 1);
        public static bool Hang = false;
        private NinjaTrader.Cbi.Instrument ins; private DateTime from, to; private Bars bars = new Bars();
        public BarsRequest(NinjaTrader.Cbi.Instrument instrument, DateTime fromLocal, DateTime toLocal) { ins = instrument; from = fromLocal; to = toLocal; }
        public BarsRequest(NinjaTrader.Cbi.Instrument instrument, int barsBack) { ins = instrument; }
        public BarsPeriod BarsPeriod { get; set; }
        public TradingHours TradingHours { get; set; }
        public Bars Bars { get { return bars; } }
        public event EventHandler<BarsUpdateEventArgs> Update;
        public void Request(Action<BarsRequest, NinjaTrader.Cbi.ErrorCode, string> callback)
        {
            if (Update != null) { }
            Log.Add(ins.FullName + "|" + from.ToString("yyyy-MM-dd HH:mm") + "|" + to.ToString("yyyy-MM-dd HH:mm") + "|" + BarsPeriod.BarsPeriodType + BarsPeriod.Value);
            if (Hang) return;
            // ticks every 10 min from 1 h before to 1 h after the window (the add-on must keep only its ET day)
            if (from.Date >= Oldest)
                for (DateTime t = from.AddHours(-1); t < to.AddHours(1); t = t.AddMinutes(10))
                    if (t.DayOfWeek != DayOfWeek.Saturday) { bars.T.Add(t); bars.P.Add(21000 + t.Minute); bars.V.Add(2); }
            callback(this, NinjaTrader.Cbi.ErrorCode.NoError, "");
        }
        public void Dispose() { }
    }
    public class MarketDataEventArgs : EventArgs
    {
        public MarketDataType MarketDataType { get; set; }
        public double Price { get; set; }
        public DateTime Time { get; set; }
        public long Volume { get; set; }
        public double Bid { get; set; }
        public double Ask { get; set; }
    }
    public class MarketData
    {
        public MarketData(NinjaTrader.Cbi.Instrument instrument) { }
        public event EventHandler<MarketDataEventArgs> Update;
        public void Touch() { if (Update != null) { } }
    }
}

namespace NinjaTrader.NinjaScript
{
    public enum State { SetDefaults, Configure, Active, DataLoaded, Historical, Transition, Realtime, Terminated, Finalized }
    public enum PrintTo { OutputTab1, OutputTab2 }
    public class Series<T> { }
    // The members NinjaScriptBase shares with indicators: the name clashes (a property called Instrument, Bars, TradingHours,
    // BarsPeriod, Account) are the ones that bite inside an AddOn, so they are stubbed too.
    public abstract class NinjaScriptBase
    {
        public string Name { get; set; }
        public string Description { get; set; }
        public State State { get; set; }
        public NinjaTrader.Cbi.Instrument Instrument { get; set; }
        public NinjaTrader.Data.Bars Bars { get; set; }
        public NinjaTrader.Data.BarsPeriod BarsPeriod { get; set; }
        public NinjaTrader.Data.TradingHours TradingHours { get; set; }
        public NinjaTrader.Cbi.Account Account { get; set; }
        public void Print(object value) { Console.WriteLine(value); }
        protected virtual void OnStateChange() { }
        public void Drive(State s) { State = s; OnStateChange(); }
    }
    public abstract class AddOnBase : NinjaScriptBase
    {
        protected virtual void OnWindowCreated(System.Windows.Window window) { }
        protected virtual void OnWindowDestroyed(System.Windows.Window window) { }
        public void Window(System.Windows.Window w) { OnWindowCreated(w); }
    }
}
