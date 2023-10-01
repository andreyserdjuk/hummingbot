from typing import Optional

from pydantic.types import Decimal

from hummingbot.smart_components.position_executor.data_types import PositionConfig


class SafeProfitPositionConfig(PositionConfig):
    open_order_time_limit: Optional[int] = None
    safe_profit: Decimal
    safe_profit_apply_after: float
    downtrend_skew: float
