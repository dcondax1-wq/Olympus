// LE_Bridge - Liquidity Engine order bridge for NinjaTrader 8 (NinjaScript AddOn, PAPER PROTOTYPE, big-execution 2026-11-26)
//
// Replaces the Order Instruction FILE bridge (Documents\NinjaTrader 8\incoming + outgoing) with a localhost socket, for the
// Python adapter engine/nt_socket.py. Same order commands (the documented OIF lines the bot already builds and validates),
// executed through NinjaTrader's own Account API instead of NinjaTrader's folder watcher. Why: OneDrive / antivirus file
// locks, a watcher that can read an empty file, order files that must be withdrawn, outgoing\ wiped on a restart
// (research/writeups/execution-2026-11-26.md).
//
// Protocol: TCP 127.0.0.1:36975 (loopback only, never the network; port override: le_feed\bridge_port.txt). One UTF-8 line
// per request, one JSON line per answer:
//   PING                                          -> {"ok":true,"build":"...","t":<unix>}
//   OIF <req> <sent_ms> <ttl_ms> <line>|<line>..  -> {"ok":true,"id":"<req>","done":n} | {"ok":false,"id":..,"error":".."}
//   SNAP <account>                                -> {"ok":true,"t":..,"orders":{<name>:{"state","filled","avg","t"}},
//                                                     "positions":[{"instrument","side","qty","avg","t"}],
//                                                     "connections":{<name>:"CONNECTED"|"DISCONNECTED"},"accounts":[..]}
// OIF commands executed: PLACE, CHANGE, CANCEL, CLOSEPOSITION, FLATTENEVERYTHING (the five the bot uses). Anything else is
// refused. A command older than its TTL when it arrives is refused whole ("expired"), so an order can never run late.
//
// SAFETY: PaperOnly = true. PLACE / CLOSEPOSITION on an account that is not a NinjaTrader simulation account (Sim101,
// SimNNN, PlaybackNNN) is refused, and FLATTENEVERYTHING only flattens simulation accounts. Order names must start with "LE"
// (the bot's ids); CHANGE / CANCEL only touch such orders. Every NinjaTrader call sits in try/catch.
// Positions: NinjaTrader drops a position from Account.Positions when it goes flat, so the bridge remembers every
// instrument it has seen per account and reports it FLAT (with the time it went flat), the way outgoing\ kept a FLAT file.
//
// Install (only after the red team + the owner's yes): copy to Documents\NinjaTrader 8\bin\Custom\AddOns\, NinjaScript
// Editor, F5. Check: python -m engine.nt_socket --ping. It does nothing until the bot connects; the file bridge keeps
// working beside it (different adapter: "adapter": "nt-socket" in a Sim101 start config).
//
// UNVERIFIED (written without a NinjaTrader install; compiled with mono mcs -langversion:5 against tests/nt_stub/
// NtStubsBridge.cs, which checks the syntax and the protocol logic but not the real API). Check first if F5 shows an error:
//  1. Account.CreateOrder(Instrument, OrderAction, OrderType, OrderEntry, TimeInForce, int qty, double limit, double stop,
//     string oco, string name, DateTime gtd, CustomOrder) and Account.Submit / Change / Cancel (IEnumerable<Order>),
//     Account.Flatten(ICollection<Instrument>).
//  2. OrderAction.Sell opens a short when flat (the ATI does the same for OIF "SELL"); if NinjaTrader wants SellShort,
//     map it in Action().
//  3. Order.Name keeps the name given at CreateOrder across a NinjaTrader restart / reconnect (Tradovate).
//  4. Order.QuantityChanged / LimitPriceChanged / StopPriceChanged + Account.Change for CHANGE.
//  5. Calling the Account API from this add-on's socket thread (NinjaTrader examples call it from add-on threads; if it
//     complains, marshal through NinjaTrader.Core.Globals.RandomDispatcher.InvokeAsync).

#region Using declarations
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    public class LE_Bridge : AddOnBase
    {
        public const string Build = "le_bridge 2026-11-26 proto1";
        public const bool PaperOnly = true;
        public const int DefaultPort = 36975;
        private static readonly Regex SimName = new Regex("^(Sim|Playback)[0-9]+$");
        private static readonly long EpochTicks = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc).Ticks;
        private static readonly object Gate = new object();          // one command at a time across every client
        private static LE_Bridge running;                            // only one bridge per NinjaTrader (F5 makes a new copy)

        private TcpListener listener;
        private Thread acceptThread;
        private volatile bool stopping;
        private int port = DefaultPort;
        private readonly Dictionary<string, PosRec> pos = new Dictionary<string, PosRec>();      // account|instrument
        private readonly Dictionary<string, OrdRec> ords = new Dictionary<string, OrdRec>();     // account|name

        private class PosRec { public string Instrument; public string Side = "FLAT"; public int Qty; public double Avg; public double T; }
        private class OrdRec { public string State = ""; public int Filled; public double T; }

        protected override void OnStateChange()
        {
            try
            {
                if (State == State.SetDefaults)
                {
                    Name = "LE_Bridge";
                    Description = "Liquidity Engine order bridge (paper prototype): runs the bot's order commands through NinjaTrader's Account API over a localhost socket. Simulation accounts only.";
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
                Say("LE_Bridge: state " + State + " failed: " + e.Message);
            }
        }

        public void Start()
        {
            lock (Gate)
            {
                if (running != null && running != this)
                    running.Stop();                                  // an older copy (before an F5) gives the port back
                running = this;
            }
            stopping = false;
            try
            {
                string f = Path.Combine(Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "le_feed"), "bridge_port.txt");
                if (File.Exists(f))
                {
                    int p;
                    if (int.TryParse(File.ReadAllText(f).Trim(), out p) && p > 1024 && p < 65536)
                        port = p;
                }
            }
            catch (Exception)
            {
            }
            listener = new TcpListener(IPAddress.Loopback, port);
            listener.Start();
            acceptThread = new Thread(AcceptLoop);
            acceptThread.IsBackground = true;
            acceptThread.Start();
            Say("LE_Bridge: started " + Build + " on 127.0.0.1:" + port + (PaperOnly ? " (simulation accounts only)" : ""));
        }

        public void Stop()
        {
            stopping = true;
            try
            {
                if (listener != null)
                    listener.Stop();
            }
            catch (Exception)
            {
            }
            lock (Gate)
            {
                if (running == this)
                    running = null;
            }
        }

        public int Port { get { return port; } }

        private void AcceptLoop()
        {
            while (!stopping)
            {
                TcpClient c;
                try
                {
                    c = listener.AcceptTcpClient();
                }
                catch (Exception)
                {
                    if (stopping)
                        return;
                    Thread.Sleep(200);
                    continue;
                }
                Thread t = new Thread(Serve);
                t.IsBackground = true;
                t.Start(c);
            }
        }

        private void Serve(object o)
        {
            TcpClient c = (TcpClient)o;
            try
            {
                c.NoDelay = true;
                NetworkStream s = c.GetStream();
                StreamReader r = new StreamReader(s, new UTF8Encoding(false));
                StreamWriter w = new StreamWriter(s, new UTF8Encoding(false));
                w.NewLine = "\n";
                while (!stopping)
                {
                    string line = r.ReadLine();
                    if (line == null)
                        break;
                    string answer;
                    try
                    {
                        answer = Handle(line.Trim());
                    }
                    catch (Exception e)
                    {
                        answer = "{\"ok\":false,\"error\":" + Q("internal: " + e.Message) + "}";
                    }
                    w.WriteLine(answer);
                    w.Flush();
                }
            }
            catch (Exception)
            {
            }
            finally
            {
                try
                {
                    c.Close();
                }
                catch (Exception)
                {
                }
            }
        }

        // ------------------------------------------------------------------ commands
        public string Handle(string line)
        {
            if (line == "PING")
                return "{\"ok\":true,\"build\":" + Q(Build) + ",\"t\":" + N(Now()) + "}";
            if (line.StartsWith("SNAP "))
            {
                lock (Gate)
                {
                    return Snapshot(line.Substring(5).Trim());
                }
            }
            if (line.StartsWith("OIF "))
            {
                string[] p = line.Split(new char[] { ' ' }, 5);
                if (p.Length < 5)
                    return "{\"ok\":false,\"error\":\"bad OIF request\"}";
                string req = p[1];
                long sent, ttl;
                if (!long.TryParse(p[2], out sent) || !long.TryParse(p[3], out ttl))
                    return Fail(req, "bad OIF request header");
                double age = Now() * 1000.0 - sent;
                if (age > ttl)
                    return Fail(req, "expired (" + ((long)age).ToString(CultureInfo.InvariantCulture) + " ms > " + ttl.ToString(CultureInfo.InvariantCulture) + " ms)");
                string[] lines = p[4].Split('|');
                lock (Gate)
                {
                    foreach (string ln in lines)                     // check every line before running any of them
                    {
                        string bad = Check(ln);
                        if (bad != null)
                            return Fail(req, bad);
                    }
                    int done = 0;
                    foreach (string ln in lines)
                    {
                        string err = Run(ln);
                        if (err != null)
                            return Fail(req, "line " + (done + 1) + " of " + lines.Length + ": " + err + (done > 0 ? " (earlier lines ran)" : ""));
                        done++;
                    }
                    return "{\"ok\":true,\"id\":" + Q(req) + ",\"done\":" + done + "}";
                }
            }
            return "{\"ok\":false,\"error\":" + Q("unknown command") + "}";
        }

        private static string Fail(string req, string why)
        {
            return "{\"ok\":false,\"id\":" + Q(req) + ",\"error\":" + Q(why) + "}";
        }

        private string Check(string ln)
        {
            string[] f = ln.Split(';');
            if (f.Length != 13)
                return "not 13 fields: " + ln;
            string cmd = f[0];
            if (cmd == "PLACE" || cmd == "CLOSEPOSITION")
            {
                if (PaperOnly && !SimName.IsMatch(f[1]))
                    return "bridge is paper-only: account " + f[1] + " refused";
                if (FindAccount(f[1]) == null)
                    return "account " + f[1] + " not found in NinjaTrader";
            }
            if (cmd == "PLACE" && !f[10].StartsWith("LE"))
                return "order id must start with LE";
            if ((cmd == "CHANGE" || cmd == "CANCEL") && !f[10].StartsWith("LE"))
                return "only the bot's orders (LE...) may be changed or cancelled";
            if (cmd != "PLACE" && cmd != "CHANGE" && cmd != "CANCEL" && cmd != "CLOSEPOSITION" && cmd != "FLATTENEVERYTHING")
                return cmd + " is not supported by LE_Bridge";
            return null;
        }

        private string Run(string ln)
        {
            string[] f = ln.Split(';');
            string cmd = f[0];
            if (cmd == "PLACE")
            {
                Account a = FindAccount(f[1]);
                NinjaTrader.Cbi.Instrument ins = NinjaTrader.Cbi.Instrument.GetInstrument(BaseName(f[2]));
                if (ins == null)
                    return "instrument " + f[2] + " not found";
                if (FindOrder(a, f[10]) != null)
                    return "order id " + f[10] + " already used";
                OrderType ot;
                if (f[5] == "MARKET") ot = OrderType.Market;
                else if (f[5] == "LIMIT") ot = OrderType.Limit;
                else if (f[5] == "STOPMARKET") ot = OrderType.StopMarket;
                else if (f[5] == "STOPLIMIT") ot = OrderType.StopLimit;
                else return "order type " + f[5];
                Order o = a.CreateOrder(ins, Action(f[3]), ot, OrderEntry.Automated, f[8] == "GTC" ? TimeInForce.Gtc : TimeInForce.Day,
                                        Int(f[4]), Dbl(f[6]), Dbl(f[7]), f[9], f[10], NinjaTrader.Core.Globals.MaxDate, null);
                a.Submit(new Order[] { o });
                Remember(a.Name, ins.FullName);
                return null;
            }
            if (cmd == "CHANGE" || cmd == "CANCEL")
            {
                Order o = null;
                Account owner = null;
                foreach (Account a in Accounts())
                {
                    o = FindOrder(a, f[10]);
                    if (o != null) { owner = a; break; }
                }
                if (o == null)
                    return "order " + f[10] + " not found";
                if (cmd == "CANCEL")
                {
                    owner.Cancel(new Order[] { o });
                    return null;
                }
                if (Int(f[4]) > 0) o.QuantityChanged = Int(f[4]);
                if (Dbl(f[6]) > 0) o.LimitPriceChanged = Dbl(f[6]);
                if (Dbl(f[7]) > 0) o.StopPriceChanged = Dbl(f[7]);
                owner.Change(new Order[] { o });
                return null;
            }
            if (cmd == "CLOSEPOSITION")
            {
                Account a = FindAccount(f[1]);
                NinjaTrader.Cbi.Instrument ins = NinjaTrader.Cbi.Instrument.GetInstrument(BaseName(f[2]));
                if (ins == null)
                    return "instrument " + f[2] + " not found";
                a.Flatten(new List<NinjaTrader.Cbi.Instrument> { ins });
                Remember(a.Name, ins.FullName);
                return null;
            }
            if (cmd == "FLATTENEVERYTHING")
            {
                foreach (Account a in Accounts())
                {
                    if (PaperOnly && !SimName.IsMatch(a.Name))
                        continue;
                    List<NinjaTrader.Cbi.Instrument> insts = new List<NinjaTrader.Cbi.Instrument>();
                    lock (a.Positions)
                    {
                        foreach (Position p in a.Positions)
                            if (p.MarketPosition != MarketPosition.Flat && !insts.Contains(p.Instrument))
                                insts.Add(p.Instrument);
                    }
                    lock (a.Orders)
                    {
                        foreach (Order o in a.Orders)
                            if (Live(o.OrderState) && !insts.Contains(o.Instrument))
                                insts.Add(o.Instrument);
                    }
                    if (insts.Count > 0)
                        a.Flatten(insts);
                }
                return null;
            }
            return cmd + " not supported";
        }

        // ------------------------------------------------------------------ snapshot
        private string Snapshot(string acctName)
        {
            double now = Now();
            Account a = FindAccount(acctName);
            StringBuilder sb = new StringBuilder(1024);
            sb.Append("{\"ok\":true,\"t\":").Append(N(now)).Append(",\"orders\":{");
            bool first = true;
            if (a != null)
            {
                List<Order> mine = new List<Order>();
                lock (a.Orders)
                {
                    foreach (Order o in a.Orders)
                        if (o.Name != null && o.Name.StartsWith("LE"))
                            mine.Add(o);
                }
                foreach (Order o in mine)
                {
                    string st = o.OrderState.ToString().ToUpperInvariant();
                    string key = a.Name + "|" + o.Name;
                    OrdRec rec;
                    if (!ords.TryGetValue(key, out rec)) { rec = new OrdRec(); ords[key] = rec; }
                    if (rec.State != st || rec.Filled != o.Filled) { rec.State = st; rec.Filled = o.Filled; rec.T = now; }
                    if (!first) sb.Append(',');
                    first = false;
                    sb.Append(Q(o.Name)).Append(":{\"state\":").Append(Q(st)).Append(",\"filled\":").Append(o.Filled)
                      .Append(",\"avg\":").Append(N(o.AverageFillPrice)).Append(",\"t\":").Append(N(rec.T)).Append('}');
                    Remember(a.Name, o.Instrument.FullName);
                }
                Dictionary<string, Position> open = new Dictionary<string, Position>();
                lock (a.Positions)
                {
                    foreach (Position p in a.Positions)
                        open[p.Instrument.FullName] = p;
                }
                foreach (KeyValuePair<string, Position> kv in open)
                    Remember(a.Name, kv.Key);
                foreach (KeyValuePair<string, PosRec> kv in pos)
                {
                    if (!kv.Key.StartsWith(a.Name + "|"))
                        continue;
                    PosRec r = kv.Value;
                    Position p;
                    string side = "FLAT";
                    int qty = 0;
                    double avg = 0;
                    if (open.TryGetValue(r.Instrument, out p) && p.MarketPosition != MarketPosition.Flat)
                    {
                        side = p.MarketPosition == MarketPosition.Long ? "LONG" : "SHORT";
                        qty = p.Quantity;
                        avg = p.AveragePrice;
                    }
                    if (r.Side != side || r.Qty != qty) { r.Side = side; r.Qty = qty; r.Avg = avg; r.T = now; }
                }
            }
            sb.Append("},\"positions\":[");
            first = true;
            if (a != null)
            {
                foreach (KeyValuePair<string, PosRec> kv in pos)
                {
                    if (!kv.Key.StartsWith(a.Name + "|"))
                        continue;
                    PosRec r = kv.Value;
                    if (!first) sb.Append(',');
                    first = false;
                    sb.Append("{\"instrument\":").Append(Q(r.Instrument)).Append(",\"side\":").Append(Q(r.Side)).Append(",\"qty\":")
                      .Append(r.Qty).Append(",\"avg\":").Append(N(r.Avg)).Append(",\"t\":").Append(N(r.T)).Append('}');
                }
            }
            sb.Append("],\"connections\":{");
            first = true;
            List<Connection> conns = new List<Connection>();
            lock (NinjaTrader.Cbi.Connection.Connections)
            {
                foreach (Connection c in NinjaTrader.Cbi.Connection.Connections)
                    conns.Add(c);
            }
            foreach (Connection c in conns)
            {
                string nm;
                try { nm = c.Options.Name; } catch (Exception) { continue; }
                if (!first) sb.Append(',');
                first = false;
                sb.Append(Q(nm)).Append(':').Append(Q(c.Status == ConnectionStatus.Connected ? "CONNECTED" : "DISCONNECTED"));
            }
            sb.Append("},\"accounts\":[");
            first = true;
            foreach (Account x in Accounts())
            {
                if (!first) sb.Append(',');
                first = false;
                sb.Append(Q(x.Name));
            }
            sb.Append("],\"build\":").Append(Q(Build)).Append('}');
            return sb.ToString();
        }

        private void Remember(string acct, string inst)
        {
            string key = acct + "|" + inst;
            if (!pos.ContainsKey(key))
            {
                PosRec r = new PosRec();
                r.Instrument = inst;
                r.T = Now();
                pos[key] = r;
            }
        }

        // ------------------------------------------------------------------ helpers
        private static List<Account> Accounts()
        {
            List<Account> list = new List<Account>();
            lock (NinjaTrader.Cbi.Account.All)
            {
                foreach (Account a in NinjaTrader.Cbi.Account.All)
                    list.Add(a);
            }
            return list;
        }

        private static Account FindAccount(string name)
        {
            foreach (Account a in Accounts())
                if (a.Name == name)
                    return a;
            return null;
        }

        private static Order FindOrder(Account a, string name)
        {
            Order hit = null;
            lock (a.Orders)
            {
                foreach (Order o in a.Orders)
                    if (o.Name == name)
                        hit = o;                                     // the newest of that name
            }
            return hit;
        }

        private static bool Live(OrderState s)
        {
            return s == OrderState.Accepted || s == OrderState.Working || s == OrderState.Submitted || s == OrderState.TriggerPending
                   || s == OrderState.ChangePending || s == OrderState.ChangeSubmitted || s == OrderState.Initialized
                   || s == OrderState.PartFilled;
        }

        private static OrderAction Action(string a)
        {
            return a == "BUY" ? OrderAction.Buy : OrderAction.Sell;
        }

        private static string BaseName(string inst)
        {
            // "MNQ 12-26 Globex" (CLOSEPOSITION with nt_close_suffix) -> "MNQ 12-26"
            string[] p = inst.Split(' ');
            return p.Length >= 2 ? p[0] + " " + p[1] : inst;
        }

        private static int Int(string s)
        {
            int v;
            return int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out v) ? v : 0;
        }

        private static double Dbl(string s)
        {
            double v;
            return double.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out v) ? v : 0;
        }

        private static double Now()
        {
            return (DateTime.UtcNow.Ticks - EpochTicks) / (double)TimeSpan.TicksPerSecond;
        }

        private static string N(double v)
        {
            return v.ToString("0.######", CultureInfo.InvariantCulture);
        }

        private static string Q(string s)
        {
            if (s == null)
                return "null";
            StringBuilder b = new StringBuilder(s.Length + 2);
            b.Append('"');
            foreach (char ch in s)
            {
                if (ch == '"' || ch == '\\') b.Append('\\').Append(ch);
                else if (ch < ' ') b.Append("\\u").Append(((int)ch).ToString("x4"));
                else b.Append(ch);
            }
            b.Append('"');
            return b.ToString();
        }

        private static void Say(string text)
        {
            try
            {
                NinjaTrader.Code.Output.Process(text, PrintTo.OutputTab1);
            }
            catch (Exception)
            {
            }
        }
    }
}
