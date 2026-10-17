import yfinance as yf
from datetime import datetime, timedelta

_PAIRS = {
    "USDJPY": "USDJPY=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "BTCJPY": "BTC-JPY",
}

_cache: dict = {}
_cache_time: datetime | None = None
_CACHE_TTL_MINUTES = 5


def get_rates() -> dict[str, float]:
    global _cache, _cache_time
    now = datetime.now()
    if _cache_time and (now - _cache_time).seconds < _CACHE_TTL_MINUTES * 60:
        return _cache

    rates = {}
    for name, ticker in _PAIRS.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                rates[name] = round(float(hist["Close"].iloc[-1]), 4)
        except Exception:
            pass

    if rates:
        _cache = rates
        _cache_time = now
    return _cache


def to_jpy(amount: float, currency: str) -> float:
    if currency == "JPY":
        return amount
    rates = get_rates()
    key = f"{currency}JPY"
    rate = rates.get(key)
    if rate is None:
        return amount
    return round(amount * rate, 2)
