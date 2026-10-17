import yfinance as yf
import pandas as pd
from core.indicators import rsi, macd, sma, bbands, hv, atr, ichimoku
import uuid

UNIVERSE_SYMBOLS = {
    "nikkei225_sample": ["7203.T", "6758.T", "9984.T", "8306.T", "6501.T", "4063.T", "7974.T", "6902.T"],
    "sp500_sample": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B"],
    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "commodity": ["GC=F", "CL=F", "SI=F", "NG=F"],
    "forex": ["USDJPY=X", "EURUSD=X", "GBPJPY=X", "EURUSD=X"],
}

_watchlist: list[dict] = []
_custom_rules: dict[str, dict] = {}


def get_watchlist() -> list[dict]:
    return _watchlist


def add_to_watchlist(symbol: str, note: str = "") -> dict:
    entry = {"symbol": symbol, "note": note}
    if not any(w["symbol"] == symbol for w in _watchlist):
        _watchlist.append(entry)
    return entry


def remove_from_watchlist(symbol: str) -> bool:
    global _watchlist
    before = len(_watchlist)
    _watchlist = [w for w in _watchlist if w["symbol"] != symbol]
    return len(_watchlist) < before


def save_rule(rule: dict) -> dict:
    _custom_rules[rule["rule_id"]] = rule
    return rule


def get_rules() -> list[dict]:
    return list(_custom_rules.values())


def delete_rule(rule_id: str) -> bool:
    if rule_id in _custom_rules:
        del _custom_rules[rule_id]
        return True
    return False


def _fetch(symbol: str, period: str, interval: str) -> pd.DataFrame | None:
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty or len(df) < 30:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return None


def _apply_filter(df: pd.DataFrame, f: dict) -> bool:
    close = df["Close"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    t = f.get("type")
    cond = f.get("condition")
    val = f.get("value")

    try:
        if t == "rsi":
            v = rsi(close).iloc[-1]
            if pd.isna(v):
                return False
            return v < val if cond == "lt" else v > val
        if t == "macd":
            m, s, _ = macd(close)
            if cond == "bullish_cross":
                return m.iloc[-2] < s.iloc[-2] and m.iloc[-1] >= s.iloc[-1]
            if cond == "bearish_cross":
                return m.iloc[-2] > s.iloc[-2] and m.iloc[-1] <= s.iloc[-1]
        if t == "sma_cross":
            s25 = sma(close, 25)
            s75 = sma(close, 75)
            if cond == "golden":
                return s25.iloc[-2] < s75.iloc[-2] and s25.iloc[-1] >= s75.iloc[-1]
            if cond == "dead":
                return s25.iloc[-2] > s75.iloc[-2] and s25.iloc[-1] <= s75.iloc[-1]
        if t == "price_above_cloud":
            _, _, sa, sb, _ = ichimoku(high, low, close)
            cloud_top = max(sa.iloc[-1], sb.iloc[-1])
            return float(close.iloc[-1]) > cloud_top
        if t == "price_below_cloud":
            _, _, sa, sb, _ = ichimoku(high, low, close)
            cloud_bot = min(sa.iloc[-1], sb.iloc[-1])
            return float(close.iloc[-1]) < cloud_bot
        if t == "hv":
            v = hv(close).iloc[-1]
            if pd.isna(v):
                return False
            return v < val if cond == "lt" else v > val
        if t == "volume_surge":
            vol = df["Volume"].squeeze()
            avg_vol = float(vol.iloc[-20:-1].mean())
            return avg_vol > 0 and float(vol.iloc[-1]) > avg_vol * val
        if t == "bbands":
            u, _, l = bbands(close)
            last = float(close.iloc[-1])
            rng = float(u.iloc[-1]) - float(l.iloc[-1])
            if rng == 0:
                return False
            pos = (last - float(l.iloc[-1])) / rng
            if cond == "near_lower":
                return pos < 0.2
            if cond == "near_upper":
                return pos > 0.8
        if t == "custom":
            rule_id = f.get("rule_id")
            rule = _custom_rules.get(rule_id)
            if not rule:
                return False
            results = [_apply_filter(df, c) for c in rule.get("conditions", [])]
            logic = rule.get("logic", "AND")
            return all(results) if logic == "AND" else any(results)
    except Exception:
        return False
    return False


def _score(df: pd.DataFrame, filters: list[dict]) -> float:
    close = df["Close"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()

    matched = sum(1 for f in filters if _apply_filter(df, f))
    filter_score = matched / len(filters) if filters else 0

    r = rsi(close).iloc[-1]
    rsi_score = max(0, (70 - float(r)) / 70) if not pd.isna(r) else 0

    vol = df["Volume"].squeeze()
    avg_vol = float(vol.iloc[-20:-1].mean())
    vol_score = min(float(vol.iloc[-1]) / avg_vol, 3) / 3 if avg_vol > 0 else 0

    try:
        _, k, sa, sb, _ = ichimoku(high, low, close)
        cloud_top = max(sa.iloc[-1], sb.iloc[-1])
        last = float(close.iloc[-1])
        ichi_score = 1.0 if last > cloud_top else 0.3
    except Exception:
        ichi_score = 0

    return round(filter_score * 0.4 + rsi_score * 0.2 + vol_score * 0.2 + ichi_score * 0.2, 3)


def run_screen(universe: list[str], filters: list[dict], period: str = "6mo",
               interval: str = "1d", sort_by: str = "score", limit: int = 20) -> dict:
    symbols = []
    for u in universe:
        if u == "watchlist":
            symbols += [w["symbol"] for w in _watchlist]
        elif u in UNIVERSE_SYMBOLS:
            symbols += UNIVERSE_SYMBOLS[u]
    symbols = list(set(symbols))

    scanned = len(symbols)
    results = []

    for symbol in symbols:
        df = _fetch(symbol, period, interval)
        if df is None:
            continue
        close = df["Close"].squeeze()
        high = df["High"].squeeze()
        low = df["Low"].squeeze()

        if not all(_apply_filter(df, f) for f in filters):
            continue

        score = _score(df, filters)
        r = rsi(close).iloc[-1]
        m, s, _ = macd(close)
        _, _, sa, sb, _ = ichimoku(high, low, close)
        vol = df["Volume"].squeeze()
        avg_vol = float(vol.iloc[-20:-1].mean())

        results.append({
            "symbol": symbol,
            "type": _asset_type(symbol),
            "score": score,
            "price": round(float(close.iloc[-1]), 4),
            "signals": {
                "rsi": round(float(r), 2) if not pd.isna(r) else None,
                "macd": "bullish" if m.iloc[-1] > s.iloc[-1] else "bearish",
                "ichimoku": "above_cloud" if float(close.iloc[-1]) > max(sa.iloc[-1], sb.iloc[-1]) else "below_cloud",
                "hv": round(float(hv(close).iloc[-1]), 2),
                "volume_surge": round(float(vol.iloc[-1]) / avg_vol, 2) if avg_vol > 0 else None,
            },
        })

    results.sort(key=lambda x: x.get(sort_by, x["score"]) or 0, reverse=True)
    return {"scanned": scanned, "matched": len(results), "results": results[:limit]}


def _asset_type(symbol: str) -> str:
    if symbol.endswith("=X"):
        return "forex"
    if symbol.endswith("=F"):
        return "commodity"
    if "-USD" in symbol or "-JPY" in symbol:
        return "crypto"
    return "stock"
