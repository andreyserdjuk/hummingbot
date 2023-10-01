from datetime import datetime

import pandas as pd

from hummingbot import data_path

trading_pair = "BTC-TUSD"

# Create a sample DataFrame
csv_path = data_path() + "/candles_binance_BTC-TUSD_5m.csv"
df = pd.read_csv(csv_path)


def log(s):
    print(s)


window_size = 5
df['highest_low_15'] = df['low'].rolling(window=window_size).max()
df['hit'] = (df['highest_low_15'] - df['low']) / df['highest_low_15'] * 100
# df['buy_hit'] = df['hit'] >= 1
# df['entry_long'] = df['buy_signal'] & (df['buy_signal'] != df['buy_signal'].shift(1))

# print(df[df['buy_signal'] == 1][['low', 'highest_low_15', 'hit', 'buy_signal', 'entry_long']].tail(50))
# print(df.iloc[5520:5540][['low', 'highest_low_15', 'hit', 'buy_signal', 'entry_long']])

asset_amount = 100
fee = 0.075

whale_diff = 1
take_profit = 1.3
i_downtrend_skew = 0.35
stop_loss = 0.65
decreased_profit_after_bars_count = 270
decreased_profit_value = 0.37

buy_price = profit_price = profit_price_decreased = loss_price = bought_amount = None
total_profit = 0
opened_position_length = 0
buy_diff = whale_diff
is_downtrend = False

for i, row in df.iterrows():
    if df.iloc[i - 8]['low'] > 0 and row['low'] > df.iloc[i - 8]['low'] and row['low'] > df.iloc[i - 9]['low']:
        is_downtrend = False

    if buy_price is None:
        buy_percentage = (buy_diff if not is_downtrend else buy_diff + i_downtrend_skew)
        if row['hit'] >= buy_percentage:
            buy_price = row['highest_low_15'] * (1 - buy_percentage / 100)
            row['bought_amount'] = bought_amount = asset_amount / buy_price * (1 - fee / 100)
            profit_price = buy_price * (1 + take_profit / 100)
            profit_price_decreased = buy_price * (1 + decreased_profit_value / 100)
            loss_price = buy_price * (1 - stop_loss / 100)
            at = datetime.fromtimestamp(row['timestamp'] / 1000)
            # log(f'{at} buy_price:    {buy_price}, profit_price: {profit_price}, loss_price: {loss_price}')
    else:
        if opened_position_length > decreased_profit_after_bars_count:
            profit_price = profit_price_decreased

        opened_position_length += 1

        if row['high'] >= profit_price:
            profit = bought_amount * profit_price * (1 - fee / 100) - asset_amount
            row['profit'] = profit
            total_profit += profit
            log(f'profit: {profit}')
            buy_price = None
            opened_position_length = 0
            is_downtrend = False
        elif row['low'] <= loss_price:
            profit = bought_amount * loss_price * (1 - fee / 100) - asset_amount
            total_profit += profit
            row['profit'] = profit
            log(f'profit: {profit}')
            buy_price = None
            opened_position_length = 0
            is_downtrend = True


log(total_profit)
