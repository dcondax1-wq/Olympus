// Stubs of the NinjaTrader 8 types LE_Bridge.cs uses (signatures as in the NT8 Help Guide) + a tiny order simulator and a
// driver, so mono can run the REAL LE_Bridge.cs and the Python adapter (engine/nt_socket.py) can trade against it.
// Not the real API: it proves the C# 5 syntax, the protocol and the bridge's own logic, not NinjaTrader's behaviour.
// Simulated: market orders fill at the price at once; stop / limit work until "MOVE <price>" on stdin crosses them; an OCO
// fill cancels its partner; Flatten cancels the instrument's working orders and closes the position; a FLAT position is
// REMOVED from Account.Positions (as NinjaTrader does). stdin: "MOVE 25000.25", "QUIT".
using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;

namespace NinjaTrader.Core
{
    public static class Globals
    {
        public static string UserDataDir { get { return Environment.GetEnvironmentVariable("LE_NTSTUB_DIR") ?? "/tmp/le_ntstub_bridge/"; } }
        public static DateTime MaxDate { get { return DateTime.MaxValue; } }
    }
}

namespace NinjaTrader.Code
{
    public static class Output { public static void Process(string message, NinjaTrader.NinjaScript.PrintTo printTo) { Console.WriteLine(message); } }
}

namespace NinjaTrader.Cbi
{
    public enum ConnectionStatus { Connected, Connecting, ConnectionLost, Disconnected, Disconnecting }
    public enum OrderAction { Buy, BuyToCover, Sell, SellShort }
    public enum OrderType { Limit, Market, MIT, StopMarket, StopLimit }
    public enum OrderEntry { Automated, Manual }
    public enum TimeInForce { Day, Gtc }
    public enum MarketPosition { Flat, Long, Short }
    public enum OrderState { Accepted, Cancelled, CancelPending, CancelSubmitted, ChangePending, ChangeSubmitted, Filled, Initialized,
                             PartFilled, Rejected, Submitted, TriggerPending, Unknown, Working }
    public class CustomOrder { }
    public class Instrument
    {
        static readonly Dictionary<string, Instrument> All = new Dictionary<string, Instrument>();
        public string FullName { get; set; }
        public static Instrument GetInstrument(string name)
        {
            if (name == null || name.Split(' ').Length != 2) return null;
            lock (All)
            {
                Instrument i;
                if (!All.TryGetValue(name, out i)) { i = new Instrument(); i.FullName = name; All[name] = i; }
                return i;
            }
        }
    }
    public class ConnectionOptions { public string Name { get; set; } }
    public class Connection
    {
        public static List<Connection> Connections = new List<Connection>();
        public ConnectionOptions Options { get; set; }
        public ConnectionStatus Status { get; set; }
    }
    public class Order
    {
        public string Name { get; set; }
        public Instrument Instrument { get; set; }
        public OrderAction OrderAction { get; set; }
        public OrderType OrderType { get; set; }
        public OrderState OrderState { get; set; }
        public int Quantity { get; set; }
        public int Filled { get; set; }
        public double AverageFillPrice { get; set; }
        public double LimitPrice { get; set; }
        public double StopPrice { get; set; }
        public string Oco { get; set; }
        public int QuantityChanged { get; set; }
        public double LimitPriceChanged { get; set; }
        public double StopPriceChanged { get; set; }
    }
    public class Position
    {
        public Instrument Instrument { get; set; }
        public MarketPosition MarketPosition { get; set; }
        public int Quantity { get; set; }
        public double AveragePrice { get; set; }
    }
    public class Account
    {
        public static List<Account> All = new List<Account>();
        public static double Price = 25020.0;
        public string Name { get; set; }
        public List<Order> Orders = new List<Order>();
        public List<Position> Positions = new List<Position>();

        public Order CreateOrder(Instrument instrument, OrderAction action, OrderType orderType, OrderEntry orderEntry, TimeInForce tif,
                                 int quantity, double limitPrice, double stopPrice, string oco, string name, DateTime gtd, CustomOrder custom)
        {
            Order o = new Order();
            o.Instrument = instrument; o.OrderAction = action; o.OrderType = orderType; o.Quantity = quantity; o.LimitPrice = limitPrice;
            o.StopPrice = stopPrice; o.Oco = oco; o.Name = name; o.OrderState = OrderState.Initialized;
            return o;
        }
        public void Submit(IEnumerable<Order> orders)
        {
            lock (Orders)
            {
                foreach (Order o in orders)
                {
                    Orders.Add(o);
                    if (o.OrderType == OrderType.Market) Fill(o, Price);
                    else o.OrderState = OrderState.Working;
                }
            }
        }
        public void Change(IEnumerable<Order> orders)
        {
            foreach (Order o in orders)
            {
                if (o.QuantityChanged > 0) o.Quantity = o.QuantityChanged;
                if (o.LimitPriceChanged > 0) o.LimitPrice = o.LimitPriceChanged;
                if (o.StopPriceChanged > 0) o.StopPrice = o.StopPriceChanged;
            }
        }
        public void Cancel(IEnumerable<Order> orders)
        {
            foreach (Order o in orders)
                if (o.OrderState == OrderState.Working || o.OrderState == OrderState.Accepted) o.OrderState = OrderState.Cancelled;
        }
        public void Flatten(ICollection<Instrument> instruments)
        {
            lock (Orders)
            {
                foreach (Order o in Orders)
                    if (instruments.Contains(o.Instrument) && o.OrderState == OrderState.Working) o.OrderState = OrderState.Cancelled;
                foreach (Instrument i in instruments)
                {
                    Position p = Pos(i);
                    if (p == null) continue;
                    Order c = CreateOrder(i, p.MarketPosition == MarketPosition.Long ? OrderAction.Sell : OrderAction.Buy, OrderType.Market,
                                          OrderEntry.Manual, TimeInForce.Day, p.Quantity, 0, 0, "", "Close", DateTime.MaxValue, null);
                    Orders.Add(c);
                    Fill(c, Price);
                }
            }
        }
        Position Pos(Instrument i)
        {
            foreach (Position p in Positions) if (p.Instrument == i) return p;
            return null;
        }
        void Fill(Order o, double px)
        {
            o.Filled = o.Quantity; o.AverageFillPrice = px; o.OrderState = OrderState.Filled;
            int signed = (o.OrderAction == OrderAction.Buy || o.OrderAction == OrderAction.BuyToCover) ? o.Quantity : -o.Quantity;
            lock (Positions)
            {
                Position p = Pos(o.Instrument);
                int q = p == null ? 0 : (p.MarketPosition == MarketPosition.Long ? p.Quantity : -p.Quantity);
                int nq = q + signed;
                if (nq == 0) { if (p != null) Positions.Remove(p); }
                else
                {
                    if (p == null) { p = new Position(); p.Instrument = o.Instrument; p.AveragePrice = px; Positions.Add(p); }
                    p.MarketPosition = nq > 0 ? MarketPosition.Long : MarketPosition.Short; p.Quantity = Math.Abs(nq);
                }
            }
            if (!string.IsNullOrEmpty(o.Oco))
                foreach (Order x in Orders)
                    if (x != o && x.Oco == o.Oco && x.OrderState == OrderState.Working) x.OrderState = OrderState.Cancelled;
        }
        public static void Move(double price)
        {
            Price = price;
            foreach (Account a in All)
                lock (a.Orders)
                {
                    foreach (Order o in a.Orders.ToArray())
                    {
                        if (o.OrderState != OrderState.Working) continue;
                        bool buy = o.OrderAction == OrderAction.Buy;
                        if (o.OrderType == OrderType.StopMarket && ((buy && price >= o.StopPrice) || (!buy && price <= o.StopPrice))) a.Fill(o, o.StopPrice);
                        else if (o.OrderType == OrderType.Limit && ((buy && price <= o.LimitPrice) || (!buy && price >= o.LimitPrice))) a.Fill(o, o.LimitPrice);
                    }
                }
        }
    }
}

namespace NinjaTrader.NinjaScript
{
    public enum State { SetDefaults, Configure, Active, DataLoaded, Historical, Transition, Realtime, Terminated, Finalized }
    public enum PrintTo { OutputTab1, OutputTab2 }
    public abstract class NinjaScriptBase
    {
        public string Name { get; set; }
        public string Description { get; set; }
        public State State { get; set; }
        public NinjaTrader.Cbi.Instrument Instrument { get; set; }
        public NinjaTrader.Cbi.Account Account { get; set; }
        protected virtual void OnStateChange() { }
        public void Drive(State s) { State = s; OnStateChange(); }
    }
    public abstract class AddOnBase : NinjaScriptBase { }
}

public static class BridgeDriver
{
    public static int Main(string[] args)
    {
        string dir = NinjaTrader.Core.Globals.UserDataDir;
        Directory.CreateDirectory(Path.Combine(dir, "le_feed"));
        string port = Environment.GetEnvironmentVariable("LE_BRIDGE_PORT");
        if (port != null) File.WriteAllText(Path.Combine(Path.Combine(dir, "le_feed"), "bridge_port.txt"), port);
        foreach (string n in new string[] { "Sim101", "Sim102", "MFFUEVAL123" })
        {
            NinjaTrader.Cbi.Account a = new NinjaTrader.Cbi.Account(); a.Name = n; NinjaTrader.Cbi.Account.All.Add(a);
        }
        NinjaTrader.Cbi.Connection c = new NinjaTrader.Cbi.Connection();
        c.Options = new NinjaTrader.Cbi.ConnectionOptions(); c.Options.Name = "Tradovate"; c.Status = NinjaTrader.Cbi.ConnectionStatus.Connected;
        NinjaTrader.Cbi.Connection.Connections.Add(c);
        NinjaTrader.NinjaScript.AddOns.LE_Bridge b = new NinjaTrader.NinjaScript.AddOns.LE_Bridge();
        b.Drive(NinjaTrader.NinjaScript.State.SetDefaults);
        b.Drive(NinjaTrader.NinjaScript.State.Active);
        Console.WriteLine("READY " + b.Port);
        Console.Out.Flush();
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            if (line.StartsWith("MOVE ")) { NinjaTrader.Cbi.Account.Move(double.Parse(line.Substring(5), System.Globalization.CultureInfo.InvariantCulture)); Console.WriteLine("MOVED"); Console.Out.Flush(); }
            else if (line == "QUIT") break;
        }
        b.Drive(NinjaTrader.NinjaScript.State.Terminated);
        return 0;
    }
}
