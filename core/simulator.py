import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
import yfinance as yf
from core.fx import to_jpy


@dataclass
class Position:
    symbol: str
    asset_type: str
    quantity: float
    avg_price: float
    currency: str = "USD"


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    limit_price: Optional[float]
    stop_price: Optional[float]
    take_profit: Optional[float]
    stop_loss: Optional[float]
    source: str
    status: str
    filled_price: Optional[float]
    slippage: float
    commission: float
    filled_at: Optional[str]
    pnl_realized: Optional[float]


class SimulatorState:
    def __init__(self):
        self.reset()

    def reset(
        self,
        initial_cash: float = 1_000_000,
        base_currency: str = "JPY",
        commission_model: dict = None,
        slippage_pct: float = 0.05,
        risk_limits: dict = None,
    ):
        self.cash = initial_cash
        self.base_currency = base_currency
        self.commission_model = commission_model or {
            "stock_pct": 0.1,
            "forex_pct": 0.02,
            "crypto_pct": 0.1,
            "commodity_pct": 0.05,
        }
        self.slippage_pct = slippage_pct
        self.risk_limits = risk_limits or {
            "max_drawdown_pct": 20.0,
            "max_position_pct": 30.0,
            "leverage_limit": 3.0,
        }
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self.total_realized_pnl: float = 0.0
        self.total_commission_paid: float = 0.0
        self.peak_value: float = initial_cash
        self.agent_status: str = "running"
        self.agent_stopped_reason: Optional[str] = None
        self.last_order_at: Optional[str] = None

    def _asset_type(self, symbol: str) -> str:
        if symbol.endswith("=X"):
            return "forex"
        if symbol.endswith("=F"):
            return "commodity"
        if "-USD" in symbol or "-JPY" in symbol or "-BTC" in symbol:
            return "crypto"
        return "stock"

    def _currency(self, symbol: str) -> str:
        t = self._asset_type(symbol)
        if t == "forex" or (t == "stock" and symbol.endswith(".T")):
            return "JPY"
        return "USD"

    def _commission_rate(self, asset_type: str) -> float:
        return self.commission_model.get(f"{asset_type}_pct", 0.1) / 100

    def _get_price(self, symbol: str) -> Optional[float]:
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass
        return None

    def place_order(self, symbol: str, side: str, quantity: float,
                    order_type: str = "market", limit_price=None,
                    stop_price=None, take_profit=None, stop_loss=None,
                    source: str = "manual") -> dict:
        if self.agent_status == "stopped_by_risk" and source == "agent":
            return {"error": "agent_stopped", "message": "Agent stopped by risk limit."}

        price = self._get_price(symbol)
        if price is None:
            return {"error": "price_unavailable", "message": f"Cannot get price for {symbol}"}

        slippage = price * (self.slippage_pct / 100)
        filled_price = price + slippage if side == "buy" else price - slippage

        asset_type = self._asset_type(symbol)
        commission = filled_price * quantity * self._commission_rate(asset_type)
        total_cost = filled_price * quantity + commission

        pnl_realized = None
        if side == "buy":
            if self.cash < total_cost:
                return {"error": "insufficient_cash", "message": "Not enough cash."}
            self.cash -= total_cost
            if symbol in self.positions:
                pos = self.positions[symbol]
                total_qty = pos.quantity + quantity
                pos.avg_price = (pos.avg_price * pos.quantity + filled_price * quantity) / total_qty
                pos.quantity = total_qty
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    asset_type=asset_type,
                    quantity=quantity,
                    avg_price=filled_price,
                    currency=self._currency(symbol),
                )
        else:
            if symbol not in self.positions or self.positions[symbol].quantity < quantity:
                return {"error": "insufficient_position", "message": "Not enough position to sell."}
            pos = self.positions[symbol]
            pnl_realized = (filled_price - pos.avg_price) * quantity - commission
            self.total_realized_pnl += pnl_realized
            self.cash += filled_price * quantity - commission
            pos.quantity -= quantity
            if pos.quantity <= 0:
                del self.positions[symbol]

        self.total_commission_paid += commission

        order = Order(
            order_id=f"ord_{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            source=source,
            status="filled",
            filled_price=round(filled_price, 4),
            slippage=round(slippage, 4),
            commission=round(commission, 4),
            filled_at=datetime.now(timezone.utc).isoformat(),
            pnl_realized=round(pnl_realized, 4) if pnl_realized is not None else None,
        )
        self.orders.append(order)
        self.last_order_at = order.filled_at
        self._check_risk()
        return order.__dict__

    def get_portfolio(self) -> dict:
        positions_out = []
        total_value = self.cash

        for symbol, pos in self.positions.items():
            price = self._get_price(symbol) or pos.avg_price
            market_value = price * pos.quantity
            market_value_jpy = to_jpy(market_value, pos.currency)
            unrealized_pnl = (price - pos.avg_price) * pos.quantity
            unrealized_pnl_pct = (price - pos.avg_price) / pos.avg_price * 100 if pos.avg_price else 0
            total_value += market_value_jpy if self.base_currency == "JPY" else market_value
            positions_out.append({
                "symbol": symbol,
                "type": pos.asset_type,
                "quantity": pos.quantity,
                "avg_price": round(pos.avg_price, 4),
                "current_price": round(price, 4),
                "market_value": round(market_value, 2),
                "market_value_jpy": round(market_value_jpy, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            })

        if total_value > self.peak_value:
            self.peak_value = total_value

        return {
            "cash": round(self.cash, 2),
            "base_currency": self.base_currency,
            "positions": positions_out,
            "total_value": round(total_value, 2),
            "total_realized_pnl": round(self.total_realized_pnl, 2),
            "total_commission_paid": round(self.total_commission_paid, 2),
            "max_drawdown_pct": self._current_drawdown(total_value),
        }

    def get_summary(self) -> dict:
        orders_filled = [o for o in self.orders if o.status == "filled"]
        wins = [o for o in orders_filled if o.pnl_realized and o.pnl_realized > 0]
        losses = [o for o in orders_filled if o.pnl_realized and o.pnl_realized < 0]
        total_win = sum(o.pnl_realized for o in wins)
        total_loss = abs(sum(o.pnl_realized for o in losses))
        profit_factor = round(total_win / total_loss, 2) if total_loss > 0 else None
        win_rate = round(len(wins) / len(orders_filled), 2) if orders_filled else 0
        return {
            "total_trades": len(orders_filled),
            "win_rate": win_rate,
            "total_realized_pnl": round(self.total_realized_pnl, 2),
            "total_commission_paid": round(self.total_commission_paid, 2),
            "net_pnl": round(self.total_realized_pnl, 2),
            "profit_factor": profit_factor,
            "agent_orders": len([o for o in self.orders if o.source == "agent"]),
            "manual_orders": len([o for o in self.orders if o.source == "manual"]),
        }

    def _current_drawdown(self, current_value: float) -> float:
        if self.peak_value == 0:
            return 0.0
        return round((current_value - self.peak_value) / self.peak_value * 100, 2)

    def _check_risk(self):
        portfolio = self.get_portfolio()
        dd = self._current_drawdown(portfolio["total_value"])
        limit = self.risk_limits.get("max_drawdown_pct", 20.0)
        if dd < -limit:
            self.agent_status = "stopped_by_risk"
            self.agent_stopped_reason = f"Drawdown {dd}% exceeded limit -{limit}%"


simulator = SimulatorState()
