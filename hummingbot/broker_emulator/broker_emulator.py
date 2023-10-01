import math
from decimal import Decimal
from typing import List, Type

import pandas as pd

from hummingbot.broker_emulator.emulated_candles import EmulatedSpotCandles
from hummingbot.broker_emulator.emulated_connector import EmulatedConnector
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    OrderCancelledEvent,
    OrderType,
    PositionAction,
    SellOrderCompletedEvent,
)
from hummingbot.smart_components.position_executor.data_types import PositionExecutorStatus
from scripts.aaa_hilow import HiLow

s_decimal_nan = Decimal("NaN")


class EmulatedHiLow(HiLow):
    candles = []

    completed_orders = []
    buy_order_price: s_decimal_nan = s_decimal_nan
    buy_order_amount: s_decimal_nan = s_decimal_nan

    sell_order_price: s_decimal_nan = s_decimal_nan
    sell_order_amount: s_decimal_nan = s_decimal_nan
    _last_tick_timestamp: float

    def __init__(self, connectors):
        self.connectors = connectors
        self.ready_to_trade: bool = True

    def tick(self, timestamp: float):
        pass

    @property
    def last_tick_timestamp(self) -> float:
        return self._last_tick_timestamp

    def buy(self,
            connector_name: str,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType,
            price=s_decimal_nan,
            position_action=PositionAction.OPEN) -> str:
        self.buy_order_price = price
        self.buy_order_amount = amount
        # if self.candles[0].candles_df.iloc[-1]['low'] < price:
        #     self.completed_orders = {price: price, }

        return f"{trading_pair}-{amount}-{order_type}-{price}-{position_action}"

    def sell(self,
             connector_name: str,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType,
             price=s_decimal_nan,
             position_action=PositionAction.OPEN) -> str:
        self.sell_order_price = price
        self.sell_order_amount = amount

        return f"{trading_pair}-{amount}-{order_type}-{price}-{position_action}"

    _canceled_order_id: str = None

    def cancel(self,
               connector_name: str,
               trading_pair: str,
               order_id: str):
        self._canceled_order_id = order_id

    def get_active_orders(self, connector_name: str) -> List[LimitOrder]:
        return []

    @property
    def time_between_signals_condition(self):
        return True


def emulate__take_profit(strategy: EmulatedHiLow,
                         current_timestamp: float,
                         current_max_price: float) -> None:
    if not math.isnan(strategy.sell_order_price):
        executor = strategy.active_executors[0]

        if executor.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
            if not executor.take_profit_order.order:
                executor.take_profit_order.order = InFlightOrder(
                    executor.take_profit_order.order_id,
                    executor.trading_pair,
                    OrderType.LIMIT,
                    TradeType.SELL,
                    strategy.sell_order_amount,
                    current_timestamp,
                    strategy.sell_order_price,
                    executor.take_profit_order.order_id,
                )

            if strategy.sell_order_price <= current_max_price:
                executor.process_order_completed_event(None, None, SellOrderCompletedEvent(
                    timestamp=current_timestamp,
                    order_id=executor.take_profit_order.order_id,
                    base_asset='TUSD',
                    quote_asset='USD',
                    base_asset_amount=strategy.sell_order_amount,
                    quote_asset_amount=strategy.sell_order_amount,
                    order_type=OrderType.LIMIT,
                ))

                executor.take_profit_order.order.order_fills = {'x': TradeUpdate(
                    executor.take_profit_order.order_id,
                    executor.take_profit_order.order_id,
                    executor.take_profit_order.order_id,
                    executor.trading_pair,
                    current_timestamp,
                    strategy.sell_order_price,
                    strategy.sell_order_amount,
                    strategy.sell_order_amount,
                    TradeFeeBase.new_spot_fee(
                        fee_schema=TradeFeeSchema(),
                        trade_type=TradeType.SELL,
                    )
                )}
                # executor.take_profit_order._order.average_executed_price = strategy.sell_order_price

                strategy.sell_order_price = s_decimal_nan
                strategy.sell_order_amount = s_decimal_nan


def emulate__stop_loss(strategy: EmulatedHiLow,
                       current_timestamp: float) -> None:
    executor = strategy.active_executors[0]
    if executor.executor_status == PositionExecutorStatus.ACTIVE_POSITION and executor.close_order.order_id:
        executor.close_order.order = InFlightOrder(
            executor.close_order.order_id,
            executor.trading_pair,
            OrderType.MARKET,
            TradeType.SELL,
            strategy.sell_order_amount,
            current_timestamp,
            executor.stop_loss_price,
            executor.close_order.order_id,
        )
        executor.process_order_completed_event(None, None, SellOrderCompletedEvent(
            timestamp=current_timestamp,
            order_id=executor.close_order.order_id,
            base_asset='TUSD',
            quote_asset='USD',
            base_asset_amount=strategy.sell_order_amount,
            quote_asset_amount=strategy.sell_order_amount,
            order_type=OrderType.MARKET,
        ))
        strategy.sell_order_price = s_decimal_nan
        strategy.sell_order_amount = s_decimal_nan


def emulate__process_order_canceled_event_if_exists(strategy: EmulatedHiLow, current_timestamp: float) -> None:
    if len(strategy.active_executors) > 0 and strategy._canceled_order_id:
        executor = strategy.active_executors[0]
        executor.process_order_canceled_event(None, None, OrderCancelledEvent(
            current_timestamp,
            strategy._canceled_order_id,
            strategy._canceled_order_id
        ))
        strategy._canceled_order_id = None


# and open process_order_completed_event
def emulate__open_order_if_exists(strategy: EmulatedHiLow, current_timestamp: float,
                                  min_market_price: float) -> bool:
    result = False

    if len(strategy.active_executors) > 0:
        executor = strategy.active_executors[0]

        if executor.executor_status == PositionExecutorStatus.NOT_STARTED:
            if not executor.open_order.order and not math.isnan(strategy.buy_order_price) and not math.isnan(strategy.buy_order_amount):
                executor.open_order.order = InFlightOrder(
                    executor.close_order.order_id,
                    executor.trading_pair,
                    OrderType.LIMIT,
                    TradeType.BUY,
                    strategy.buy_order_amount,
                    current_timestamp,
                    strategy.buy_order_price,
                    executor.open_order.order_id,
                )
                strategy.buy_order_price = s_decimal_nan
                strategy.buy_order_amount = s_decimal_nan

            if executor.open_order.order.price >= min_market_price:
                executor.open_order._order.executed_amount_base = executor.open_order.order.amount

                # completed buy order
                # now executor_status == PositionExecutorStatus.ACTIVE_POSITION
                executor.process_order_completed_event(None, None, BuyOrderCompletedEvent(
                    timestamp=current_timestamp,
                    order_id=executor.open_order.order_id,
                    base_asset='TUSD',
                    quote_asset='USD',
                    base_asset_amount=executor.open_order.order.amount,
                    quote_asset_amount=executor.open_order.order.amount,
                    order_type=OrderType.LIMIT,
                ))
                result = True

    return result


class BrokerEmulator:
    async def test_strategy(self, df: pd.DataFrame, strategy_class: Type[EmulatedHiLow]):
        connector = EmulatedConnector()
        strategy = strategy_class({'binance': connector})

        for i, _ in df.iterrows():
            candles_df = df.iloc[i:i + 10]
            dfs = df.iloc[i + 10:i + 11]
            if dfs.shape[0] < 1 or candles_df.shape[0] < 10:
                break

            cur_df = dfs.iloc[-1]
            current_timestamp = cur_df['timestamp'] / 1000

            connector._mid_price = Decimal(cur_df['low'])
            strategy.candles = [EmulatedSpotCandles(candles_df)]
            strategy._last_tick_timestamp = current_timestamp
            strategy.on_tick()
            if len(strategy.active_executors) == 0:
                continue

            executor = strategy.active_executors[0]

            await executor.control_task()
            if executor.executor_status == PositionExecutorStatus.NOT_STARTED:
                if emulate__open_order_if_exists(strategy, current_timestamp, cur_df['low']):
                    # don't sell in first candle in ACTIVE_POSITION
                    continue

            emulate__process_order_canceled_event_if_exists(strategy, current_timestamp)
            emulate__stop_loss(strategy, current_timestamp)

            if executor.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
                connector._mid_price = Decimal(cur_df['high'])
                await executor.control_task()
                emulate__take_profit(strategy, current_timestamp, cur_df['high'])

        for executor in strategy.active_executors:
            executor.terminate_control_loop()

        return strategy.format_status()
