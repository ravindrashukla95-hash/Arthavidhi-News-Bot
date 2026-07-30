# SPX Open-Close Research

Downloads the full S&P 500 (`^GSPC`) daily history from Yahoo Finance and
produces a complete Open → Close move analysis: CSV tables, a multi-sheet
Excel report, and charts. Built for SPX 0DTE research — the daily dataset
also stores Open→High, Open→Low, High-Low range, gap, direction, weekday,
month, quarter and year so the same data can back future strategy work
without re-downloading.

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

Runs in a few seconds. Everything lands in `reports/`.

Options:

```bash
python main.py --start 2000-01-01 --end 2025-12-31   # date range
python main.py --csv my_spx_data.csv                 # offline: use a local
                                                     # CSV (Date, Open, High,
                                                     # Low, Close)
python main.py --keep-equal-open-close               # keep Open == Close rows
```

If Yahoo Finance is unreachable, the script automatically falls back to
stooq.com for the same history.

> **Note on early history:** Yahoo's pre-1962 SPX rows repeat the Close as
> the Open, which would flood the analysis with fake 0-point days. Those
> rows are dropped by default (`--keep-equal-open-close` restores them).

## Output

```
reports/
├── SPX_Open_Close_Analysis.xlsx   # multi-sheet Excel report
├── raw_data.csv
├── daily_analysis.csv             # all derived columns per trading day
├── exact_frequency.csv            # count per exact rounded point difference
├── bucket_frequency.csv           # counts in 0-10, 10-20, ... buckets
├── weekday_analysis.csv
├── weekday_bucket_analysis.csv
├── summary_statistics.csv
├── histogram.png
├── exact_frequency_curve.png
├── bucket_distribution.png
├── weekday_comparison.png
├── weekday_boxplot.png
├── monthly_heatmap.png
└── yearly_distribution.png
```

### Excel sheets

Summary · Raw Data · Daily Analysis · Exact Difference Frequency ·
Bucket Frequency · Weekday Analysis · Weekday Buckets ·
Monday–Friday (one sheet each) · Up Days · Down Days · Statistics

### Statistics included

Total trading days, first/last date, max/min/average/median/mode of the
absolute Open-Close difference, standard deviation, 90/95/99th percentiles,
largest bullish and bearish days, bullish/bearish day counts and win rate,
average daily range, average gap — plus the same stat block broken out per
weekday and for up-days vs down-days separately.

## Daily analysis columns

| Column | Meaning |
|---|---|
| `Close_Minus_Open` | signed Open → Close move (points) |
| `Abs_Move` | absolute Open → Close move |
| `Open_To_High` | High − Open |
| `Open_To_Low` | Open − Low |
| `High_To_Low_Range` | daily range |
| `Gap` | today's Open − yesterday's Close |
| `Direction` | Bullish / Bearish |
| `Pct_Move` | Open → Close move in % |
| `Weekday`, `Month`, `Quarter`, `Year` | calendar breakdowns |
