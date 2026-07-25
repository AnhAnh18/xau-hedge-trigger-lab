from pathlib import Path
import pandas as pd

def parse_ticks(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", encoding="utf-8-sig")
    df.columns = [c.strip().strip("<>").lower() for c in df.columns]
    required = {"date", "time", "bid", "ask", "last", "volume", "flags"}
    missing = required - set(df.columns)
    if missing: raise ValueError(f"Missing tick columns: {sorted(missing)}")
    df["timestamp"] = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), format="%Y.%m.%d %H:%M:%S.%f", errors="raise")
    df["time_msc"] = df["timestamp"].map(lambda value: int(value.timestamp() * 1000)).astype("int64")
    for c in ("bid", "ask", "last"): df[c] = pd.to_numeric(df[c], errors="coerce")
    missing_quotes = {"bid": int(df["bid"].isna().sum()), "ask": int(df["ask"].isna().sum())}
    df[["bid", "ask"]] = df[["bid", "ask"]].ffill()
    if df[["bid", "ask"]].isna().any().any(): raise ValueError("Tick stream starts without an initial Bid/Ask quote")
    df["volume"] = pd.to_numeric(df["volume"], errors="raise")
    df["flags"] = pd.to_numeric(df["flags"], errors="raise").astype("int64")
    df["mid"] = (df["bid"] + df["ask"]) / 2
    df["spread"] = df["ask"] - df["bid"]
    out = df[["timestamp", "time_msc", "bid", "ask", "mid", "spread", "last", "volume", "flags"]]
    if (out["timestamp"].diff().dropna() < pd.Timedelta(0)).any(): raise ValueError("Tick timestamps decrease")
    if out[["bid", "ask"]].isna().any().any() or (out[["bid", "ask"]] <= 0).any().any(): raise ValueError("Invalid Bid/Ask")
    if (out["ask"] < out["bid"]).any(): raise ValueError("Ask is below Bid")
    out.attrs["missing_quote_updates"] = missing_quotes
    return out
