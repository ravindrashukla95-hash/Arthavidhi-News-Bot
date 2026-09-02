#!/usr/bin/env python3
"""
SPX Open-Close Research
=======================

Downloads the full S&P 500 (^GSPC) daily history from Yahoo Finance and
produces a complete Open -> Close move analysis:

  - Raw data CSV + enriched daily analysis CSV
  - Exact point-difference frequency table
  - Bucketed (0-10, 10-20, ...) frequency table
  - Weekday analysis (per-weekday stats and bucket distributions)
  - Up-day / Down-day statistics
  - Summary statistics (mean, median, mode, std, percentiles, extremes)
  - Multi-sheet Excel report
  - Charts: histogram, exact frequency curve, bucket distribution,
    weekday comparison, weekday box plot, monthly heatmap,
    yearly distribution

Usage:
    python main.py                  # download ^GSPC full history from Yahoo
    python main.py --csv data.csv   # use a local OHLC CSV instead
    python main.py --start 2000-01-01 --end 2025-12-31

The local CSV must have columns: Date, Open, High, Low, Close
(Volume optional). Extra columns are ignored.
"""

import argparse
import io
import os
import sys
import urllib.request

import matplotlib

matplotlib.use("Agg")  # headless-safe; must be set before pyplot import
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
BUCKET_SIZE = 10  # points per bucket
WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# ---------------------------------------------------------------------------
# Data acquisition
# ---------------------------------------------------------------------------

def fetch_yahoo(start=None, end=None):
    """Download ^GSPC daily OHLC from Yahoo Finance via yfinance."""
    import yfinance as yf

    print("Downloading ^GSPC history from Yahoo Finance ...")
    if start or end:
        df = yf.download("^GSPC", start=start, end=end,
                         auto_adjust=False, progress=False)
    else:
        df = yf.download("^GSPC", period="max",
                         auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise RuntimeError("Yahoo Finance returned no data")
    # yfinance >= 0.2 returns MultiIndex columns for single tickers too
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()[["Date", "Open", "High", "Low", "Close"]]
    return df


def fetch_stooq(start=None, end=None):
    """Fallback: full ^SPX daily history as CSV from stooq.com."""
    print("Yahoo failed - falling back to stooq.com ...")
    url = "https://stooq.com/q/d/l/?s=%5Espx&i=d"
    with urllib.request.urlopen(url, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(raw))
    df["Date"] = pd.to_datetime(df["Date"])
    df = df[["Date", "Open", "High", "Low", "Close"]]
    if start:
        df = df[df["Date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["Date"] <= pd.Timestamp(end)]
    if df.empty:
        raise RuntimeError("Stooq returned no data")
    return df


def load_csv(path):
    """Load a local OHLC CSV (columns: Date, Open, High, Low, Close)."""
    print(f"Loading local CSV: {path}")
    df = pd.read_csv(path)
    required = {"Date", "Open", "High", "Low", "Close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")
    df["Date"] = pd.to_datetime(df["Date"])
    return df[["Date", "Open", "High", "Low", "Close"]]


def get_data(args):
    if args.csv:
        df = load_csv(args.csv)
    else:
        try:
            df = fetch_yahoo(args.start, args.end)
        except Exception as exc:
            print(f"  Yahoo download failed: {exc}")
            df = fetch_stooq(args.start, args.end)
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    # Very early Yahoo history (pre-1962) repeats Close as Open; those rows
    # would flood the analysis with fake 0-point days, so drop them.
    df = df[df["Open"] != df["Close"]].copy() if args.drop_equal_open_close else df
    df = df.sort_values("Date").reset_index(drop=True)
    print(f"  {len(df)} trading days "
          f"({df['Date'].iloc[0].date()} to {df['Date'].iloc[-1].date()})")
    return df


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def build_daily(df):
    """Add all derived columns used by the rest of the analysis."""
    out = df.copy()
    out["Close_Minus_Open"] = out["Close"] - out["Open"]
    out["Abs_Move"] = out["Close_Minus_Open"].abs()
    out["Open_To_High"] = out["High"] - out["Open"]
    out["Open_To_Low"] = out["Open"] - out["Low"]
    out["High_To_Low_Range"] = out["High"] - out["Low"]
    out["Gap"] = out["Open"] - out["Close"].shift(1)
    out["Direction"] = np.where(out["Close_Minus_Open"] >= 0, "Bullish", "Bearish")
    out["Pct_Move"] = out["Close_Minus_Open"] / out["Open"] * 100
    out["Weekday"] = out["Date"].dt.day_name()
    out["Month"] = out["Date"].dt.month_name()
    out["Month_Num"] = out["Date"].dt.month
    out["Quarter"] = "Q" + out["Date"].dt.quarter.astype(str)
    out["Year"] = out["Date"].dt.year
    return out


def exact_frequency(daily):
    """Frequency of the absolute Open->Close difference rounded to a point."""
    pts = daily["Abs_Move"].round().astype(int)
    freq = pts.value_counts().sort_index()
    table = freq.rename_axis("Difference_Points").reset_index(name="Count")
    table["Percent"] = (table["Count"] / table["Count"].sum() * 100).round(2)
    table["Cumulative_Percent"] = table["Percent"].cumsum().round(2)
    return table


def bucket_series(abs_move):
    """Map absolute moves to labelled buckets of BUCKET_SIZE points."""
    top = int(np.ceil(abs_move.max() / BUCKET_SIZE)) * BUCKET_SIZE
    top = max(top, BUCKET_SIZE)
    edges = list(range(0, top + BUCKET_SIZE, BUCKET_SIZE))
    labels = [f"{lo}-{lo + BUCKET_SIZE}" for lo in edges[:-1]]
    return pd.cut(abs_move, bins=edges, labels=labels,
                  right=False, include_lowest=True)


def bucket_frequency(daily):
    buckets = bucket_series(daily["Abs_Move"])
    freq = buckets.value_counts().reindex(buckets.cat.categories, fill_value=0)
    table = freq.rename_axis("Range_Points").reset_index(name="Count")
    table["Percent"] = (table["Count"] / table["Count"].sum() * 100).round(2)
    table["Cumulative_Percent"] = table["Percent"].cumsum().round(2)
    return table[table["Count"] > 0].reset_index(drop=True)


def describe_moves(moves):
    """Standard stat block for a series of absolute moves."""
    return {
        "Trading_Days": int(moves.count()),
        "Average_Move": round(moves.mean(), 2),
        "Median_Move": round(moves.median(), 2),
        "Std_Dev": round(moves.std(), 2),
        "Max_Move": round(moves.max(), 2),
        "Min_Move": round(moves.min(), 2),
        "P90": round(moves.quantile(0.90), 2),
        "P95": round(moves.quantile(0.95), 2),
        "P99": round(moves.quantile(0.99), 2),
    }


def weekday_analysis(daily):
    rows = []
    for day in WEEKDAY_ORDER:
        sub = daily.loc[daily["Weekday"] == day, "Abs_Move"]
        if sub.empty:
            continue
        rows.append({"Weekday": day, **describe_moves(sub)})
    return pd.DataFrame(rows)


def weekday_bucket_analysis(daily):
    """Bucket counts per weekday - one column per weekday."""
    tmp = daily[["Weekday"]].copy()
    tmp["Bucket"] = bucket_series(daily["Abs_Move"])
    pivot = (tmp.pivot_table(index="Bucket", columns="Weekday",
                             aggfunc=len, fill_value=0, observed=False)
             .reindex(columns=WEEKDAY_ORDER, fill_value=0))
    pivot.columns = WEEKDAY_ORDER
    pivot = pivot[pivot.sum(axis=1) > 0]
    return pivot.rename_axis("Range_Points").reset_index()


def summary_statistics(daily):
    moves = daily["Abs_Move"]
    signed = daily["Close_Minus_Open"]
    best = daily.loc[signed.idxmax()]
    worst = daily.loc[signed.idxmin()]
    mode_val = moves.round().mode()
    stats = [
        ("Total Trading Days", len(daily)),
        ("First Date", daily["Date"].iloc[0].date().isoformat()),
        ("Last Date", daily["Date"].iloc[-1].date().isoformat()),
        ("Maximum Open-Close Difference (abs)", round(moves.max(), 2)),
        ("Minimum Open-Close Difference (abs)", round(moves.min(), 2)),
        ("Average Difference (abs)", round(moves.mean(), 2)),
        ("Median Difference (abs)", round(moves.median(), 2)),
        ("Mode (rounded points)", int(mode_val.iloc[0]) if not mode_val.empty else None),
        ("Standard Deviation", round(moves.std(), 2)),
        ("90th Percentile", round(moves.quantile(0.90), 2)),
        ("95th Percentile", round(moves.quantile(0.95), 2)),
        ("99th Percentile", round(moves.quantile(0.99), 2)),
        ("Largest Bullish Day (points)",
         f"{best['Close_Minus_Open']:+.2f} on {best['Date'].date()}"),
        ("Largest Bearish Day (points)",
         f"{worst['Close_Minus_Open']:+.2f} on {worst['Date'].date()}"),
        ("Bullish Days", int((daily["Direction"] == "Bullish").sum())),
        ("Bearish Days", int((daily["Direction"] == "Bearish").sum())),
        ("Bullish %", round((daily["Direction"] == "Bullish").mean() * 100, 2)),
        ("Average Daily Range (High-Low)", round(daily["High_To_Low_Range"].mean(), 2)),
        ("Average Gap (abs)", round(daily["Gap"].abs().mean(), 2)),
    ]
    return pd.DataFrame(stats, columns=["Statistic", "Value"])


def direction_statistics(daily):
    rows = []
    for direction in ["Bullish", "Bearish"]:
        sub = daily.loc[daily["Direction"] == direction, "Abs_Move"]
        if sub.empty:
            continue
        rows.append({"Direction": direction, **describe_moves(sub)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def _save(fig, name):
    path = os.path.join(REPORTS_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  chart  -> {path}")


def make_charts(daily, exact, buckets):
    moves = daily["Abs_Move"]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(moves, bins=80, color="#3b6fb5", edgecolor="white")
    ax.set_title("SPX Absolute Open-Close Move - Histogram")
    ax.set_xlabel("Points")
    ax.set_ylabel("Trading Days")
    _save(fig, "histogram.png")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(exact["Difference_Points"], exact["Count"], color="#3b6fb5")
    ax.set_title("Exact Open-Close Difference Frequency")
    ax.set_xlabel("Difference (points, rounded)")
    ax.set_ylabel("Count")
    _save(fig, "exact_frequency_curve.png")

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(buckets["Range_Points"], buckets["Count"], color="#3b6fb5")
    ax.set_title(f"Open-Close Move Distribution ({BUCKET_SIZE}-point buckets)")
    ax.set_xlabel("Range (points)")
    ax.set_ylabel("Trading Days")
    ax.tick_params(axis="x", rotation=60)
    _save(fig, "bucket_distribution.png")

    wk = weekday_analysis(daily)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.bar(wk["Weekday"], wk["Average_Move"], color="#3b6fb5", label="Average")
    ax.plot(wk["Weekday"], wk["Median_Move"], color="#d1495b",
            marker="o", label="Median")
    ax.set_title("Average / Median Absolute Move by Weekday")
    ax.set_ylabel("Points")
    ax.legend()
    _save(fig, "weekday_comparison.png")

    data = [daily.loc[daily["Weekday"] == d, "Abs_Move"] for d in WEEKDAY_ORDER]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.boxplot(data, showfliers=False)
    ax.set_xticks(range(1, len(WEEKDAY_ORDER) + 1), WEEKDAY_ORDER)
    ax.set_title("Absolute Move by Weekday (box plot, outliers hidden)")
    ax.set_ylabel("Points")
    _save(fig, "weekday_boxplot.png")

    heat = daily.pivot_table(index="Year", columns="Month_Num",
                             values="Abs_Move", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(10, max(6, len(heat) * 0.22)))
    im = ax.imshow(heat.values, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(12),
                  ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    step = max(1, len(heat) // 40)
    ax.set_yticks(range(0, len(heat), step), heat.index[::step])
    ax.set_title("Average Absolute Move - Monthly Heatmap")
    fig.colorbar(im, ax=ax, label="Points")
    _save(fig, "monthly_heatmap.png")

    yearly = daily.groupby("Year")["Abs_Move"].mean()
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(yearly.index, yearly.values, color="#3b6fb5")
    ax.set_title("Average Absolute Open-Close Move by Year")
    ax.set_xlabel("Year")
    ax.set_ylabel("Points")
    _save(fig, "yearly_distribution.png")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_csvs(raw, daily, exact, buckets, weekday, weekday_buckets, summary):
    for name, frame in [
        ("raw_data.csv", raw),
        ("daily_analysis.csv", daily),
        ("exact_frequency.csv", exact),
        ("bucket_frequency.csv", buckets),
        ("weekday_analysis.csv", weekday),
        ("weekday_bucket_analysis.csv", weekday_buckets),
        ("summary_statistics.csv", summary),
    ]:
        path = os.path.join(REPORTS_DIR, name)
        frame.to_csv(path, index=False)
        print(f"  csv    -> {path}")


def write_excel(raw, daily, exact, buckets, weekday, weekday_buckets,
                summary, directions):
    path = os.path.join(REPORTS_DIR, "SPX_Open_Close_Analysis.xlsx")
    with pd.ExcelWriter(path, engine="xlsxwriter",
                        datetime_format="yyyy-mm-dd") as writer:
        book = writer.book
        header_fmt = book.add_format(
            {"bold": True, "bg_color": "#1f4e79", "font_color": "white",
             "border": 1})

        def sheet(frame, name):
            frame.to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            for col, title in enumerate(frame.columns):
                ws.write(0, col, str(title), header_fmt)
                width = max(len(str(title)) + 2, 12)
                ws.set_column(col, col, min(width, 28))
            ws.freeze_panes(1, 0)

        sheet(summary, "Summary")
        sheet(raw, "Raw Data")
        sheet(daily, "Daily Analysis")
        sheet(exact, "Exact Difference Frequency")
        sheet(buckets, "Bucket Frequency")
        sheet(weekday, "Weekday Analysis")
        sheet(weekday_buckets, "Weekday Buckets")
        for day in WEEKDAY_ORDER:
            sub = daily[daily["Weekday"] == day]
            if not sub.empty:
                sheet(sub, day)
        sheet(daily[daily["Direction"] == "Bullish"], "Up Days")
        sheet(daily[daily["Direction"] == "Bearish"], "Down Days")
        sheet(directions, "Statistics")

        for img, anchor_sheet, cell in [
            ("histogram.png", "Summary", "E2"),
            ("bucket_distribution.png", "Bucket Frequency", "G2"),
            ("weekday_comparison.png", "Weekday Analysis", "L2"),
        ]:
            img_path = os.path.join(REPORTS_DIR, img)
            if os.path.exists(img_path):
                writer.sheets[anchor_sheet].insert_image(
                    cell, img_path, {"x_scale": 0.55, "y_scale": 0.55})
    print(f"  excel  -> {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SPX Open-Close analysis")
    parser.add_argument("--csv", help="local OHLC CSV instead of Yahoo download")
    parser.add_argument("--start", help="start date YYYY-MM-DD")
    parser.add_argument("--end", help="end date YYYY-MM-DD")
    parser.add_argument("--keep-equal-open-close", dest="drop_equal_open_close",
                        action="store_false", default=True,
                        help="keep rows where Open == Close (early Yahoo "
                             "history fakes Open as the previous Close)")
    args = parser.parse_args()

    os.makedirs(REPORTS_DIR, exist_ok=True)

    raw = get_data(args)
    daily = build_daily(raw)
    exact = exact_frequency(daily)
    buckets = bucket_frequency(daily)
    weekday = weekday_analysis(daily)
    weekday_buckets = weekday_bucket_analysis(daily)
    summary = summary_statistics(daily)
    directions = direction_statistics(daily)

    print("Writing reports ...")
    save_csvs(raw, daily, exact, buckets, weekday, weekday_buckets, summary)
    make_charts(daily, exact, buckets)
    write_excel(raw, daily, exact, buckets, weekday, weekday_buckets,
                summary, directions)

    print("\nDone. Key numbers:")
    for _, row in summary.head(13).iterrows():
        print(f"  {row['Statistic']}: {row['Value']}")


if __name__ == "__main__":
    sys.exit(main())
