from decimal import Decimal

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.smart_components.position_executor.data_types import CloseType
from hummingbot.smart_components.position_executor.safe_profit_position_config import SafeProfitPositionConfig
from hummingbot.smart_components.position_executor.safe_profit_position_executor import SafeProfitPositionExecutor
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class HiLow(DirectionalStrategyBase):
    directional_strategy_name: str = "HiLow"
    # Define the trading pair and exchange that we want to use and the csv where we are going to store the entries
    trading_pair: str = "BTC-TUSD"
    # exchange: str = "binance"
    # exchange = "binance_paper_trade"
    exchange = "binance"
    order_amount_usd = Decimal("100")
    open_order_type = OrderType.LIMIT
    take_profit_order_type: OrderType = OrderType.LIMIT
    # stop_loss_order_type: OrderType = OrderType.LIMIT
    cooldown_after_execution = 0
    # Configure the parameters for the position
    max_executors: int = 1
    stop_loss: float = 0.008
    take_profit: float = 0.01
    time_limit: int = None
    open_order_time_limit: int = 300
    trailing_stop_activation_delta = 0.15 + 0.0015  # take profit + fee
    trailing_stop_trailing_delta = 0.01

    candles = [CandlesFactory.get_candle(connector="binance",
                                         trading_pair=trading_pair,
                                         interval="5m", max_records=10)]
    markets = {exchange: {trading_pair}}

    whale_diff = 0.01
    bars_look_back = 4

    @property
    def last_tick_timestamp(self):
        return self.current_timestamp

    def on_tick(self):
        self.clean_and_store_executors()
        # self.stored_executors
        if self.is_perpetual:
            self.check_and_set_leverage()
        if self.max_active_executors_condition and self.all_candles_ready and self.time_between_signals_condition:
            position_config = self.get_position_config()
            if position_config:
                signal_executor = SafeProfitPositionExecutor(
                    strategy=self,
                    position_config=position_config,
                )
                self.active_executors.append(signal_executor)

    def is_last_executor_unprofitable(self):
        if len(self.stored_executors) > 0:
            return self.stored_executors[-1].close_type == CloseType.STOP_LOSS
        else:
            return False

    def get_position_config(self):
        side = TradeType.BUY
        price = self.buy_price
        position_config = SafeProfitPositionConfig(
            timestamp=self.last_tick_timestamp,
            trading_pair=self.trading_pair,
            exchange=self.exchange,
            side=side,
            amount=self.order_amount_usd / price,
            take_profit=self.take_profit,
            stop_loss=self.stop_loss,
            time_limit=self.time_limit,
            entry_price=price,
            open_order_type=self.open_order_type,
            take_profit_order_type=self.take_profit_order_type,
            stop_loss_order_type=self.stop_loss_order_type,
            time_limit_order_type=self.time_limit_order_type,
            # trailing_stop=TrailingStop(
            #     activation_price_delta=self.trailing_stop_activation_delta,
            #     trailing_delta=self.trailing_stop_trailing_delta
            # ),
            leverage=self.leverage,
            safe_profit=Decimal(0.37),
            safe_profit_apply_after=60 * 5 * 270,
            downtrend_skew=0.35,
            open_order_time_limit=self.open_order_time_limit
        )
        return position_config

    def get_signal(self):
        """
        -1 sell, 0 hold, 1 buy.
        """
        if self.buy_price >= self.best_ask:
            return 1
        else:
            return 0

    def market_data_extra_info(self):
        """
        Provides additional information about the market data to the format status.
        Returns:
            List[str]: A list of formatted strings containing market data information.
        """
        lines = []
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume"]
        candles_df = self.candles[0].candles_df
        lines.extend([f"Candles: {self.candles[0].name} | Interval: {self.candles[0].interval}\n"])
        lines.extend(self.candles_formatted_list(candles_df, columns_to_show))
        lines.extend([f"Expected buy price: {self.buy_price}, ask: {self.best_ask}"])
        lines.extend([f"Buy-Ask diff: {self.best_ask - self.buy_price}"])
        return lines

    @property
    def buy_price(self):
        return round(Decimal(self.highest_low) * Decimal(1 - self.whale_diff), 4)

    @property
    def highest_low(self):
        return self.candles[0].candles_df.tail(self.bars_look_back)['low'].max()

    @property
    def best_ask(self):
        return self.connectors[self.exchange].get_price_by_type(self.trading_pair, PriceType.BestAsk)
