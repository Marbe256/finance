from fastapi import APIRouter
from core.simulator import simulator
from core.fx import get_rates
from datetime import datetime, timezone

router = APIRouter()

_history: list[dict] = []


def record_snapshot():
    portfolio = simulator.get_portfolio()
    by_type: dict[str, float] = {}
    for pos in portfolio["positions"]:
        t = pos["type"]
        by_type[t] = by_type.get(t, 0) + pos["market_value_jpy"]
    by_type["cash"] = portfolio["cash"]
    _history.append({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_jpy": portfolio["total_value"],
        "by_type": by_type,
    })


@router.get("/api/portfolio/summary")
def portfolio_summary():
    portfolio = simulator.get_portfolio()
    rates = get_rates()

    by_type: dict[str, dict] = {}
    total = portfolio["total_value"]

    for pos in portfolio["positions"]:
        t = pos["type"]
        if t not in by_type:
            by_type[t] = {"value_jpy": 0, "pnl_jpy": 0}
        by_type[t]["value_jpy"] += pos["market_value_jpy"]
        by_type[t]["pnl_jpy"] += pos["unrealized_pnl"]

    cash_jpy = portfolio["cash"]
    by_type["cash"] = {"value_jpy": cash_jpy, "pnl_jpy": 0}

    by_type_list = [
        {
            "type": k,
            "value_jpy": round(v["value_jpy"], 2),
            "pct": round(v["value_jpy"] / total * 100, 1) if total else 0,
            "pnl_jpy": round(v["pnl_jpy"], 2),
        }
        for k, v in by_type.items()
    ]

    return {
        "total_value_jpy": portfolio["total_value"],
        "cash_jpy": cash_jpy,
        "invested_jpy": round(total - cash_jpy, 2),
        "total_pnl_jpy": portfolio["total_realized_pnl"],
        "fx_rates": rates,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "by_type": by_type_list,
        "by_position": portfolio["positions"],
    }


@router.get("/api/portfolio/history")
def portfolio_history(period: str = "1mo", interval: str = "1d"):
    record_snapshot()
    return {"history": _history[-90:]}
