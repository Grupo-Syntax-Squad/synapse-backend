import pandas as pd
from datetime import datetime
from typing import Any, Callable
from prophet import Prophet  # type: ignore[import-untyped]
from sqlalchemy import Engine, inspect, text

from src.logger_instance import logger
from src.nlp.forecast_service import ForecastService



class SQLQueryBuilder:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.inspector = inspect(engine)

    def _q(self, identifier: str) -> str:
        return f'"{identifier}"'

    def _find_table(self, candidates: list[str]) -> str | None:
        tables = self.inspector.get_table_names()
        for cand in candidates:
            for t in tables:
                if cand in t.lower():
                    return t
        return None

    def _find_column(self, table: str, candidates: list[str]) -> str | None:
        reflected_columns = self.inspector.get_columns(table)
        best: tuple[int, str | None] = (0, None)
        for cand in candidates:
            lcand = cand.lower()
            for col in reflected_columns:
                name = col["name"]
                lname = name.lower()
                score = 0
                if lname == lcand:
                    score += 100
                if lname.endswith("_" + lcand):
                    score += 50
                if lname.startswith(lcand + "_"):
                    score += 30
                if lcand in lname:
                    score += 10

                t = col.get("type")
                type_name = type(t).__name__.lower() if t is not None else ""
                if lcand in {
                    "sku",
                    "produto",
                    "produto_id",
                    "cod_produto",
                    "codigo",
                    "cod",
                }:
                    if (
                        "char" in type_name
                        or "string" in type_name
                        or "varchar" in type_name
                    ):
                        score += 20
                if lcand in {
                    "quant",
                    "qtd",
                    "qty",
                    "amount",
                    "valor",
                    "es_totalestoque",
                    "giro_sku_cliente",
                    "zs_peso_liquido",
                }:
                    if (
                        "numeric" in type_name
                        or "integer" in type_name
                        or "float" in type_name
                        or "decimal" in type_name
                    ):
                        score += 20

                if score > best[0]:
                    best = (score, name)

        return best[1]

    def _get_prophet_model(self, seasonality_mode: str = "multiplicative") -> Any:
        return Prophet(
            seasonality_mode=seasonality_mode,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
            holidays_prior_scale=10.0,
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            interval_width=0.95,
        )

    def _get_business_days(self, date_inicial: datetime, date_final: datetime) -> int:
        date_range = pd.date_range(date_inicial, date_final, freq="D")

        df = pd.DataFrame(date_range, columns=["data"])
        df = df[df["data"].dt.dayofweek < 5]

        return len(df)

    def execute(self, intent: str, params: dict[str, Any]) -> Any:
        if intent == "greeting":
            return {"message": "greeting"}

        if intent == "farewell":
            return {"message": "farewell"}

        if intent == "unknown_intent":
            return {
                "error": "Não entendi sua pergunta",
                "original_text": params.get("original_text", ""),
            }
        
        if intent == "total_stock":
            table = self._find_table(["estoque", "stock", "inventory"])
            if not table:
                raise ValueError("Tabela de estoque não encontrada")
            if table == "estoque":
                qty_col = (
                    "es_totalestoque"
                    if "es_totalestoque"
                    in [c["name"] for c in self.inspector.get_columns(table)]
                    else None
                )
            else:
                qty_col = None
            if not qty_col:
                qty_col = self._find_column(
                    table, ["quant", "qtd", "qty", "amount", "saldo"]
                )
            if not qty_col:
                raise ValueError(
                    f"Coluna de quantidade não encontrada na tabela {table}"
                )
            sql = text(
                f"select coalesce(sum({self._q(qty_col)}),0) as total from {self._q(table)}"
            )
            with self.engine.connect() as conn:
                r = conn.execute(sql)
                return {"total_stock": int(r.scalar() or 0)}

        if intent == "distinct_products_count":
            table = self._find_table(["estoque", "stock", "inventory"])
            if not table:
                raise ValueError("Tabela de estoque não encontrada")
            if table == "estoque":
                sku_col: str | None = (
                    "sku"
                    if "sku" in [c["name"] for c in self.inspector.get_columns(table)]
                    else None
                )
            else:
                sku_col = None
            if not sku_col:
                sku_col = self._find_column(
                    table,
                    ["sku", "produto", "produto_id", "codigo", "cod_cliente", "cod"],
                )
            if not sku_col:
                raise ValueError(f"Coluna SKU não encontrada na tabela {table}")
            sql = text(
                f"select count(distinct {self._q(sku_col)}) as count from {self._q(table)}"
            )
            with self.engine.connect() as conn:
                r = conn.execute(sql)
                return {"distinct_products": int(r.scalar() or 0)}

        if intent == "active_clients_count":
            table = self._find_table(["clientes", "clients", "customers"])
            if not table:
                raise ValueError("Tabela de clientes não encontrada")

            reflected_columns = self.inspector.get_columns(table)
            col_names = [c["name"] for c in reflected_columns]
            status_col = self._find_column(
                table, ["ativo", "is_active", "active", "status"]
            )

            if not status_col:
                for cand in ["is_active", "ativo", "active"]:
                    if cand in col_names:
                        status_col = cand
                        break

            if not status_col:
                sql_all = text(f"select count(*) as count from {self._q(table)}")
                with self.engine.connect() as conn:
                    rall = conn.execute(sql_all)
                    return {
                        "active_clients": int(rall.scalar() or 0),
                        "note": "Nenhuma coluna de status encontrada; retornando contagem total de clientes.",
                    }

            col_meta = next(
                (c for c in reflected_columns if c["name"] == status_col), None
            )
            type_name = type(col_meta.get("type")).__name__.lower() if col_meta else ""
            if "bool" in type_name:
                active_value: str | bool = True
            else:
                active_value = "ativo"

            sql = text(
                f"select count(*) as count from {self._q(table)} where {self._q(status_col)} = :status"
            )
            with self.engine.connect() as conn:
                r = conn.execute(sql, {"status": active_value})
                return {"active_clients": int(r.scalar() or 0)}

        if intent == "sku_sales_compare":
            fatur_table = self._find_table(["faturamento", "venda", "sales", "fatur"])
            if not fatur_table:
                raise ValueError("Tabela de faturamento/vendas não encontrada")
            cols = [c["name"] for c in self.inspector.get_columns(fatur_table)]
            sku_col = (
                "SKU"
                if "SKU" in cols
                else self._find_column(
                    fatur_table, ["sku", "produto", "codigo", "cod", "cod_produto"]
                )
            )
            qty_col = (
                "giro_sku_cliente"
                if "giro_sku_cliente" in cols
                else self._find_column(
                    fatur_table, ["quant", "qtd", "qty", "amount", "valor", "giro"]
                )
            )
            date_col = (
                "data"
                if "data" in cols
                else self._find_column(fatur_table, ["data", "date", "mes", "periodo"])
            )
            if not sku_col or not qty_col:
                raise ValueError(
                    "Colunas SKU ou quantidade não encontradas em faturamento"
                )

            sku = params.get("sku")
            if params.get("periods"):
                p1, p2 = params["periods"]
                sql_tmpl = (
                    f"select coalesce(sum({self._q(qty_col)}),0) as total from {self._q(fatur_table)} "
                    f"where {self._q(sku_col)} = :sku and extract(month from {self._q(date_col)}) = :m and extract(year from {self._q(date_col)}) = :y"  # type: ignore[arg-type]
                )
                with self.engine.connect() as conn:
                    r1 = conn.execute(
                        text(sql_tmpl), {"sku": sku, "m": p1["month"], "y": p1["year"]}
                    ).scalar()
                    r2 = conn.execute(
                        text(sql_tmpl), {"sku": sku, "m": p2["month"], "y": p2["year"]}
                    ).scalar()
                return {"sku": sku, "period1": int(r1 or 0), "period2": int(r2 or 0)}

            if params.get("years"):
                y1, y2 = params["years"]
                sql_tmpl = (
                    f"select coalesce(sum({self._q(qty_col)}),0) as total from {self._q(fatur_table)} "
                    f"where {self._q(sku_col)} = :sku and extract(year from {self._q(date_col if date_col else 'null')}) = :y"
                )
                with self.engine.connect() as conn:
                    r1 = conn.execute(
                        text(sql_tmpl), {"sku": sku, "y": int(y1)}
                    ).scalar()
                    r2 = conn.execute(
                        text(sql_tmpl), {"sku": sku, "y": int(y2)}
                    ).scalar()
                return {"sku": sku, "year1": int(r1 or 0), "year2": int(r2 or 0)}

            raise ValueError("Períodos para comparação não fornecidos")

        if intent == "sku_best_month":
            fatur_table = self._find_table(["faturamento", "venda", "sales", "fatur"])
            if not fatur_table:
                raise ValueError("Tabela de faturamento/vendas não encontrada")
            cols = [c["name"] for c in self.inspector.get_columns(fatur_table)]
            sku_col = (
                "sku"
                if "sku" in cols
                else self._find_column(
                    fatur_table, ["sku", "produto", "codigo", "cod", "cod_produto"]
                )
            )
            qty_col = (
                "giro_sku_cliente"
                if "giro_sku_cliente" in cols
                else self._find_column(
                    fatur_table, ["quant", "qtd", "qty", "amount", "valor", "giro"]
                )
            )
            date_col = (
                "data"
                if "data" in cols
                else self._find_column(fatur_table, ["data", "date", "mes", "periodo"])
            )
            sku = params.get("sku")
            sql = text(
                f"select extract(month from {self._q(date_col if date_col else 'null')}) as month, extract(year from {self._q(date_col if date_col else 'null')}) as year, coalesce(sum({self._q(qty_col if qty_col else 'null')}),0) as total "
                f"from {self._q(fatur_table)} where {self._q(sku_col if sku_col else 'null')} = :sku group by year, month order by total desc limit 1"
            )
            with self.engine.connect() as conn:
                r = conn.execute(sql, {"sku": sku}).first()  # type: ignore[assignment]
                if not r:
                    return {"sku": sku, "best_month": None}
                month, year, total = int(r.month), int(r.year), int(r.total)  # type: ignore[attr-defined]
                return {
                    "sku": sku,
                    "best_month": {"month": month, "year": year, "total": total},
                }

        if intent == "sales_time_series":
            fatur_table = self._find_table(["faturamento", "venda", "sales", "fatur"])
            if not fatur_table:
                raise ValueError("Tabela de faturamento/vendas não encontrada")
            sku_col = self._find_column(
                fatur_table, ["sku", "produto", "codigo", "cod"]
            )
            qty_col = self._find_column(
                fatur_table, ["quant", "qtd", "qty", "amount", "valor"]
            )
            date_col = self._find_column(
                fatur_table, ["data", "date", "mes", "periodo"]
            )
            bind = {}
            where = []
            if params.get("sku"):
                where.append(f"{sku_col} = :sku")
                bind["sku"] = params["sku"]
            sql = text(
                f"select extract(year from {self._q(date_col if date_col else 'null')}) as year, extract(month from {self._q(date_col if date_col else 'null')}) as month, coalesce(sum({self._q(qty_col if qty_col else 'null')}),0) as total "
                f"from {self._q(fatur_table)} "
                + ("where " + " and ".join(where) if where else "")
                + " group by year, month order by year, month"
            )
            with self.engine.connect() as conn:
                res = conn.execute(sql, bind).fetchall()
                return [
                    dict(year=int(r.year), month=int(r.month), total=int(r.total))
                    for r in res
                ]

        if intent == "sales_between_dates":
            fatur_table = self._find_table(["faturamento", "venda", "sales", "fatur"])
            if not fatur_table:
                raise ValueError("Tabela de faturamento/vendas não encontrada")
            cols = [c["name"] for c in self.inspector.get_columns(fatur_table)]
            sku_col = (
                "SKU"
                if "SKU" in cols
                else self._find_column(
                    fatur_table, ["sku", "produto", "codigo", "cod", "cod_produto"]
                )
            )
            qty_col = (
                "giro_sku_cliente"
                if "giro_sku_cliente" in cols
                else self._find_column(
                    fatur_table, ["quant", "qtd", "qty", "amount", "valor", "giro"]
                )
            )
            date_col = (
                "data"
                if "data" in cols
                else self._find_column(fatur_table, ["data", "date", "mes", "periodo"])
            )
            if not qty_col or not date_col:
                raise ValueError(
                    "Colunas de data ou quantidade não encontradas em faturamento"
                )

            bind = {}
            where = []
            if params.get("sku"):
                where.append(f"{self._q(sku_col if sku_col else 'null')} = :sku")
                bind["sku"] = params["sku"]

            start = params.get("start")
            end = params.get("end")
            if start and end:
                if (
                    start.get("month")
                    and start.get("year")
                    and end.get("month")
                    and end.get("year")
                ):
                    where.append(
                        f"( ({self._q(date_col)}) >= to_date(:start_ym,'YYYY-MM') and ({self._q(date_col)}) <= to_date(:end_ym,'YYYY-MM') )"
                    )
                    bind["start_ym"] = f"{start['year']}-{start['month']:02d}"
                    bind["end_ym"] = f"{end['year']}-{end['month']:02d}"
                elif start.get("year") and end.get("year"):
                    where.append(
                        f"extract(year from {self._q(date_col)}) between :y1 and :y2"
                    )
                    bind["y1"] = int(start["year"])
                    bind["y2"] = int(end["year"])

            sql = text(
                f"select coalesce(sum({self._q(qty_col)}),0) as total from {self._q(fatur_table)} "
                + ("where " + " and ".join(where) if where else "")
            )
            with self.engine.connect() as conn:
                r = conn.execute(sql, bind).scalar()  # type: ignore[assignment]
                return {"total": int(r or 0), "filters": bind}  # type: ignore[arg-type]

        if intent == "top_n_skus":
            fatur_table = self._find_table(["faturamento", "venda", "sales", "fatur"])
            if not fatur_table:
                raise ValueError("Tabela de faturamento/vendas não encontrada")
            cols = [c["name"] for c in self.inspector.get_columns(fatur_table)]
            sku_col = (
                "SKU"
                if "SKU" in cols
                else self._find_column(
                    fatur_table, ["sku", "produto", "codigo", "cod", "cod_produto"]
                )
            )
            qty_col = (
                "giro_sku_cliente"
                if "giro_sku_cliente" in cols
                else self._find_column(
                    fatur_table, ["quant", "qtd", "qty", "amount", "valor", "giro"]
                )
            )
            if not sku_col or not qty_col:
                raise ValueError(
                    "Colunas SKU ou quantidade não encontradas em faturamento"
                )
            n = int(params.get("n", 10))
            sql = text(
                f"select {self._q(sku_col)} as sku, coalesce(sum({self._q(qty_col)}),0) as total from {self._q(fatur_table)} group by {self._q(sku_col)} order by total desc limit :n"
            )
            with self.engine.connect() as conn:
                rows = conn.execute(sql, {"n": n}).fetchall()
                return [{"sku": r.sku, "total": int(r.total)} for r in rows]

        if intent == "stock_by_client":
            table = self._find_table(["estoque", "stock", "inventory"])
            if not table:
                raise ValueError("Tabela de estoque não encontrada")
            cols = [c["name"] for c in self.inspector.get_columns(table)]
            qty_col = (
                "es_totalestoque"
                if "es_totalestoque" in cols
                else self._find_column(
                    table, ["quant", "qtd", "qty", "amount", "saldo"]
                )
            )
            client_col = self._find_column(
                table, ["cod_cliente", "cliente", "codclient", "client"]
            )
            if not qty_col:
                raise ValueError(
                    "Coluna de quantidade não encontrada na tabela de estoque"
                )
            bind = {}
            where = []
            if params.get("client"):
                where.append(
                    f"{self._q(client_col if client_col else 'null')} = :client"
                )
                bind["client"] = int(params["client"])
            sql = text(
                f"select coalesce(sum({self._q(qty_col)}),0) as total from {self._q(table)} "
                + ("where " + " and ".join(where) if where else "")
            )
            with self.engine.connect() as conn:
                r = conn.execute(sql, bind).scalar()  # type: ignore[assignment]
                return {"total_stock_client": int(r or 0), "filters": bind}  # type: ignore[arg-type]

        if intent in ["predict_stockout","predict_top_sales","predict_sku_sales"]:
            forecast_service = ForecastService(self.engine)
            result = forecast_service.handle_forecast_intent(intent, params)
            return result

        raise ValueError(f"Intent '{intent}' não suportada")


