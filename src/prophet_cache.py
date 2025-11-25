import hashlib
from typing import Optional
import joblib
import pandas as pd
from pathlib import Path
from prophet import Prophet
import pickle

CACHE_DIR = Path("cache/prophet")
MODELS_DIR = CACHE_DIR / "models"
FORECAST_DIR = CACHE_DIR / "forecasts"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
FORECAST_DIR.mkdir(parents=True, exist_ok=True)


def hash_dataframe(df: pd.DataFrame) -> str:
    df_sorted = df.sort_values(df.columns.tolist()).reset_index(drop=True)
    text = df_sorted.to_csv(index=False)
    return hashlib.sha256(text.encode()).hexdigest()


def get_model_path(sku: str, data_hash: str) -> Path:
    safe_sku = "".join(c for c in sku if c.isalnum() or c in "_-")
    return MODELS_DIR / f"{safe_sku}_{data_hash}.pkl"


def get_forecast_path(sku: str, data_hash: str, horizon: int) -> Path:
    safe_sku = "".join(c for c in sku if c.isalnum() or c in "_-")
    return FORECAST_DIR / f"{safe_sku}_{data_hash}_{horizon}.pkl"


def load_cached_model(sku: str, df_hash: str) -> Optional[Prophet]:
    path = get_model_path(sku, df_hash)
    if path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def save_model(model: Prophet, sku: str, df_hash: str) -> None:
    path = get_model_path(sku, df_hash)
    with open(path, "wb") as f:
        pickle.dump(model, f)


def load_cached_forecast(
    sku: str, df_hash: str, horizon: int
) -> Optional[pd.DataFrame]:
    path = get_forecast_path(sku, df_hash, horizon)
    if path.exists():
        return joblib.load(path)
    return None


def save_forecast(forecast: pd.DataFrame, sku: str, df_hash: str, horizon: int) -> None:
    path = get_forecast_path(sku, df_hash, horizon)
    joblib.dump(forecast, path)


def train_prophet_model(df: pd.DataFrame) -> Prophet:
    model = Prophet()
    model.fit(df)
    return model
