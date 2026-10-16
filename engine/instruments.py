"""Contract specs for CME equity index futures (minis + micros)."""

INSTRUMENTS = {
    "NQ": {
        "name": "E-mini Nasdaq-100",
        "tick": 0.25,
        "mini_pv": 20.0,      # $ per point, NQ
        "micro_pv": 2.0,      # $ per point, MNQ
        "mini_comm_rt": 4.50,  # round-turn commission+fees estimate (Tradovate-style)
        "micro_comm_rt": 1.50,
        "profile_bin": 5.0,   # volume-profile bin size (points)
        "min_fvg": 3.0,       # min FVG size (points) on base timeframe
        "min_stop": 10.0,
        "max_stop": 60.0,
        "stop_buffer": 2.0,
        "eq_tol": 6.0,        # equal highs/lows tolerance (points)
    },
    "ES": {
        "name": "E-mini S&P 500",
        "tick": 0.25,
        "mini_pv": 50.0,
        "micro_pv": 5.0,
        "mini_comm_rt": 4.50,
        "micro_comm_rt": 1.50,
        "profile_bin": 1.0,
        "min_fvg": 0.75,
        "min_stop": 2.5,
        "max_stop": 15.0,
        "stop_buffer": 0.5,
        "eq_tol": 1.5,
    },
}

# Long-history proxies (Dukascopy index CFDs) - P&L expressed in NQ/ES-equivalent contracts
INSTRUMENTS["NQX"] = {**INSTRUMENTS["NQ"], "name": "Nasdaq-100 CFD proxy (3y history)"}
INSTRUMENTS["ESX"] = {**INSTRUMENTS["ES"], "name": "S&P 500 CFD proxy (3y history)"}

PARTNER = {"NQ": "ES", "ES": "NQ", "NQX": "ESX", "ESX": "NQX"}  # SMT divergence pairing
