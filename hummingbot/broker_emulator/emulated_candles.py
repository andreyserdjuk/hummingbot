import pandas as pd


class EmulatedSpotCandles:
    candles_df: pd.DataFrame

    def __init__(self, df):
        self.candles_df = df

    @property
    def is_ready(self):
        return True
