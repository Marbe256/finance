import numpy as np
import pandas as pd


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast=12, slow=26, signal=9):
    e_fast = ema(close, fast)
    e_slow = ema(close, slow)
    macd_line = e_fast - e_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bbands(close: pd.Series, period: int = 20, std_dev: float = 2.0):
    mid = sma(close, period)
    std = close.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def hv(close: pd.Series, period: int = 20) -> pd.Series:
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(period).std() * np.sqrt(252) * 100


def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series):
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    chikou = close.shift(-26)
    return tenkan, kijun, senkou_a, senkou_b, chikou


def _series_to_list(s: pd.Series) -> list:
    return [None if pd.isna(v) else round(float(v), 4) for v in s]


def compute_indicators(df: pd.DataFrame, indicator_names: list[str]) -> dict:
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    result = {}

    if "sma" in indicator_names:
        result["sma"] = [
            {"period": 25, "values": _series_to_list(sma(close, 25))},
            {"period": 75, "values": _series_to_list(sma(close, 75))},
        ]

    if "ema" in indicator_names:
        result["ema"] = [
            {"period": 12, "values": _series_to_list(ema(close, 12))},
            {"period": 26, "values": _series_to_list(ema(close, 26))},
        ]

    if "rsi" in indicator_names:
        result["rsi"] = {"period": 14, "values": _series_to_list(rsi(close))}

    if "macd" in indicator_names:
        m, s, h = macd(close)
        result["macd"] = {
            "macd": _series_to_list(m),
            "signal": _series_to_list(s),
            "histogram": _series_to_list(h),
        }

    if "bbands" in indicator_names:
        u, m, l = bbands(close)
        result["bbands"] = {
            "upper": _series_to_list(u),
            "middle": _series_to_list(m),
            "lower": _series_to_list(l),
        }

    if "atr" in indicator_names:
        result["atr"] = {"period": 14, "values": _series_to_list(atr(high, low, close))}

    if "hv" in indicator_names:
        result["hv"] = {"period": 20, "values": _series_to_list(hv(close))}

    if "ichimoku" in indicator_names:
        t, k, sa, sb, ch = ichimoku(high, low, close)
        result["ichimoku"] = {
            "tenkan": _series_to_list(t),
            "kijun": _series_to_list(k),
            "senkou_a": _series_to_list(sa),
            "senkou_b": _series_to_list(sb),
            "chikou": _series_to_list(ch),
        }

    if "volume" in indicator_names:
        result["volume"] = _series_to_list(df["Volume"])

    return result


def compute_signals(df: pd.DataFrame) -> dict:
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    signals = {}

    r = rsi(close)
    last_rsi = float(r.iloc[-1]) if not pd.isna(r.iloc[-1]) else None
    if last_rsi is not None:
        state = "oversold" if last_rsi < 30 else "overbought" if last_rsi > 70 else "neutral"
        signals["rsi"] = {"value": round(last_rsi, 2), "state": state}

    m, s, h = macd(close)
    if len(m) >= 2 and not pd.isna(m.iloc[-1]) and not pd.isna(m.iloc[-2]):
        cross = None
        if m.iloc[-2] < s.iloc[-2] and m.iloc[-1] >= s.iloc[-1]:
            cross = "bullish_cross"
        elif m.iloc[-2] > s.iloc[-2] and m.iloc[-1] <= s.iloc[-1]:
            cross = "bearish_cross"
        else:
            cross = "bullish" if m.iloc[-1] > s.iloc[-1] else "bearish"
        signals["macd"] = {"state": cross}

    u, mid, l = bbands(close)
    last_close = float(close.iloc[-1])
    last_upper = float(u.iloc[-1]) if not pd.isna(u.iloc[-1]) else None
    last_lower = float(l.iloc[-1]) if not pd.isna(l.iloc[-1]) else None
    if last_upper and last_lower:
        band_range = last_upper - last_lower
        if band_range > 0:
            pos = (last_close - last_lower) / band_range
            state = "near_upper" if pos > 0.8 else "near_lower" if pos < 0.2 else "middle"
            signals["bbands"] = {"state": state}

    t, k, sa, sb, ch = ichimoku(high, low, close)
    above_cloud = None
    if not pd.isna(sa.iloc[-1]) and not pd.isna(sb.iloc[-1]):
        cloud_top = max(float(sa.iloc[-1]), float(sb.iloc[-1]))
        cloud_bot = min(float(sa.iloc[-1]), float(sb.iloc[-1]))
        above_cloud = last_close > cloud_top
        below_cloud = last_close < cloud_bot
    tk_cross = None
    if len(t) >= 2 and not pd.isna(t.iloc[-1]) and not pd.isna(t.iloc[-2]):
        if t.iloc[-2] < k.iloc[-2] and t.iloc[-1] >= k.iloc[-1]:
            tk_cross = "bullish_cross"
        elif t.iloc[-2] > k.iloc[-2] and t.iloc[-1] <= k.iloc[-1]:
            tk_cross = "bearish_cross"
    signals["ichimoku"] = {
        "above_cloud": above_cloud,
        "tenkan_kijun": tk_cross,
    }

    last_atr = atr(high, low, close).iloc[-1]
    if not pd.isna(last_atr):
        signals["atr"] = {
            "value": round(float(last_atr), 4),
            "stop_loss_2atr": round(last_close - 2 * float(last_atr), 4),
        }

    last_hv = hv(close).iloc[-1]
    if not pd.isna(last_hv):
        hv_val = round(float(last_hv), 2)
        hv_state = "low" if hv_val < 15 else "high" if hv_val > 30 else "normal"
        signals["hv"] = {"value": hv_val, "state": hv_state}

    return signals
