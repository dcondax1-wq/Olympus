// Minimal stub of the NinjaTrader 8 API surface LE_TickRec.cs uses (documented AddOn / MarketData API), for a C# 5 compile check only.
using System;
namespace System.Windows { public class Window { } }
namespace NinjaTrader.Core
{
    public class GeneralOptionsT { public TimeZoneInfo TimeZoneInfo { get { return TimeZoneInfo.Local; } } }
    public static class Globals
    {
        public static string UserDataDir { get { return "/tmp/nt8"; } }
        public static GeneralOptionsT GeneralOptions { get { return new GeneralOptionsT(); } }
    }
}
namespace NinjaTrader.Cbi
{
    public class Instrument { public static Instrument GetInstrument(string name) { return new Instrument(); } }
}
namespace NinjaTrader.Data
{
    public enum MarketDataType { Ask, Bid, DailyHigh, DailyLow, DailyVolume, Last, LastClose, Opening, OpenInterest, Settlement, Unknown }
    public class MarketDataEventArgs : EventArgs
    {
        public double Ask { get; set; } public double Bid { get; set; } public double Price { get; set; }
        public DateTime Time { get; set; } public long Volume { get; set; } public MarketDataType MarketDataType { get; set; }
        public NinjaTrader.Cbi.Instrument Instrument { get; set; } public bool IsReset { get; set; }
    }
    public class MarketData { public MarketData(NinjaTrader.Cbi.Instrument i) { } public event EventHandler<MarketDataEventArgs> Update; public void Fire(MarketDataEventArgs e) { if (Update != null) Update(this, e); } }
}
namespace NinjaTrader.NinjaScript
{
    public enum State { SetDefaults, Configure, Active, DataLoaded, Historical, Transition, Realtime, Terminated }
    public abstract class NinjaScriptBase { public State State { get; set; } public string Name { get; set; } public string Description { get; set; } }
    public abstract class AddOnBase : NinjaScriptBase
    {
        protected virtual void OnStateChange() { }
        protected virtual void OnWindowCreated(System.Windows.Window window) { }
    }
}
