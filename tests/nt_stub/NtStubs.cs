// Hand-made stubs of the NinjaTrader 8 types LE_Feed.cs uses (signatures as in the NT8 Help Guide), for a C# 5 syntax and
// type check with mono mcs. Not the real API: it cannot prove NinjaTrader accepts the calls, only that the code is consistent.
using System;
using System.Collections.Generic;

namespace System.Windows { public class Window { } }

namespace NinjaTrader.Core
{
    public class GeneralOptionsStub { public TimeZoneInfo TimeZoneInfo { get { return TimeZoneInfo.Local; } } }
    public static class Globals
    {
        public static string UserDataDir { get { return "/tmp/le_ntstub/"; } }
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
        public static Instrument GetInstrument(string name) { return null; }
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
        public int Count { get { return 0; } }
        public DateTime GetTime(int i) { return DateTime.Now; }
        public double GetOpen(int i) { return 0; }
        public double GetHigh(int i) { return 0; }
        public double GetLow(int i) { return 0; }
        public double GetClose(int i) { return 0; }
        public long GetVolume(int i) { return 0; }
        public double GetBid(int i) { return 0; }
        public double GetAsk(int i) { return 0; }
    }
    public class BarsUpdateEventArgs : EventArgs { public int MinIndex; public int MaxIndex; }
    public class BarsRequest : IDisposable
    {
        public BarsRequest(NinjaTrader.Cbi.Instrument instrument, DateTime fromLocal, DateTime toLocal) { }
        public BarsRequest(NinjaTrader.Cbi.Instrument instrument, int barsBack) { }
        public BarsPeriod BarsPeriod { get; set; }
        public TradingHours TradingHours { get; set; }
        public Bars Bars { get { return new Bars(); } }
        public event EventHandler<BarsUpdateEventArgs> Update;
        public void Request(Action<BarsRequest, NinjaTrader.Cbi.ErrorCode, string> callback) { if (Update != null) { } }
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
