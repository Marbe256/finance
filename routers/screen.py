from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.screener import (
    run_screen, get_watchlist, add_to_watchlist, remove_from_watchlist,
    save_rule, get_rules, delete_rule, UNIVERSE_SYMBOLS,
)

router = APIRouter()


class ScreenRequest(BaseModel):
    universe: list[str]
    filters: list[dict] = []
    period: str = "6mo"
    interval: str = "1d"
    sort_by: str = "score"
    limit: int = 20


class WatchlistEntry(BaseModel):
    symbol: str
    note: str = ""


class RuleRequest(BaseModel):
    rule_id: str
    name: str
    description: str = ""
    conditions: list[dict]
    logic: str = "AND"


@router.post("/api/screen")
def screen(req: ScreenRequest):
    return run_screen(
        universe=req.universe,
        filters=req.filters,
        period=req.period,
        interval=req.interval,
        sort_by=req.sort_by,
        limit=req.limit,
    )


@router.get("/api/screen/universe")
def list_universe():
    return {
        "groups": [
            {"id": k, "label": k, "count": len(v)}
            for k, v in UNIVERSE_SYMBOLS.items()
        ] + [{"id": "watchlist", "label": "ウォッチリスト", "count": len(get_watchlist())}]
    }


@router.get("/api/watchlist")
def watchlist():
    return {"watchlist": get_watchlist()}


@router.post("/api/watchlist")
def add_watchlist(entry: WatchlistEntry):
    return add_to_watchlist(entry.symbol, entry.note)


@router.delete("/api/watchlist/{symbol}")
def del_watchlist(symbol: str):
    if not remove_from_watchlist(symbol):
        raise HTTPException(status_code=404, detail="Symbol not in watchlist.")
    return {"status": "removed"}


@router.get("/api/screen/rules")
def list_rules():
    return {"rules": get_rules()}


@router.post("/api/screen/rules")
def create_rule(req: RuleRequest):
    return save_rule(req.dict())


@router.delete("/api/screen/rules/{rule_id}")
def remove_rule(rule_id: str):
    if not delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found.")
    return {"status": "deleted"}
