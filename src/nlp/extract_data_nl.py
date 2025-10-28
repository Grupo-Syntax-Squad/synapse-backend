import random
import spacy
import re
import pandas as pd
from datetime import datetime
from typing import Any, Callable
from prophet import Prophet  # type: ignore[import-untyped]
from sqlalchemy import Engine, inspect, text

from src.logger_instance import logger


MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


class RuleIntentClassifier:
    SKU_RE = re.compile(r"\b([sS][kK][uU][_\-]?\d+)\b")
    YEAR_RE = re.compile(r"\b(20\d{2})\b")
    NUMBER_RE = re.compile(
        r"\btop\s*(\d+)\b|\b(\d+)\s*(top|maiores|principais)\b", re.I
    )
    MONTH_WITH_YEAR_RE = re.compile(
        r"(janeiro|fevereiro|mar[cç]o|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s*(?:de\s*)?(20\d{2})",
        re.I,
    )

    VOCABULARY = {
        "greeting": [
            "oi",
            "olá",
            "ola",
            "eae",
            "tudo bem",
            "bom dia",
            "boa tarde",
            "boa noite",
            "hey",
            "iai",
            "fala",
            "salve",
            "como vai",
        ],
        "farewell": [
            "tchau",
            "obrigado",
            "obrigada",
            "valeu",
            "até logo",
            "até mais",
            "flw",
            "falou",
            "bye",
            "adeus",
            "encerrar",
            "finalizar",
            "fim",
        ],
        "predict_stockout": [
            "estoque zero",
            "sem estoque",
            "acabar",
            "ficar sem",
            "esgotar",
        ],
        "predict_top_sales": [
            "top",
            "maiores",
            "principais",
            "mais vendidos",
            "mais vendeu",
        ],
        "predict_sku_sales": ["vendas", "vender"],
        "total_stock": ["total", "estoque"],
        "active_clients_count": [
            "quantos",
            "quantidade",
            "número de",
            "numero de",
            "clientes",
            "ativos",
            "ativo",
        ],
        "distinct_products_count": [
            "quantos",
            "quantidade",
            "numero",
            "número",
            "produtos",
            "skus",
            "estoque",
        ],
        "sku_sales_compare": ["maior", "comparar", "teve maior"],
        "sku_best_month": ["que mes", "mais vendeu", "melhor mes", "mês"],
        "sales_between_dates": ["entre", " a ", "até", "ate"],
        "top_n_skus": ["top", "maiores", "principais"],
        "stock_by_client": ["estoque", "cliente"],
        "sales_time_series": ["venda", "vendas", "faturamento"],
    }

    def __init__(self) -> None:
        self._nlp = spacy.load("pt_core_news_sm")

    def execute(self, text: str) -> tuple[str, dict[str, Any]]:
        text_lower = text.lower()
        doc = self._nlp(text)
        logger.debug(f"Text lower: {text_lower}")

        scores = {intent: 0 for intent in self.VOCABULARY}
        for intent, words in self.VOCABULARY.items():
            for w in words:
                if w in text_lower:
                    scores[intent] += 1

        best_intent = max(scores, key=scores.get)  # type: ignore[arg-type]
        logger.debug(f"BoW scores: {scores}, best intent: {best_intent}")

        sku_match = self.SKU_RE.search(text)
        sku = sku_match.group(1) if sku_match else None

        years = [int(y) for y in self.YEAR_RE.findall(text)]
        month_year = self.MONTH_WITH_YEAR_RE.findall(text)
        months = [
            {"month": MONTHS_PT.get(m.lower().replace("ç", "c")), "year": int(y)}
            for m, y in month_year
        ]

        mnum = self.NUMBER_RE.search(text)
        n = int(mnum.group(1) or mnum.group(2)) if mnum else 10

        client_match = re.search(r"\b(\d{2,6})\b", text)
        client = int(client_match.group(1)) if client_match else None

        params = {}
        if best_intent in {
            "predict_stockout",
            "predict_sku_sales",
            "sku_sales_compare",
            "sku_best_month",
            "sales_between_dates",
            "top_n_skus",
            "stock_by_client",
            "sales_time_series",
        }:
            if sku:
                params["sku"] = sku
            if months:
                params["months"] = months
            if years:
                params["years"] = years
            if best_intent == "top_n_skus":
                params["n"] = n
            if best_intent == "stock_by_client" and client:
                params["client"] = client
            if best_intent == "sales_between_dates":
                if len(months) >= 2:
                    params.update({"start": months[0], "end": months[1]})
                elif len(years) >= 2:
                    params.update(
                        {"start": {"year": years[0]}, "end": {"year": years[1]}}
                    )

        for ent in doc.ents:
            if ent.label_.lower() in {"product", "produto", "sku"}:
                best_intent = "sales_time_series"
                params["sku"] = ent.text

        return best_intent, params


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
                    "SKU"
                    if "SKU" in [c["name"] for c in self.inspector.get_columns(table)]
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

        if intent in ["predict_stockout", "predict_top_sales", "predict_sku_sales"]:
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

            sql = text(
                f"""
                WITH daily_sales AS (
                    SELECT {self._q(date_col if date_col else "null")}::date as ds,
                           {self._q(sku_col if sku_col else "null")} as sku,
                           coalesce(sum({self._q(qty_col if qty_col else "null")})::float,0.0) as y
                    FROM {self._q(fatur_table)}
                    WHERE {self._q(date_col if date_col else "null")} >= current_date - interval '2 years'
                    GROUP BY ds, sku
                ),
                sku_points AS (
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
            )

            with self.engine.connect() as conn:
                df = pd.DataFrame(conn.execute(sql).fetchall())

                if df.empty:
                    return {
                        "error": "Não há dados históricos suficientes para fazer previsões"
                    }

                if intent == "predict_stockout":
                    results = []
                    for sku_group in df.groupby("sku"):
                        sku, sku_df = sku_group

                        try:
                            sku_df["y"] = sku_df["y"].clip(lower=0)
                            Q1 = sku_df["y"].quantile(0.25)
                            Q3 = sku_df["y"].quantile(0.75)
                            IQR = Q3 - Q1
                            sku_df = sku_df[
                                (sku_df["y"] >= Q1 - 1.5 * IQR)
                                & (sku_df["y"] <= Q3 + 1.5 * IQR)
                            ]

                            if len(sku_df) < 2:
                                continue

                            m = self._get_prophet_model("multiplicative")
                            m.fit(sku_df[["ds", "y"]])
                            future = m.make_future_dataframe(periods=30)
                            forecast = m.predict(future)

                            last_values = forecast.tail(7)["yhat"]
                            if last_values.min() <= 0 or (
                                last_values.mean() < sku_df["y"].mean() * 0.2
                            ):
                                zero_date = forecast.loc[
                                    forecast["yhat"].idxmin(), "ds"
                                ]
                                results.append(
                                    {
                                        "sku": sku,
                                        "predicted_stockout": zero_date,
                                        "current_avg": float(sku_df["y"].mean()),
                                        "predicted_avg": float(last_values.mean()),
                                    }
                                )

                        except Exception as e:
                            logger.error(
                                f"Erro na previsão do SKU {str(sku)}: {str(e)}"
                            )
                            continue

                    results.sort(key=lambda x: x["predicted_stockout"])
                    return {"predictions": results}

                elif intent == "predict_top_sales":
                    period = params.get("period", "next_month")
                    periods = 30 if period == "next_month" else 365

                    results = []
                    for sku_group in df.groupby("sku"):
                        sku, sku_df = sku_group

                        try:
                            sku_df["y"] = sku_df["y"].clip(lower=0)
                            Q1 = sku_df["y"].quantile(0.25)
                            Q3 = sku_df["y"].quantile(0.75)
                            IQR = Q3 - Q1
                            sku_df = sku_df[
                                (sku_df["y"] >= Q1 - 1.5 * IQR)
                                & (sku_df["y"] <= Q3 + 1.5 * IQR)
                            ]

                            if len(sku_df) < 2:
                                continue

                            m = self._get_prophet_model("multiplicative")
                            m.fit(sku_df[["ds", "y"]])
                            future = m.make_future_dataframe(periods=periods)
                            forecast = m.predict(future)

                            last_predictions = forecast.tail(periods)["yhat"]
                            avg_forecast = last_predictions.mean()

                            results.append(
                                {
                                    "sku": sku,
                                    "predicted_sales": float(avg_forecast),
                                    "current_avg": float(sku_df["y"].mean()),
                                    "growth_rate": float(
                                        (avg_forecast / sku_df["y"].mean() - 1) * 100
                                    ),
                                }
                            )

                        except Exception as e:
                            logger.error(
                                f"Erro na previsão do SKU {str(sku)}: {str(e)}"
                            )
                            continue

                    results.sort(key=lambda x: x["predicted_sales"], reverse=True)
                    return {"predictions": results[:5]}

                elif intent == "predict_sku_sales":
                    try:
                        sku = params.get("sku")
                        period = params.get("period", "next_month")
                        periods = 30 if period == "next_month" else 365

                        sku_df = df[df["sku"] == sku]
                        if sku_df.empty:
                            return {
                                "error": f"Não há dados históricos para o SKU {sku}"
                            }

                        sku_df["y"] = sku_df["y"].clip(lower=0)
                        Q1 = sku_df["y"].quantile(0.25)
                        Q3 = sku_df["y"].quantile(0.75)
                        IQR = Q3 - Q1
                        sku_df = sku_df[
                            (sku_df["y"] >= Q1 - 1.5 * IQR)
                            & (sku_df["y"] <= Q3 + 1.5 * IQR)
                        ]

                        if len(sku_df) < 2:
                            return {
                                "error": f"Dados insuficientes para fazer previsões confiáveis para o SKU {sku}"
                            }

                        m = self._get_prophet_model("multiplicative")
                        m.fit(sku_df[["ds", "y"]])
                        future = m.make_future_dataframe(periods=periods)
                        forecast = m.predict(future)

                        last_predictions = forecast.tail(periods)
                        current_avg = float(sku_df["y"].mean())
                        predicted_avg = float(last_predictions["yhat"].mean())
                        growth_rate = (predicted_avg / current_avg - 1) * 100

                        return {
                            "sku": sku,
                            "predicted_sales": predicted_avg,
                            "current_avg": current_avg,
                            "growth_rate": float(growth_rate),
                            "confidence_interval": {
                                "lower": float(last_predictions["yhat_lower"].mean()),
                                "upper": float(last_predictions["yhat_upper"].mean()),
                            },
                        }

                    except Exception as e:
                        return {
                            "error": f"Erro ao gerar previsões para o SKU {sku}: {str(e)}"
                        }

        raise ValueError(f"Intent '{intent}' não suportada")


class ResponseGenerator:
    def __init__(self) -> None:
        self._response_handlers: dict[str, Callable[[dict[str, Any], Any], str]] = {
            "total_stock": self._format_total_stock,
            "distinct_products_count": self._format_distinct_products_count,
            "active_clients_count": self._format_active_clients_count,
            "sku_sales_compare": self._format_sku_sales_compare,
            "sku_best_month": self._format_sku_best_month,
            "sales_time_series": self._format_sales_time_series,
            "sales_between_dates": self._format_sales_between_dates,
            "top_n_skus": self._format_top_n_skus,
            "stock_by_client": self._format_stock_by_client,
            "predict_stockout": self._format_predict_stockout,
            "predict_top_sales": self._format_predict_top_sales,
            "predict_sku_sales": self._format_predict_sku_sales,
            "greeting": self._format_greeting,
            "farewell": self._format_farewell,
            "unknown_intent": self._format_unknown_intent,
        }

    def _format_greeting(self, params: dict[str, Any], result: Any) -> str:
        greetings = [
            "Olá! Como posso ajudar você com informações sobre vendas e estoque?",
            "Oi! Estou aqui para ajudar com dados de vendas, estoque e previsões.",
            "Olá! Pronto para analisar alguns dados de negócio?",
            "Oi! Em que posso ser útil hoje?",
        ]
        return random.choice(greetings)

    def _format_farewell(self, params: dict[str, Any], result: Any) -> str:
        farewells = [
            "Até logo! Fico à disposição para mais análises.",
            "Obrigado! Volte sempre que precisar de informações.",
            "Tchau! Foi um prazer ajudar.",
            "Até mais! Estarei aqui quando precisar.",
        ]
        return random.choice(farewells)

    def _format_unknown_intent(self, params: dict[str, Any], result: Any) -> str:
        original_text = params.get("original_text", "")
        responses = [
            f"Desculpe, não entendi '{original_text}'. Posso ajudar com informações sobre vendas, estoque, previsões e análises de SKU.",
            f"Não consegui compreender '{original_text}'. Tente perguntar sobre vendas, estoque, produtos mais vendidos ou previsões.",
            f"Minha especialidade é análise de dados comerciais. Não entendi '{original_text}'. Que tal perguntar sobre vendas ou estoque?",
        ]
        return random.choice(responses)

    def _format_total_stock(self, params: dict[str, Any], result: Any) -> str:
        if isinstance(result, dict) and "total_stock" in result:
            total = result["total_stock"]
            return f"O total de itens em estoque é {total}."

        return "Nenhum dado disponível sobre estoque."

    def _format_distinct_products_count(
        self, params: dict[str, Any], result: Any
    ) -> str:
        c = result.get("distinct_products") if isinstance(result, dict) else None
        return (
            f"Encontramos {c} produtos diferentes no estoque."
            if c is not None
            else "Não foi possível contar os produtos."
        )

    def _format_active_clients_count(self, params: dict[str, Any], result: Any) -> str:
        ac = result.get("active_clients") if isinstance(result, dict) else None
        note = result.get("note") if isinstance(result, dict) else None
        base = (
            f"Existem {ac} clientes ativos."
            if ac is not None
            else "Não foi possível contar clientes ativos."
        )
        if note:
            base += f" (Observação: {note})"
        return base

    def _format_sku_sales_compare(self, params: dict[str, Any], result: Any) -> str:
        sku = params.get("sku", "o SKU solicitado")

        intro = (
            f"Analisando as vendas do {sku}, "
            if random.random() > 0.5
            else f"Comparando o desempenho do {sku}, "
        )

        if "period1" in result and "period2" in result:
            p1_val = result["period1"]
            p2_val = result["period2"]

            if p1_val > p2_val:
                return (
                    f"{intro}o primeiro período teve vendas maiores "
                    f"({p1_val} vs {p2_val})."
                )
            elif p2_val > p1_val:
                return (
                    f"{intro}o segundo período teve vendas maiores "
                    f"({p2_val} vs {p1_val})."
                )
            else:
                return f"{intro}as vendas foram iguais nos dois períodos ({p1_val})."

        if "year1" in result and "year2" in result:
            y1_val = result["year1"]
            y2_val = result["year2"]

            if y1_val > y2_val:
                return (
                    f"{intro}o primeiro ano teve vendas maiores ({y1_val} vs {y2_val})."
                )
            elif y2_val > y1_val:
                return (
                    f"{intro}o segundo ano teve vendas maiores ({y2_val} vs {y1_val})."
                )
            else:
                return f"{intro}as vendas foram iguais nos dois anos ({y1_val})."

        return f"Não foi possível obter dados comparativos para {sku}."

    def _format_sku_best_month(self, params: dict[str, Any], result: Any) -> str:
        sku = result.get("sku", params.get("sku", "o SKU solicitado"))
        bm = result.get("best_month") if isinstance(result, dict) else None
        if bm:
            return f"O melhor mês de vendas para o SKU {sku} foi {bm['month']:02d}/{bm['year']}, com um total de {bm['total']} unidades."
        return f"Não encontrei registros de vendas para o SKU {sku} para determinar o melhor mês."

    def _format_sales_time_series(self, params: dict[str, Any], result: Any) -> str:
        sku_info = f" para o SKU {params['sku']}" if params.get("sku") else ""
        if isinstance(result, list) and result:
            first = result[0]
            last = result[-1]
            return f"Encontrei {len(result)} registros de vendas mensais{sku_info}, indo de {first['month']:02d}/{first['year']} (Total: {first['total']}) até {last['month']:02d}/{last['year']} (Total: {last['total']})."
        return f"Não há dados de série temporal de vendas disponíveis{sku_info}."

    def _format_sales_between_dates(self, params: dict[str, Any], result: Any) -> str:
        total = result.get("total") if isinstance(result, dict) else None
        filters = result.get("filters", {}) if isinstance(result, dict) else {}
        sku_info = f" para o SKU {filters['sku']}" if filters.get("sku") else ""
        period_info = ""

        if "start_ym" in filters and "end_ym" in filters:
            start_y, start_m = filters["start_ym"].split("-")
            end_y, end_m = filters["end_ym"].split("-")
            period_info = (
                f"entre {int(start_m):02d}/{start_y} e {int(end_m):02d}/{end_y}"
            )
        elif "y1" in filters and "y2" in filters:
            period_info = f"entre os anos {filters['y1']} e {filters['y2']}"

        if total is not None:
            return f"O total de vendas{sku_info} no período {period_info} foi de {total} unidades."
        return f"Não encontrei vendas{sku_info} no período {period_info}."

    def _format_top_n_skus(self, params: dict[str, Any], result: Any) -> str:
        if not result:
            return "Desculpe, não consegui encontrar os SKUs mais vendidos."

        intro = "Os SKUs com melhor desempenho são:"

        sku_lines = []
        for i, r in enumerate(result, 1):
            sku_lines.append(f"{i}. {r['sku']}: {r['total']} vendas")

        formatted_skus = "\n".join(sku_lines)
        return f"{intro}\n{formatted_skus}"

    def _format_stock_by_client(self, params: dict[str, Any], result: Any) -> str:
        total = result.get("total_stock_client") if isinstance(result, dict) else None
        filters = result.get("filters", {}) if isinstance(result, dict) else {}
        if total is not None:
            if filters.get("client"):
                return f"O estoque total associado ao cliente {filters['client']} é de {total} unidades."
            return f"O estoque total (considerando todos os clientes/registros) é de {total} unidades."
        client_info = (
            f" para o cliente {params['client']}" if params.get("client") else ""
        )
        return f"Não foi possível calcular o estoque{client_info}."

    def _format_predict_stockout(self, params: dict[str, Any], result: Any) -> str:
        if "error" in result:
            return result["error"]  # type: ignore[no-any-return]

        predictions = result.get("predictions", [])
        if not predictions:
            return "Não foi identificado risco de estoque zero para nenhum SKU no próximo mês."

        response = "SKUs com risco de estoque zero:\n\n"
        for p in predictions:
            stockout_date = p["predicted_stockout"].strftime("%d/%m/%Y")
            current_avg = int(p["current_avg"])
            predicted_avg = int(p["predicted_avg"])
            percent_drop = (
                ((current_avg - predicted_avg) / current_avg * 100)
                if current_avg > 0
                else 0
            )

            response += (
                f"SKU: {p['sku']}\n"
                f"- Data prevista: {stockout_date}\n"
                f"- Média atual: {current_avg} unidades\n"
                f"- Média prevista: {predicted_avg} unidades\n"
                f"- Queda prevista: {percent_drop:.1f}%\n\n"
            )
        return response

    def _format_predict_top_sales(self, params: dict[str, Any], result: Any) -> str:
        if "error" in result:
            return result["error"]  # type: ignore[no-any-return]

        predictions = result.get("predictions", [])
        if not predictions:
            return "Não foi possível fazer previsões de vendas no momento."

        period = (
            "próximo mês" if params.get("period") == "next_month" else "próximo ano"
        )
        response = f"Previsão dos SKUs mais vendidos para o {period}:\n\n"

        for i, p in enumerate(predictions, 1):
            predicted = int(p["predicted_sales"])
            current = int(p["current_avg"])
            growth = p["growth_rate"]

            growth_text = (
                f"crescimento de {growth:.1f}%"
                if growth > 0
                else f"queda de {abs(growth):.1f}%"
                if growth < 0
                else "estável"
            )

            response += (
                f"{i}. SKU: {p['sku']}\n"
                f"   - Previsão: {predicted} unidades\n"
                f"   - Média atual: {current} unidades\n"
                f"   - Tendência: {growth_text}\n\n"
            )
        return response

    def _format_predict_sku_sales(self, params: dict[str, Any], result: Any) -> str:
        if "error" in result:
            return result["error"]  # type: ignore[no-any-return]

        sku = result["sku"]
        predicted = int(result["predicted_sales"])
        current = int(result["current_avg"])
        growth = result["growth_rate"]
        period = (
            "próximo mês" if params.get("period") == "next_month" else "próximo ano"
        )

        growth_text = (
            f"crescimento de {growth:.1f}%"
            if growth > 0
            else f"queda de {abs(growth):.1f}%"
            if growth < 0
            else "estável"
        )

        ci = result.get("confidence_interval", {})
        confidence_text = (
            f"\nIntervalo de confiança: entre {int(ci['lower'])} e {int(ci['upper'])} unidades"
            if ci
            else ""
        )

        return (
            f"Análise de vendas para o SKU {sku}:\n\n"
            f"- Período: {period}\n"
            f"- Média atual: {current} unidades\n"
            f"- Previsão: {predicted} unidades\n"
            f"- Tendência: {growth_text}{confidence_text}"
        )

    def execute(self, intent: str, params: dict[str, Any], result: Any) -> str:
        handler = self._response_handlers.get(intent)
        if not handler:
            logger.warning(
                f"Aviso: Handler de resposta não encontrado para a intenção '{intent}'"
            )
            return f"Não tenho um formato de resposta específico para '{intent}', mas o resultado foi: {result}"

        try:
            return handler(params, result)
        except Exception as e:
            logger.error(f"Erro ao gerar resposta para intent '{intent}': {e}")
            return "Desculpe — não consegui formular uma resposta amigável a partir dos dados retornados."
