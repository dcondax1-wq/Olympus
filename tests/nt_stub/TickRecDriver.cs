// Behaviour driver for ninjatrader/LE_TickRec.cs backfill (day-ofprogram 2026-11-23), compiled with NtStubsTick.cs by
// tests/test_tickrec_cs.py. Drives the private 15 s Check() by reflection with a fake clock; prints PASS / FAIL lines.
using System;
using System.IO;
using System.Reflection;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.AddOns;

public static class TickRecDriver
{
    static int fails = 0;
    static void Ok(bool c, string what) { Console.WriteLine((c ? "PASS " : "FAIL ") + what); if (!c) fails++; }
    static DateTime clock;
    static void SetStatic(string name, object v)
    {
        FieldInfo f = typeof(LE_TickRec).GetField(name, BindingFlags.NonPublic | BindingFlags.Static);
        f.SetValue(null, v);
    }
    static void Check(LE_TickRec r) { typeof(LE_TickRec).GetMethod("Check", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(r, new object[] { null }); }
    static void Run(LE_TickRec r, int steps) { for (int i = 0; i < steps; i++) { clock = clock.AddSeconds(15); Check(r); } }
    static string Status(string dir) { return File.ReadAllText(Path.Combine(dir, "le_ticks", "le_tickrec_status.txt")); }

    public static int Main()
    {
        string dir = Environment.GetEnvironmentVariable("LE_NTSTUB_DIR");
        string lt = Path.Combine(dir, "le_ticks");
        Directory.CreateDirectory(lt);
        SetStatic("UtcNow", new Func<DateTime>(delegate { return clock; }));
        SetStatic("MinFreeBytes", 0L);
        // pure helpers
        Ok(LE_TickRec.FrontName("NQ", new DateTime(2026, 11, 23)) == "NQ 12-26", "front Nov 23 = NQ 12-26");
        Ok(LE_TickRec.FrontName("NQ", new DateTime(2026, 12, 10)) == "NQ 12-26" && LE_TickRec.FrontName("NQ", new DateTime(2026, 12, 11)) == "NQ 03-27", "roll 8 days before the 3rd Friday (Dec 18): Dec 10 = 12-26, Dec 11 = 03-27");
        Ok(LE_TickRec.FrontName("ES", new DateTime(2026, 6, 12)) == "ES 09-26", "front Jun 12 2026 = ES 09-26");
        Ok(!LE_TickRec.InWindow(new DateTime(2026, 11, 23, 9, 30, 0)) && !LE_TickRec.InWindow(new DateTime(2026, 11, 23, 2, 0, 0))
           && !LE_TickRec.InWindow(new DateTime(2026, 11, 23, 16, 4, 0)), "no requests Mon 02:00-16:05 ET");
        Ok(LE_TickRec.InWindow(new DateTime(2026, 11, 23, 16, 5, 0)) && LE_TickRec.InWindow(new DateTime(2026, 11, 24, 1, 59, 0))
           && LE_TickRec.InWindow(new DateTime(2026, 11, 28, 11, 0, 0)), "requests 16:05-02:00 weekdays and all Saturday");
        Ok(LE_TickRec.SendWindow(new DateTime(2026, 11, 24, 1, 39, 0)) && !LE_TickRec.SendWindow(new DateTime(2026, 11, 24, 1, 40, 0))
           && !LE_TickRec.SendWindow(new DateTime(2026, 11, 24, 1, 59, 0)) && LE_TickRec.SendWindow(new DateTime(2026, 11, 28, 1, 50, 0))
           && LE_TickRec.SendWindow(new DateTime(2026, 11, 24, 16, 5, 0)), "red team: a NEW request only until 01:40 ET on weekdays (it ends before 02:00)");

        // 1. off: nothing requested
        clock = new DateTime(2026, 11, 23, 22, 0, 0, DateTimeKind.Utc);          // 17:00 ET Monday
        LE_TickRec r = new LE_TickRec();
        r.Drive(State.SetDefaults); r.Drive(State.Active);
        Run(r, 4);
        Ok(NinjaTrader.Data.BarsRequest.Log.Count == 0, "disabled: no history request");
        // 2. enable inside the trading window (Tue 10:00 ET): pass starts but waits for the window
        clock = new DateTime(2026, 11, 24, 15, 0, 0, DateTimeKind.Utc);
        File.WriteAllText(Path.Combine(lt, "instruments.txt"), "NQ 12-26\nES 12-26\n");
        File.WriteAllText(Path.Combine(lt, "enabled.txt"), "on\n");
        Run(r, 8);
        Ok(NinjaTrader.Data.BarsRequest.Log.Count == 0 && Status(dir).Contains("backfill=waiting_window"), "enabled at 10:00 ET: waits (status waiting_window)");
        // 3. evening: requests one at a time, 5 s apart -> one per 15 s step, newest day first, front contract, Tick 1
        clock = new DateTime(2026, 11, 24, 21, 10, 0, DateTimeKind.Utc);          // 16:10 ET
        Run(r, 1);
        Ok(NinjaTrader.Data.BarsRequest.Log.Count == 1 && NinjaTrader.Data.BarsRequest.Log[0].StartsWith("NQ 12-26|2026-11-23 05:00|2026-11-24 05:00|Tick1"),
           "first request = NQ 12-26, Mon Nov 23 ET day (05:00-05:00 UTC), Tick 1: " + (NinjaTrader.Data.BarsRequest.Log.Count > 0 ? NinjaTrader.Data.BarsRequest.Log[0] : "none"));
        string f1 = Path.Combine(lt, "bf_NQ_2026-11-23.csv");
        Ok(File.Exists(f1) && File.ReadAllLines(f1)[0] == "t_ms,price,size,bid,ask" && File.ReadAllLines(f1).Length == 1 + 144,
           "bf_NQ_2026-11-23.csv = header + 144 ticks of that ET day only");
        string[] row = File.ReadAllLines(f1)[1].Split(',');
        Ok(row.Length == 5 && row[0] == "1795410000000" && double.Parse(row[3]) == double.Parse(row[1]) - 0.25, "first tick 00:00 ET in UTC ms, bid/ask kept: " + string.Join(",", row));
        Ok(!File.Exists(f1 + ".tmp"), "no .tmp left behind");
        Run(r, 1);
        Ok(NinjaTrader.Data.BarsRequest.Log[1].StartsWith("ES 12-26|2026-11-23"), "then ES same day");
        // 4. skips: days already present are not asked again; Saturday skipped
        File.WriteAllText(Path.Combine(lt, "bf_NQ_2026-11-22.done"), "");
        Run(r, 1);
        Ok(NinjaTrader.Data.BarsRequest.Log[2].StartsWith("ES 12-26|2026-11-22"), "NQ Sunday already .done -> skipped, ES Sunday asked: " + NinjaTrader.Data.BarsRequest.Log[2]);
        Run(r, 1);
        Ok(NinjaTrader.Data.BarsRequest.Log[3].StartsWith("NQ 12-26|2026-11-20"), "Saturday Nov 21 skipped -> Fri Nov 20: " + NinjaTrader.Data.BarsRequest.Log[3]);
        // 5. end of history: server has nothing before Nov 1 -> 7 empty weekdays then stop that root
        NinjaTrader.Data.BarsRequest.Oldest = new DateTime(2026, 11, 2);
        Run(r, 200);
        int n = NinjaTrader.Data.BarsRequest.Log.Count;
        Ok(Status(dir).Contains("backfill=done"), "pass ends (status done): " + Status(dir).Trim());
        Ok(File.Exists(Path.Combine(lt, "bf_NQ_2026-10-30.none")) && !File.Exists(Path.Combine(lt, "bf_NQ_2026-10-01.none")), "empty days marked .none, stops after 7 empty weekdays");
        Ok(n < 80, "bounded number of requests (" + n + ")");
        Ok(Status(dir).Contains("oldest=2026-11-02") && Status(dir).Contains("backfill_days=1"), "status oldest / NQ days: " + Status(dir).Trim());
        // 6. a later pass the same evening does not repeat; next day 17:15 ET a new pass asks only the new day
        Run(r, 20);
        Ok(NinjaTrader.Data.BarsRequest.Log.Count == n, "no repeat requests within the day");
        clock = new DateTime(2026, 11, 25, 22, 15, 0, DateTimeKind.Utc);          // Wed 17:15 ET
        Run(r, 3);
        Ok(NinjaTrader.Data.BarsRequest.Log.Count == n + 2 && NinjaTrader.Data.BarsRequest.Log[n].Contains("|2026-11-24 05:00|"), "17:15 ET pass: only Nov 24 (NQ + ES)");
        // 7. disk guard: nothing requested under the limit
        SetStatic("MinFreeBytes", long.MaxValue);
        clock = new DateTime(2026, 11, 26, 22, 15, 0, DateTimeKind.Utc);
        Run(r, 3);
        Ok(NinjaTrader.Data.BarsRequest.Log.Count == n + 2 && Status(dir).Contains("low_disk=1"), "under 10 GB free: no request, low_disk=1");
        SetStatic("MinFreeBytes", 0L);
        // 8. a hung request is dropped after 10 min and the pass moves on
        NinjaTrader.Data.BarsRequest.Hang = true;
        Run(r, 1);
        int h = NinjaTrader.Data.BarsRequest.Log.Count;
        Run(r, 10);
        Ok(NinjaTrader.Data.BarsRequest.Log.Count == h, "while in flight: no second request");
        Run(r, 40);
        Ok(Status(dir).Contains("bf_errors=1") && !File.Exists(Path.Combine(lt, "bf_NQ_2026-11-25.csv")), "hung request dropped after 10 min, counted, day not marked");
        NinjaTrader.Data.BarsRequest.Hang = false;
        clock = new DateTime(2026, 11, 27, 22, 15, 0, DateTimeKind.Utc);          // Fri 17:15 ET: the next pass retries it
        Run(r, 6);
        Ok(File.Exists(Path.Combine(lt, "bf_NQ_2026-11-25.csv")) && File.Exists(Path.Combine(lt, "bf_NQ_2026-11-26.csv")), "next pass retries the dropped day");
        // 9a. DEPTH (day-ofmax): NQ only by default, top-10 snapshot on change, at most one per 250 ms, header, offsets in ticks
        System.Collections.Generic.List<NinjaTrader.Data.MarketDepth<NinjaTrader.Data.MarketDepthRow>> made = NinjaTrader.Data.MarketDepth<NinjaTrader.Data.MarketDepthRow>.Made;
        Ok(made.Count >= 1 && made[made.Count - 1].Instrument.FullName == "NQ 12-26" && made[made.Count - 1].HasHandler, "depth subscribed for NQ (not ES), event bound by reflection");
        bool esDepth = false;
        foreach (NinjaTrader.Data.MarketDepth<NinjaTrader.Data.MarketDepthRow> m in made) if (m.Instrument.FullName.StartsWith("ES")) esDepth = true;
        Ok(!esDepth, "no depth for ES by default");
        NinjaTrader.Data.MarketDepth<NinjaTrader.Data.MarketDepthRow> md = made[made.Count - 1];
        for (int k = 0; k < 12; k++)
        {
            NinjaTrader.Data.MarketDepthRow b = new NinjaTrader.Data.MarketDepthRow(); b.Price = 21000 - 0.25 * k; b.Volume = 5 + k; md.Bids.Add(b);
            NinjaTrader.Data.MarketDepthRow a = new NinjaTrader.Data.MarketDepthRow(); a.Price = 21000.25 + 0.25 * k; a.Volume = 7 + k; md.Asks.Add(a);
        }
        MethodInfo flush = typeof(LE_TickRec).GetMethod("Flush", BindingFlags.NonPublic | BindingFlags.Instance);
        md.Fire(); flush.Invoke(r, new object[] { null });
        string[] dl = Directory.GetFiles(Path.Combine(lt, "depth"));
        Ok(dl.Length == 1 && Path.GetFileName(dl[0]).StartsWith("NQ_"), "depth file le_ticks/depth/NQ_<day>.csv: " + string.Join(";", dl));
        string[] lines = File.ReadAllLines(dl[0]);
        Ok(lines[0] == LE_TickRec.DepthHeader().Trim() && lines[0].Split(',').Length == 42 && lines.Length == 2, "header (42 columns) + 1 snapshot: " + lines.Length);
        string[] c = lines[1].Split(',');
        Ok(c[1] == "21000" && c[2] == "0" && c[3] == "1" && c[11] == "9" && c[12] == "5" && c[22] == "1" && c[32] == "7", "bp, bid offsets 0,1.., ask offset 1, sizes: " + lines[1]);
        md.Fire(); md.Fire(); flush.Invoke(r, new object[] { null });
        Ok(File.ReadAllLines(dl[0]).Length == 2, "same book again: no new line");
        md.Bids[0].Volume = 50; md.Fire(); flush.Invoke(r, new object[] { null });
        Ok(File.ReadAllLines(dl[0]).Length == 2, "a change inside 250 ms waits (throttle)");
        clock = clock.AddMilliseconds(300); flush.Invoke(r, new object[] { null }); flush.Invoke(r, new object[] { null });
        Ok(File.ReadAllLines(dl[0]).Length == 3 && File.ReadAllLines(dl[0])[2].Split(',')[12] == "50", "... and is written by the 1 s timer once 250 ms passed");
        Ok(Status(dir).Contains("depth=on"), "status depth=on: " + Status(dir).Trim());
        // 9b. pure helpers of the roll fix
        Ok(LE_TickRec.Candidates("NQ", new DateTime(2026, 11, 23)).Count == 1, "Nov 23: one contract to try");
        System.Collections.Generic.List<string> cs = LE_TickRec.Candidates("NQ", new DateTime(2026, 12, 14));
        Ok(cs.Count == 2 && cs[0] == "NQ 03-27" && cs[1] == "NQ 12-26", "Dec 14 (expiry week): front 03-27, then the expiring 12-26: " + string.Join(",", cs.ToArray()));
        Ok(LE_TickRec.Candidates("NQ", new DateTime(2026, 9, 10))[0] == "NQ 09-26" && LE_TickRec.Candidates("NQ", new DateTime(2026, 9, 10)).Count == 1, "Sep 10 = NQ 09-26 only");
        // 9. disable: no more requests
        File.Delete(Path.Combine(lt, "enabled.txt"));
        Run(r, 1);
        int d = NinjaTrader.Data.BarsRequest.Log.Count;
        clock = new DateTime(2026, 11, 28, 22, 15, 0, DateTimeKind.Utc);
        Run(r, 20);
        Ok(NinjaTrader.Data.BarsRequest.Log.Count == d, "disabled: backfill stops");
        r.Drive(State.Terminated);
        Ok(md.Disposed && !md.HasHandler, "depth unsubscribed and disposed on stop / disable");

        // 10. ROLL FIX (day-ofmax): NinjaTrader does not know "NQ 09-26" -> those days are skipped, NOT the end of history; the
        // June contract's days behind them are fetched; old end.txt and old-format .none are ignored once
        foreach (string f in Directory.GetFiles(lt)) File.Delete(f);
        File.WriteAllText(Path.Combine(lt, "bf_NQ_end.txt"), "2026-09-14\n");
        File.WriteAllText(Path.Combine(lt, "bf_NQ_2026-09-15.none"), "no ticks from the server 2026-11-24\n");
        File.WriteAllText(Path.Combine(lt, "instruments.txt"), "NQ 12-26\n");
        File.WriteAllText(Path.Combine(lt, "depth_off.txt"), "off\n");
        NinjaTrader.Cbi.Instrument.Missing.Add("NQ 09-26");
        NinjaTrader.Data.BarsRequest.Oldest = new DateTime(2026, 6, 1);
        clock = new DateTime(2026, 9, 26, 15, 0, 0, DateTimeKind.Utc);           // a Saturday: requests all day
        LE_TickRec r2 = new LE_TickRec();
        r2.Drive(State.SetDefaults); r2.Drive(State.Active);
        File.WriteAllText(Path.Combine(lt, "enabled.txt"), "on\n");
        Run(r2, 400);
        string st2 = Status(dir);
        Ok(File.Exists(Path.Combine(lt, "bf_NQ_2026-09-15.csv")), "an old-format .none day is asked once more");
        Ok(File.ReadAllText(Path.Combine(lt, "bf_NQ_2026-09-01.none")).StartsWith("v2 unknown contract NQ 09-26"), "Sep 1 (NQ 09-26 unknown): marked, not requested");
        Ok(File.Exists(Path.Combine(lt, "bf_NQ_2026-06-10.csv")), "past the unknown contract: June days (NQ 06-26) are fetched");
        Ok(File.Exists(Path.Combine(lt, "bf_NQ_end2.txt")) && File.ReadAllText(Path.Combine(lt, "bf_NQ_end2.txt")).StartsWith("2026-05"), "the real end (before Jun 1) found and written as end2.txt");
        Ok(st2.Contains("bf_unknown=") && !st2.Contains("bf_unknown=0") && st2.Contains("depth=off"), "status bf_unknown counted, depth off by depth_off.txt: " + st2.Trim());
        r2.Drive(State.Terminated);
        Console.WriteLine(fails == 0 ? "ALL PASS" : fails + " FAILED");
        return fails == 0 ? 0 : 1;
    }
}
