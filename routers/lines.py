from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import yfinance as yf
import pandas as pd
import uuid
from core.line_detector import detect_lines, get_lines, save_line, update_line, delete_line

router = APIRouter()


def _fetch_df(symbol: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


@router.get("/api/lines/detect")
def detect(symbol: str, period: str = "6mo", interval: str = "1d",
           types: str = "horizontal,trend,channel,fibonacci", max_lines: int = 10):
    df = _fetch_df(symbol, period, interval)
    lines = detect_lines(df, types=types, max_lines=max_lines)
    return {"symbol": symbol, "lines": lines}


@router.get("/api/lines")
def list_lines(symbol: str = None, status: str = "active"):
    return {"lines": get_lines(symbol, status)}


class HorizontalLineRequest(BaseModel):
    symbol: str
    type: str = "horizontal"
    role: str = "support"
    price: float


class TrendLineRequest(BaseModel):
    symbol: str
    type: str = "trend"
    direction: str = "ascending"
    point1: dict
    point2: dict


@router.post("/api/lines")
def create_line(body: dict):
    line_type = body.get("type", "horizontal")
    line = {**body, "id": f"line_{uuid.uuid4().hex[:8]}", "status": "active", "score": 0.5}
    save_line(line)
    return line


@router.patch("/api/lines/{line_id}")
def patch_line(line_id: str, body: dict):
    result = update_line(line_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Line not found.")
    return result


@router.delete("/api/lines/{line_id}")
def remove_line(line_id: str):
    if not delete_line(line_id):
        raise HTTPException(status_code=404, detail="Line not found.")
    return {"status": "deleted"}
