from concurrent.futures import ThreadPoolExecutor
import pandas as pd

from src.prophet_cache import (
    hash_dataframe,
    load_cached_model,
    save_model,
    load_cached_forecast,
    save_forecast,
    train_prophet_model,
)


class ProphetForecast:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def run_prophet(
        self, sku: str, df: pd.DataFrame, horizon: int
    ) -> pd.DataFrame | None:
        if df.empty or len(df) < 2:
            return None

        df = df.copy()
        df["y"] = df["y"].clip(lower=0)

        df_hash = hash_dataframe(df)

        model = load_cached_model(sku, df_hash)
        if model is None:
            model = train_prophet_model(df)
            save_model(model, sku, df_hash)

        forecast = load_cached_forecast(sku, df_hash, horizon)
        if forecast is None:
            future = model.make_future_dataframe(periods=horizon)
            forecast = model.predict(future)
            save_forecast(forecast, sku, df_hash, horizon)

        return forecast

    def predict_async(
        self, sku: str, sku_df: pd.DataFrame, periods: int
    ) -> tuple[str, pd.DataFrame, pd.DataFrame | None, Exception | None]:
        try:
            forecast = self.run_prophet(sku, sku_df, periods)
            return sku, sku_df, forecast, None
        except Exception as e:
            return sku, sku_df, None, e
