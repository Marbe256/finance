import numpy as np
import pandas as pd
from scipy import stats
import uuid


def _pivot_highs(high: pd.Series, window: int = 5) -> list[int]:
    pivots = []
    for i in range(window, len(high) - window):
        if high.iloc[i] == high.iloc[i - window:i + window + 1].max():
            pivots.append(i)
    return pivots


def _pivot_lows(low: pd.Series, window: int = 5) -> list[int]:
    pivots = []
    for i in range(window, len(low) - window):
        if low.iloc[i] == low.iloc[i - window:i + window + 1].min():
            pivots.append(i)
    return pivots


def _cluster_prices(prices: list[float], tolerance_pct: float = 0.5) -> list[float]:
    if not prices:
        return []
    sorted_prices = sorted(prices)
    clusters = [[sorted_prices[0]]]
    for p in sorted_prices[1:]:
        center = np.mean(clusters[-1])
        if abs(p - center) / center * 100 <= tolerance_pct:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return [round(float(np.mean(c)), 4) for c in clusters]


def _extend(slope: float, intercept: float, n: int, dates: list[str], steps: int = 15) -> dict:
    """最終バーから steps 営業日先の延長点を返す"""
    i_ext = n - 1 + steps
    price_ext = round(float(slope * i_ext + intercept), 4)
    last_date = pd.Timestamp(dates[-1])
    ext_date = (last_date + pd.tseries.offsets.BDay(steps)).strftime("%Y-%m-%d")
    return {"date": ext_date, "price": price_ext}


def detect_horizontal(df: pd.DataFrame, max_lines: int = 4) -> list[dict]:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    ph_idx = _pivot_highs(high)
    pl_idx = _pivot_lows(low)

    resistance_prices = [float(high.iloc[i]) for i in ph_idx]
    support_prices = [float(low.iloc[i]) for i in pl_idx]

    r_clusters = _cluster_prices(resistance_prices)
    s_clusters = _cluster_prices(support_prices)

    lines = []
    current_price = float(close.iloc[-1])

    for price in r_clusters:
        touches = sum(1 for p in resistance_prices if abs(p - price) / price * 100 < 0.5)
        dist_pct = abs(price - current_price) / current_price * 100
        score = round(min(touches / 5, 1.0) * 0.5 + max(0, 1 - dist_pct / 20) * 0.5, 3)
        # タッチ2回以上を「強」とする
        strength = "strong" if touches >= 2 else "weak"
        lines.append({
            "id": f"line_{uuid.uuid4().hex[:8]}",
            "type": "horizontal",
            "role": "resistance",
            "strength": strength,
            "price": price,
            "touches": touches,
            "score": score,
            "status": "active",
        })

    for price in s_clusters:
        touches = sum(1 for p in support_prices if abs(p - price) / price * 100 < 0.5)
        dist_pct = abs(price - current_price) / current_price * 100
        score = round(min(touches / 5, 1.0) * 0.5 + max(0, 1 - dist_pct / 20) * 0.5, 3)
        strength = "strong" if touches >= 2 else "weak"
        lines.append({
            "id": f"line_{uuid.uuid4().hex[:8]}",
            "type": "horizontal",
            "role": "support",
            "strength": strength,
            "price": price,
            "touches": touches,
            "score": score,
            "status": "active",
        })

    lines.sort(key=lambda x: x["score"], reverse=True)
    return lines[:max_lines]


def _fit_trendline(series: pd.Series, pivot_idx: list[int], dates: list[str], n: int,
                   side: str = "support") -> dict | None:
    """ピボット点群から最適なトレンドラインを選ぶ。
    side='support': 安値ライン — 全ピボット点が線上または線より上になるペアを選ぶ
    side='resistance': 高値ライン — 全ピボット点が線上または線より下になるペアを選ぶ
    直近の2点から始めて、違反がなければ採用する。なければ古い点に広げる。
    """
    if len(pivot_idx) < 2:
        return None
    candidates = pivot_idx[-8:]
    vals = [float(series.iloc[i]) for i in candidates]

    best = None
    # 直近ペアを優先: 後ろのインデックスから前に向かって探す
    for b in range(len(candidates) - 1, 0, -1):
        for a in range(b - 1, -1, -1):
            ia, ib = candidates[a], candidates[b]
            ya, yb = vals[a], vals[b]
            if ia == ib:
                continue
            slope = (yb - ya) / (ib - ia)
            intercept = ya - slope * ia

            # 全ピボット点が正しい側にあるかチェック
            ok = True
            for k, idx_k in enumerate(candidates):
                predicted = slope * idx_k + intercept
                if side == "support" and vals[k] < predicted - 0.001:
                    ok = False
                    break
                if side == "resistance" and vals[k] > predicted + 0.001:
                    ok = False
                    break
            if not ok:
                continue

            # スパンが長くて直近バーに近いほど高スコア
            span_score = (ib - ia) / n
            recency_score = ib / n
            score = round(span_score * 0.5 + recency_score * 0.5, 3)
            if best is None or score > best["score"]:
                best = {"ia": ia, "ib": ib, "slope": slope, "intercept": intercept, "score": score}

    if best is None:
        # 違反なしのペアが見つからない場合は直近2点をそのまま使う
        ia, ib = candidates[-2], candidates[-1]
        slope = (vals[-1] - vals[-2]) / (ib - ia) if ib != ia else 0
        intercept = vals[-2] - slope * ia
        best = {"ia": ia, "ib": ib, "slope": slope, "intercept": intercept, "score": 0.1}

    xall = np.array(candidates, dtype=float)
    yall = np.array(vals)
    _, _, r, _, _ = stats.linregress(xall, yall)
    best["r_squared"] = round(float(r**2), 3)
    return best


def detect_trendlines(df: pd.DataFrame, max_lines: int = 2) -> list[dict]:
    high = df["High"]
    low = df["Low"]
    dates = df.index.strftime("%Y-%m-%d").tolist()
    n = len(dates)

    ph_idx = _pivot_highs(high, window=3)
    pl_idx = _pivot_lows(low, window=3)

    lines = []

    # 安値トレンドライン（サポート）
    pl_best = _fit_trendline(low, pl_idx, dates, n, side="support")
    if pl_best:
        ia, ib = pl_best["ia"], pl_best["ib"]
        slope, intercept = pl_best["slope"], pl_best["intercept"]
        lines.append({
            "id": f"line_{uuid.uuid4().hex[:8]}",
            "type": "trend",
            "role": "support",
            "direction": "ascending" if slope >= 0 else "descending",
            "point1": {"date": dates[ia], "price": round(float(low.iloc[ia]), 4)},
            "point2": {"date": dates[ib], "price": round(float(low.iloc[ib]), 4)},
            "point_extended": _extend(slope, intercept, n, dates),
            "slope": round(float(slope), 6),
            "r_squared": pl_best["r_squared"],
            "score": pl_best["score"],
            "status": "active",
        })

    # 高値トレンドライン（レジスタンス）
    ph_best = _fit_trendline(high, ph_idx, dates, n, side="resistance")
    if ph_best:
        ia, ib = ph_best["ia"], ph_best["ib"]
        slope, intercept = ph_best["slope"], ph_best["intercept"]
        lines.append({
            "id": f"line_{uuid.uuid4().hex[:8]}",
            "type": "trend",
            "role": "resistance",
            "direction": "ascending" if slope >= 0 else "descending",
            "point1": {"date": dates[ia], "price": round(float(high.iloc[ia]), 4)},
            "point2": {"date": dates[ib], "price": round(float(high.iloc[ib]), 4)},
            "point_extended": _extend(slope, intercept, n, dates),
            "slope": round(float(slope), 6),
            "r_squared": ph_best["r_squared"],
            "score": ph_best["score"],
            "status": "active",
        })

    lines.sort(key=lambda x: x["score"], reverse=True)
    return lines[:max_lines]


def detect_channels(df: pd.DataFrame, trend_lines: list[dict]) -> list[dict]:
    """トレンドラインと平行なチャンネルラインを生成する。
    サポートライン → 平行な高値ライン (channel_upper)
    レジスタンスライン → 平行な安値ライン (channel_lower)
    オフセットはピボット点の反対側最大偏差で決める。
    """
    dates = df.index.strftime("%Y-%m-%d").tolist()
    n = len(dates)
    channels = []

    # ピボット点を取得（チャンネルのタッチ点探索用）
    ph_idx = _pivot_highs(df["High"], window=3)
    pl_idx = _pivot_lows(df["Low"], window=3)

    for tl in trend_lines:
        if tl["type"] != "trend":
            continue
        slope = tl["slope"]
        i0 = dates.index(tl["point1"]["date"]) if tl["point1"]["date"] in dates else 0
        intercept_tl = tl["point1"]["price"] - slope * i0

        # トレンドラインの時間範囲（始点〜終点のインデックス）内に限定してオフセットを計算
        i_start = dates.index(tl["point1"]["date"]) if tl["point1"]["date"] in dates else 0
        i_end = dates.index(tl["point2"]["date"]) if tl["point2"]["date"] in dates else n - 1

        if tl["role"] == "support":
            # サポートラインの上側にチャンネル上限を引く
            # 同期間内のピボット高値との最大距離をオフセットとして使う
            ph_in_range = [i for i in ph_idx if i_start <= i <= i_end]
            if not ph_in_range:
                ph_in_range = ph_idx  # 範囲内になければ全体から
            offsets = [float(df["High"].iloc[i]) - (slope * i + intercept_tl) for i in ph_in_range]
            offset = max(offsets)
            if offset <= 0:
                continue
            intercept_ch = intercept_tl + offset
            role = "channel_upper"
        else:
            # レジスタンスラインの下側にチャンネル下限を引く
            # 同期間内のピボット安値との最大距離をオフセットとして使う
            pl_in_range = [i for i in pl_idx if i_start <= i <= i_end]
            if not pl_in_range:
                pl_in_range = pl_idx
            offsets = [(slope * i + intercept_tl) - float(df["Low"].iloc[i]) for i in pl_in_range]
            offset = max(offsets)
            if offset <= 0:
                continue
            intercept_ch = intercept_tl - offset
            role = "channel_lower"

        price_ch_start = round(float(slope * i0 + intercept_ch), 4)
        i1 = n - 1
        price_ch_end = round(float(slope * i1 + intercept_ch), 4)
        ext = _extend(slope, intercept_ch, n, dates)

        channels.append({
            "id": f"line_{uuid.uuid4().hex[:8]}",
            "type": "channel",
            "role": role,
            "direction": tl["direction"],
            "point1": {"date": dates[i0], "price": price_ch_start},
            "point2": {"date": dates[i1], "price": price_ch_end},
            "point_extended": ext,
            "slope": round(float(slope), 6),
            "score": tl["score"] * 0.8,
            "status": "active",
        })

    return channels


def detect_fibonacci(df: pd.DataFrame) -> list[dict]:
    """直近高値〜安値間のフィボナッチリトレースメント（38.2% / 61.8%）"""
    high = df["High"]
    low = df["Low"]
    dates = df.index.strftime("%Y-%m-%d").tolist()

    swing_high = float(high.max())
    swing_low = float(low.min())
    diff = swing_high - swing_low

    lines = []
    for ratio, label in [(0.382, "fib_382"), (0.618, "fib_618")]:
        price = round(swing_high - diff * ratio, 4)
        lines.append({
            "id": f"line_{uuid.uuid4().hex[:8]}",
            "type": "fibonacci",
            "role": label,
            "price": price,
            "ratio": ratio,
            "swing_high": round(swing_high, 4),
            "swing_low": round(swing_low, 4),
            "score": 0.5,
            "status": "active",
        })
    return lines


_line_store: dict[str, dict] = {}

# 10本構成: 水平4(強弱2+2) / トレンド2 / チャンネル2 / フィボ2
_COUNTS = {"horizontal": 4, "trend": 2, "channel": 2, "fibonacci": 2}


def detect_lines(df: pd.DataFrame, types: str = "horizontal,trend", max_lines: int = 10) -> list[dict]:
    type_list = [t.strip() for t in types.split(",")]
    lines = []

    if "horizontal" in type_list:
        lines += detect_horizontal(df, max_lines=_COUNTS["horizontal"])

    trend_lines = []
    if "trend" in type_list:
        trend_lines = detect_trendlines(df, max_lines=_COUNTS["trend"])
        lines += trend_lines

    if "channel" in type_list and trend_lines:
        lines += detect_channels(df, trend_lines)

    if "fibonacci" in type_list:
        lines += detect_fibonacci(df)

    result = lines[:max_lines]
    for line in result:
        _line_store[line["id"]] = line
    return result


def get_lines(symbol: str = None, status: str = "active") -> list[dict]:
    lines = list(_line_store.values())
    if status != "all":
        lines = [l for l in lines if l.get("status") == status]
    return lines


def save_line(line: dict) -> dict:
    _line_store[line["id"]] = line
    return line


def update_line(line_id: str, updates: dict) -> dict | None:
    if line_id not in _line_store:
        return None
    _line_store[line_id].update(updates)
    return _line_store[line_id]


def delete_line(line_id: str) -> bool:
    if line_id in _line_store:
        _line_store[line_id]["status"] = "deleted"
        return True
    return False
