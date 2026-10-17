from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.simulator import simulator

router = APIRouter()


class OrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: float
    order_type: str = "market"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    source: str = "manual"


class ResetRequest(BaseModel):
    initial_cash: float = 1_000_000
    base_currency: str = "JPY"
    commission_model: Optional[dict] = None
    slippage_pct: float = 0.05
    risk_limits: Optional[dict] = None


@router.post("/api/sim/order")
def place_order(req: OrderRequest):
    result = simulator.place_order(
        symbol=req.symbol,
        side=req.side,
        quantity=req.quantity,
        order_type=req.order_type,
        limit_price=req.limit_price,
        stop_price=req.stop_price,
        take_profit=req.take_profit,
        stop_loss=req.stop_loss,
        source=req.source,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/api/sim/portfolio")
def get_portfolio():
    return simulator.get_portfolio()


@router.get("/api/sim/orders")
def get_orders(symbol: str = None, source: str = None, limit: int = 50):
    orders = simulator.orders
    if symbol:
        orders = [o for o in orders if o.symbol == symbol]
    if source:
        orders = [o for o in orders if o.source == source]
    return {"orders": [o.__dict__ for o in orders[-limit:]]}


@router.get("/api/sim/summary")
def get_summary():
    return simulator.get_summary()


@router.post("/api/sim/reset")
def reset(req: ResetRequest):
    simulator.reset(
        initial_cash=req.initial_cash,
        base_currency=req.base_currency,
        commission_model=req.commission_model,
        slippage_pct=req.slippage_pct,
        risk_limits=req.risk_limits,
    )
    return {"status": "ok", "initial_cash": req.initial_cash}


@router.get("/api/sim/agent/status")
def agent_status():
    from datetime import datetime, timezone
    return {
        "status": simulator.agent_status,
        "stopped_reason": simulator.agent_stopped_reason,
        "last_order_at": simulator.last_order_at,
        "drawdown_limit_pct": simulator.risk_limits.get("max_drawdown_pct"),
    }


@router.post("/api/sim/agent/pause")
def agent_pause():
    simulator.agent_status = "paused"
    return {"status": "paused"}


@router.post("/api/sim/agent/resume")
def agent_resume():
    simulator.agent_status = "running"
    simulator.agent_stopped_reason = None
    return {"status": "running"}
