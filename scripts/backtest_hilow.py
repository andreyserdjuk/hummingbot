import pandas as pd

from hummingbot import data_path
from hummingbot.broker_emulator.broker_emulator import BrokerEmulator, EmulatedHiLow
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class BacktestHiLow(ScriptStrategyBase):
    # User-defined parameters
    exchange = "binance"
    trading_pair = "ETH-USDT"
    order_amount = 0.1
    bid_spread_bps = 10
    ask_spread_bps = 10
    fee_bps = 10
    days = 7
    paper_trade_enabled = True

    # System parameters
    precision = 2
    base, quote = trading_pair.split("-")
    execution_exchange = f"{exchange}_paper_trade" if paper_trade_enabled else exchange
    interval = "1m"
    results_df = None
    # candle = CandlesFactory.get_candle(connector=exchange, trading_pair=trading_pair, interval=interval, max_records=days * 60 * 24)
    # candle.start()

    csv_path = data_path() + f"/backtest_{trading_pair}_{bid_spread_bps}_bid_{ask_spread_bps}_ask.csv"
    markets = {f"{execution_exchange}": {trading_pair}}

    render_status: str = ''
    on_going_task = False

    def format_status(self) -> str:
        return self.render_status

    def on_tick(self):
        if not self.on_going_task:
            self.on_going_task = True
            # wrap async task in safe_ensure_future
            safe_ensure_future(self.async_task())

    async def async_task(self):
        emulator = BrokerEmulator()
        csv_path = data_path() + "/candles_binance_BTC-TUSD_5m.csv"
        self.render_status = await emulator.test_strategy(pd.read_csv(csv_path), EmulatedHiLow)
