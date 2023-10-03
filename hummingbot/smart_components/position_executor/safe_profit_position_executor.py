from datetime import datetime
from decimal import Decimal

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.events import MarketOrderFailureEvent
from hummingbot.smart_components.position_executor.data_types import CloseType, PositionExecutorStatus
from hummingbot.smart_components.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.position_executor.safe_profit_position_config import SafeProfitPositionConfig
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SafeProfitPositionExecutor(PositionExecutor):
    def __init__(self, strategy: ScriptStrategyBase, position_config: SafeProfitPositionConfig):
        super().__init__(strategy, position_config)

    def time_limit_condition(self):
        return self._strategy.last_tick_timestamp >= self.end_time

    def control_open_order(self):
        if not self.open_order.order_id:
            if not self.end_time or self.end_time >= self._strategy.last_tick_timestamp:
                self.place_open_order()
            else:
                self.executor_status = PositionExecutorStatus.COMPLETED
                self.close_type = CloseType.EXPIRED
                self.terminate_control_loop()
        else:
            self.control_open_order_expiration()

    def control_open_order_expiration(self):
        if self.end_open_order_time and self.end_open_order_time <= self._strategy.last_tick_timestamp:
            self._strategy.cancel(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                order_id=self._open_order.order_id
            )
            self.logger().info("Removing open order by time limit")

    def control_take_profit(self):
        if self.take_profit_order_type.is_limit_type():
            if not self.take_profit_order.order_id:
                self.place_take_profit_limit_order()
            elif (
                    self.take_profit_order_type == OrderType.MARKET
                    and self.take_profit_order.executed_amount_base != self.open_order.executed_amount_base
            ) or (self.take_profit_order.order and self.take_profit_price != self.take_profit_order.order.price):
                self.renew_take_profit_order()
        elif self.take_profit_condition():
            self.place_close_order(close_type=CloseType.TAKE_PROFIT)

    @property
    def end_open_order_time(self):
        if not self.position_config.open_order_time_limit:
            return None
        return self.position_config.timestamp + self.position_config.open_order_time_limit

    @property
    def take_profit_price(self):
        take_profit = self.position_config.safe_profit if self.safe_profit_time_limit_condition else self.position_config.take_profit
        take_profit_price = self.entry_price * (1 + take_profit) if self.side == TradeType.BUY else \
            self.entry_price * (1 - take_profit)
        return take_profit_price

    @property
    def safe_profit_time_limit_condition(self):
        end_time = self.position_config.timestamp + self.position_config.safe_profit_apply_after

        return self._strategy.last_tick_timestamp >= end_time

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        if self.open_order.order_id == event.order_id:
            self.place_open_order()
        elif self.close_order.order_id == event.order_id:
            self.place_close_order(self.close_type)
        elif self.take_profit_order.order_id == event.order_id:
            self.place_take_profit_limit_order()

    def to_format_status(self, scale=1.0):
        lines = []
        current_price = self.get_price(self.exchange, self.trading_pair)
        amount_in_quote = self.entry_price * (self.filled_amount if self.filled_amount > Decimal("0") else self.amount)
        quote_asset = self.trading_pair.split("-")[1]
        # if self.is_closed:
        created_at = datetime.fromtimestamp(self.position_config.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        lines.extend([f"{created_at}  {self.entry_price:8.6f}-{self.close_price:8.6f} {self.net_pnl * 100:7.2f}% {self.net_pnl_quote:7.4f} {quote_asset}   Amount: {amount_in_quote:7.4f} {quote_asset}"])

        if self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
            progress = 0
            if self.position_config.time_limit:
                time_scale = int(scale * 60)
                seconds_remaining = (self.end_time - self._strategy.last_tick_timestamp)
                time_progress = (self.position_config.time_limit - seconds_remaining) / self.position_config.time_limit
                time_bar = "".join(['*' if i < time_scale * time_progress else '-' for i in range(time_scale)])
                lines.extend([f"Time limit: {time_bar}"])

            if self.position_config.take_profit and self.position_config.stop_loss:
                price_scale = int(scale * 60)
                stop_loss_price = self.stop_loss_price
                take_profit_price = self.take_profit_price
                if self.side == TradeType.BUY:
                    price_range = take_profit_price - stop_loss_price
                    progress = (current_price - stop_loss_price) / price_range
                elif self.side == TradeType.SELL:
                    price_range = stop_loss_price - take_profit_price
                    progress = (stop_loss_price - current_price) / price_range
                price_bar = [f'--{current_price:.5f}--' if i == int(price_scale * progress) else '-' for i in
                             range(price_scale)]
                price_bar.insert(0, f"SL:{stop_loss_price:.5f}")
                price_bar.append(f"TP:{take_profit_price:.5f}")
                lines.extend(["".join(price_bar)])
            if self.trailing_stop_config:
                lines.extend([
                    f"Trailing stop status: {self._trailing_stop_activated} | Trailing stop price: {self._trailing_stop_price:.5f}"])
        return lines

    @property
    def cum_fee_quote(self):
        return self.open_order.cum_fees + self.close_order.cum_fees + self.take_profit_order.cum_fees
