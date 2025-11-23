from typing import Any
import pandas as pd
from sqlalchemy import Engine
from src.logger_instance import logger
from src.nlp.prophet_forecast import ProphetForecast
from src.nlp.sql_utils import SQLUtils


class ForecastService(SQLUtils):
    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.prophet = ProphetForecast()

    def handle_forecast_intent(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        if intent not in ["predict_stockout", "predict_top_sales", "predict_sku_sales"]:
            raise ValueError(f"Intent '{intent}' não suportada")

        fatur_table = self._find_table(["faturamento", "venda", "sales", "fatur"])
        if not fatur_table:
            raise ValueError("Tabela de faturamento/vendas não encontrada")

        cols = [c["name"] for c in self.inspector.get_columns(fatur_table)]
        sku_col = "SKU" if "SKU" in cols else self._find_column(fatur_table, ["sku", "produto", "codigo", "cod", "cod_produto"])
        qty_col = "giro_sku_cliente" if "giro_sku_cliente" in cols else self._find_column(fatur_table, ["quant", "qtd", "qty", "amount", "valor", "giro"])
        date_col = "data" if "data" in cols else self._find_column(fatur_table, ["data", "date", "mes", "periodo"])
        if not sku_col or not qty_col or not date_col:
            raise ValueError("Colunas necessárias (SKU, quantidade, data) não encontradas na tabela de faturamento")

        sql = f"""
        WITH daily_sales AS (
            SELECT {self._q(date_col)}::date as ds,
                   {self._q(sku_col)} as sku,
                   coalesce(sum({self._q(qty_col)})::float,0.0) as y
            FROM {self._q(fatur_table)}
            WHERE {self._q(date_col)} >= current_date - interval '2 years'
            GROUP BY ds, sku
        ), sku_points AS (
            SELECT sku, count(*) as points
            FROM daily_sales
            GROUP BY sku
            HAVING count(*) >= 2
        )
        SELECT ds.ds, ds.sku, ds.y
        FROM daily_sales ds
        INNER JOIN sku_points sp ON ds.sku = sp.sku
        ORDER BY ds.sku, ds.ds
        """
        df = pd.DataFrame(self.execute_query(sql))
        if df.empty:
            return {"error": "Não há dados históricos suficientes para fazer previsões"}

        df = df.rename(columns={sku_col: "sku", qty_col: "y", date_col: "ds"})

        if intent == "predict_stockout":
            return self._predict_stockout(df)

        elif intent == "predict_top_sales":
            period = params.get("period", "next_month")
            periods = 30 if period == "next_month" else 365
            return self._predict_top_sales(df, periods)

        elif intent == "predict_sku_sales":
            sku = params.get("sku")
            if not isinstance(sku, str):
                return {"error": "SKU inválido"}
            period = params.get("period", "next_month")
            periods = 30 if period == "next_month" else 365
            return self._predict_sku_sales(df, sku, periods)
        return {}

    def _predict_stockout(self, df: pd.DataFrame) -> dict[str, Any]:
        results = []
        for sku, sku_df in df.groupby("sku"):
            try:
                sku_df = self._clean_outliers(sku_df)
                if len(sku_df) < 2: 
                    continue
                forecast = self.prophet.run_prophet(sku, sku_df, 30)
                assert isinstance(forecast, pd.DataFrame)
                last_values = forecast.tail(7)["yhat"]
                if last_values.min() <= 0 or last_values.mean() < sku_df["y"].mean() * 0.2:
                    zero_date = forecast.loc[forecast["yhat"].idxmin(), "ds"]
                    results.append({
                        "sku": sku,
                        "predicted_stockout": zero_date,
                        "current_avg": float(sku_df["y"].mean()),
                        "predicted_avg": float(last_values.mean())
                    })
            except Exception as e:
                logger.error(f"Erro na previsão do SKU {sku}: {str(e)}")
        results.sort(key=lambda x: x["predicted_stockout"])
        return {"predictions": results}

    def _predict_top_sales(self, df: pd.DataFrame, periods: int) -> dict[str, Any]:
        results = []
        for sku, sku_df in df.groupby("sku"):
            try:
                sku_df = self._clean_outliers(sku_df)
                if len(sku_df) < 2:
                    continue
                forecast = self.prophet.run_prophet(sku, sku_df, periods)
                assert isinstance(forecast, pd.DataFrame)
                last_values = forecast.tail(periods)["yhat"]
                avg_forecast = last_values.mean()
                current_avg = sku_df["y"].mean()
                if current_avg == 0:
                    growth_rate = 0.0
                else:
                    growth_rate = (avg_forecast / current_avg - 1) * 100

                results.append({
                    "sku": sku,
                    "predicted_sales": float(avg_forecast),
                    "current_avg": float(current_avg),
                    "growth_rate": float(growth_rate)
                })
            except Exception as e:
                logger.error(f"Erro na previsão do SKU {sku}: {str(e)}")
        results.sort(key=lambda x: x["predicted_sales"], reverse=True)
        return {"predictions": results[:5]}

    def _predict_sku_sales(self, df: pd.DataFrame, sku: str, periods: int) -> dict[str, Any]:
        sku_df = df[df["sku"].str.upper() == sku]
        if sku_df.empty:
            return {"error": f"Não há dados históricos para o SKU {sku}"}
        try:
            sku_df = self._clean_outliers(sku_df)
            if len(sku_df) < 2:
                return {"error": f"Dados insuficientes para o SKU {sku}"}
            forecast = self.prophet.run_prophet(sku, sku_df, periods)
            assert isinstance(forecast, pd.DataFrame)
            last_predictions = forecast.tail(periods)
            current_avg = float(sku_df["y"].mean())
            predicted_avg = float(last_predictions["yhat"].mean())
            if current_avg == 0:
                growth_rate = 0.0
            else:
                growth_rate = (predicted_avg / current_avg - 1) * 100
            return {
                "sku": sku,
                "predicted_sales": predicted_avg,
                "current_avg": current_avg,
                "growth_rate": float(growth_rate),
                "confidence_interval": {
                    "lower": float(last_predictions["yhat_lower"].mean()),
                    "upper": float(last_predictions["yhat_upper"].mean())
                }
            }
        except Exception as e:
            return {"error": f"Erro ao gerar previsões para o SKU {sku}: {str(e)}"}

    def _clean_outliers(self, sku_df: pd.DataFrame) -> pd.DataFrame:
        sku_df["y"] = sku_df["y"].clip(lower=0)
        Q1 = sku_df["y"].quantile(0.25)
        Q3 = sku_df["y"].quantile(0.75)
        IQR = Q3 - Q1
        return sku_df[(sku_df["y"] >= Q1 - 1.5 * IQR) & (sku_df["y"] <= Q3 + 1.5 * IQR)]
