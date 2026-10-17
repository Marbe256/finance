from fastapi import APIRouter, HTTPException, Query
import yfinance as yf
import pandas as pd
from core.indicators import compute_indicators, compute_signals

router = APIRouter()


def _fetch_df(symbol: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found or no data.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


@router.get("/api/chart")
def get_chart(
    symbol: str,
    period: str = "3mo",
    interval: str = "1d",
    indicators: str = "sma,volume",
):
    df = _fetch_df(symbol, period, interval)
    indicator_names = [i.strip() for i in indicators.split(",")]

    candles = []
    for ts, row in df.iterrows():
        date = ts.strftime("%Y-%m-%d") if interval in ("1d", "1wk", "1mo") else ts.strftime("%Y-%m-%d %H:%M")
        candles.append({
            "date": date,
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
        })

    return {
        "symbol": symbol,
        "period": period,
        "interval": interval,
        "candles": candles,
        "indicators": compute_indicators(df, indicator_names),
    }


@router.get("/api/analyze")
def get_analyze(symbol: str, period: str = "6mo", interval: str = "1d"):
    df = _fetch_df(symbol, period, interval)
    signals = compute_signals(df)

    parts = []
    if "rsi" in signals:
        r = signals["rsi"]
        parts.append(f"RSI {r['value']}（{r['state']}）")
    if "macd" in signals:
        parts.append(f"MACD {signals['macd']['state']}")
    if "ichimoku" in signals:
        ichi = signals["ichimoku"]
        if ichi.get("above_cloud") is True:
            parts.append("一目均衡表：雲の上")
        elif ichi.get("above_cloud") is False:
            parts.append("一目均衡表：雲の下")
    if "hv" in signals:
        parts.append(f"HV {signals['hv']['value']}%（{signals['hv']['state']}）")

    return {
        "symbol": symbol,
        "signals": signals,
        "summary": "。".join(parts) + "。" if parts else "シグナルなし",
    }


@router.get("/api/symbols/search")
def search_symbols(q: str, type: str = None):
    results = []
    try:
        ticker = yf.Ticker(q.upper())
        info = ticker.info
        if info and info.get("symbol"):
            results.append({
                "symbol": info.get("symbol", q.upper()),
                "name": info.get("longName") or info.get("shortName", ""),
                "type": _guess_type(q),
                "exchange": info.get("exchange", ""),
            })
    except Exception:
        pass

    if not results:
        results.append({"symbol": q.upper(), "name": q.upper(), "type": _guess_type(q), "exchange": ""})

    if type:
        results = [r for r in results if r["type"] == type]
    return {"results": results}


def _guess_type(symbol: str) -> str:
    if symbol.endswith("=X"):
        return "forex"
    if symbol.endswith("=F"):
        return "commodity"
    if "-USD" in symbol or "-JPY" in symbol:
        return "crypto"
    return "stock"
