#!/bin/bash
# K5: refetch all candles (public API, cached, resumable): series, hours before close, min volume, first close date.
cd "$(dirname "$0")"
python harvest.py candles KXYTVIEWSW 72 1
python harvest.py candles KXTRUTHSOCIAL 30 1
python harvest.py candles KXTRUTHSOCIALD 24 1
python harvest.py candles KXAAAGASW 96 1 2024-01-01
python harvest.py candles KXAAAGASM 96 1
python harvest.py candles KXAAAGASD 24 1 2026-03-20
python harvest.py candles KXTSAW 48 1 2024-01-01
python harvest.py candles KXAPPRANKFREE 48 1
python harvest.py candles KXNETFLIXRANKSHOW 48 1
python harvest.py candles KXSPOTIFYD 30 1
