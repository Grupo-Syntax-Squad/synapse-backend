import random
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import spacy
from prophet import Prophet  # type: ignore
from sqlalchemy import CursorResult, Engine, Row, create_engine, inspect, text

from src.settings import settings

# no local datetime usage required


class IntentEntityRecognizer:
    """Tiny helper that extracts the first named entity found by spaCy.

    Kept for backwards compatibility with other parts of the code.
    """

    def __init__(self) -> None:
        self._nlp = spacy.load("pt_core_news_sm")

    def recognize(self, text: str) -> Optional[str]:
        doc = self._nlp(text)
        for ent in doc.ents:
            return ent.text
        return None


MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
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
    """Rule-based intent classifier for common SQL query intents.

    It returns a tuple (intent_name, params_dict). Intent names supported:
      - total_stock
      - distinct_products_count
      - sku_sales_compare
      - sku_best_month
      - sales_time_series

    The classifier extracts SKUs, months and years when possible.
    """

    SKU_RE = re.compile(r"\b([sS][kK][uU][_\-]?\d+)\b")
    YEAR_RE = re.compile(r"\b(20\d{2})\b")
    NUMBER_RE = re.compile(
        r"\btop\s*(\d+)\b|\b(\d+)\s*(top|maiores|principais)\b", re.I
    )
    MONTH_WITH_YEAR_RE = re.compile(
        r"(janeiro|fevereiro|mar[cç]o|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s*(?:de\s*)?(20\d{2})",
        re.I,
    )

    def __init__(self) -> None:
        self._nlp = spacy.load("pt_core_news_sm")

    def classify(self, text: str) -> tuple[str, dict[str, Any]]:
        t = text.lower()
        doc = self._nlp(text)

        sku = None
        m = self.SKU_RE.search(text)
        if m:
            sku = m.group(1)

        years = [int(y) for y in self.YEAR_RE.findall(text)]
        month_year = self.MONTH_WITH_YEAR_RE.findall(text)
        months = []
        for mo, yr in month_year:
            months.append(
                {
                    "month": MONTHS_PT.get(mo.lower().replace("ç", "c"), None),
                    "year": int(yr),
                }
            )

        # Novos padrões para previsões
        if ("previsão" in t or "prever" in t or "tendência" in t or "vai ficar" in t or
            "correm risco" in t or "podem acabar" in t or "risco de acabar" in t):
            if ("estoque zero" in t or "sem estoque" in t or "acabar" in t or
                "ficar sem" in t or "esgotar" in t):
                return "predict_stockout", {"sku": sku} if sku else {}

            if "mais" in t and ("vendido" in t or "consumido" in t):
                period = None
                if "próximo mês" in t or "mês que vem" in t:
                    period = "next_month"
                elif "próximo ano" in t or "ano que vem" in t:
                    period = "next_year"
                return "predict_top_sales", {"period": period or "next_month"}

            if sku and ("vendas" in t or "vender" in t):
                period = None
                if "próximo mês" in t or "mês que vem" in t:
                    period = "next_month"
                elif "próximo ano" in t or "ano que vem" in t:
                    period = "next_year"
                return "predict_sku_sales", {
                    "sku": sku,
                    "period": period or "next_month",
                }

        # total stock
        if "total" in t and "estoque" in t:
            return "total_stock", {}

        # count active clients (more specific rule first)
        if (
            (
                "quantos" in t
                or "quantidade" in t
                or "número de" in t
                or "numero de" in t
            )
            and "clientes" in t
            and ("ativos" in t or "ativo" in t)
        ):
            return "active_clients_count", {}

        if (
            ("quantos" in t or "quantidade" in t or "numero" in t or "número" in t)
            and ("produtos" in t or "skus" in t)
            and "estoque" in t
        ):
            return "distinct_products_count", {}

        # sku comparison: look for 'maior' and two dates/years
        if ("maior" in t or "comparar" in t or "teve maior" in t) and sku:
            params = {"sku": sku}
            if len(months) >= 2:
                params["periods"] = months[:2]
            elif len(years) >= 2:
                params["years"] = years[:2]
            return "sku_sales_compare", params

        # best month for SKU
        if (
            "que mes" in t or "mais vendeu" in t or "melhor mes" in t or "mês" in t
        ) and sku:
            return "sku_best_month", {"sku": sku}

        # sales between two dates / periods (months with years or years)
        if ("entre" in t or " a " in t or "até" in t or "ate" in t) and (
            len(months) >= 2 or len(years) >= 2
        ):
            if len(months) >= 2:
                return (
                    "sales_between_dates",
                    {
                        "start": months[0],
                        "end": months[1],
                        **({"sku": sku} if sku else {}),
                    },
                )
            if len(years) >= 2:
                return (
                    "sales_between_dates",
                    {
                        "start": {"year": years[0]},
                        "end": {"year": years[1]},
                        **({"sku": sku} if sku else {}),
                    },
                )

        # top N SKUs
        mnum = self.NUMBER_RE.search(text)
        if (
            "top" in t or "maiores" in t or "principais" in t or "mais vendidos" in t
        ) and (mnum or "mais vendidos" in t):
            n = 10
            if mnum:
                n = int(mnum.group(1) or mnum.group(2))
            return "top_n_skus", {"n": int(n)}

        # stock by client
        if "estoque" in t and "cliente" in t:
            # try to extract client code if present (numeric token)
            mclient = re.search(r"\b(\d{2,6})\b", text)
            client = int(mclient.group(1)) if mclient else None
            return "stock_by_client", {**({"client": client} if client else {})}

        # time series / aggregate sales by period
        if "venda" in t or "vendas" in t or "faturamento" in t:
            params = {}
            if sku:
                params["sku"] = sku
            if months:
                params["months"] = months
            return "sales_time_series", params

        # fallback: try to infer entity via spaCy named entities
        for ent in doc.ents:
            if ent.label_.lower() in {"product", "produto", "sku"}:
                return "sales_time_series", {"sku": ent.text}

        raise ValueError("Não consegui identificar a intenção do usuário")


class SQLQueryBuilder:
    """Builds and executes SQL queries for the classified intents.

    The builder inspects the database to find reasonable table and column names
    and composes parameterized queries using SQLAlchemy text().
    """

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.inspector = inspect(engine)

    def _q(self, identifier: str) -> str:
        # quote identifier to preserve case and special characters
        return f'"{identifier}"'

    def _find_table(self, candidates: list[str]) -> Optional[str]:
        tables = self.inspector.get_table_names()
        for cand in candidates:
            for t in tables:
                if cand in t.lower():
                    return t
        return None

    def _find_column(self, table: str, candidates: list[str]) -> Optional[str]:
        cols = self.inspector.get_columns(table)
        # scoring: prefer exact matches, suffix matches, then contains
        best: tuple[int, Optional[str]] = (0, None)
        for cand in candidates:
            lcand = cand.lower()
            for col in cols:
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

                # prefer string-like columns for SKU-like candidates and numeric for qty-like
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

    def _get_prophet_model(self, seasonality_mode: str = 'multiplicative') -> Prophet:
        """Cria um modelo Prophet com configurações otimizadas.
        
        Args:
            seasonality_mode: The seasonality mode for the Prophet model.
                Can be 'multiplicative' or 'additive'.
        
        Returns:
            A configured Prophet model instance
        """
        return Prophet(
            seasonality_mode=seasonality_mode,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
            holidays_prior_scale=10.0,
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            interval_width=0.95
        )
        
    def _get_business_days(self, date_inicial: datetime, date_final: datetime) -> int:
        """Retorna a quantidade de dias úteis (incluindo feriados nacionais) entre duas datas.
        
        Args:
            date_inicial: The start date
            date_final: The end date
            
        Returns:
            The number of business days between the two dates, excluding weekends
        """
        # Criar dataframe com as datas
        date_range = pd.date_range(date_inicial, date_final, freq='D')

        # Remover fim de semana 
        df = pd.DataFrame(date_range, columns=['data'])
        df = df[df['data'].dt.dayofweek < 5]

        return len(df)

    def execute(self, intent: str, params: dict[str, Any]) -> Any:
        if intent == "total_stock":
            table = self._find_table(["estoque", "stock", "inventory"])
            if not table:
                raise ValueError("Tabela de estoque não encontrada")
            # prefer model column name used in this project
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
            # prefer SKU column name in models
            if table == "estoque":
                sku_col = (
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

            # try to find a boolean-like or status column
            cols = self.inspector.get_columns(table)
            col_names = [c["name"] for c in cols]
            status_col = self._find_column(
                table, ["ativo", "is_active", "active", "status"]
            )

            # if no status column, try common boolean column names or fall back
            if not status_col:
                for cand in ["is_active", "ativo", "active"]:
                    if cand in col_names:
                        status_col = cand
                        break

            # If still not found, return a clarification response instead of guessing
            if not status_col:
                # no status column; fallback to counting all clients
                sql_all = text(f"select count(*) as count from {self._q(table)}")
                with self.engine.connect() as conn:
                    rall = conn.execute(sql_all)
                    return {
                        "active_clients": int(rall.scalar() or 0),
                        "note": "Nenhuma coluna de status encontrada; retornando contagem total de clientes.",
                    }

            # Determine active value type: boolean vs text vs int
            col_meta = next((c for c in cols if c["name"] == status_col), None)
            # Heuristics: if column is boolean-like, query TRUE; if text, look for 'ativo' or 'A'
            type_name = type(col_meta.get("type")).__name__.lower() if col_meta else ""
            if "bool" in type_name:
                active_value = True
            else:
                # try textual value 'ativo' or 'A' as common possibilities
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
            # prefer model-specific names in faturamento
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
            # compare two periods supplied as months or years
            if params.get("periods"):
                p1, p2 = params["periods"]
                sql_tmpl = (
                    f"select coalesce(sum({self._q(qty_col)}),0) as total from {self._q(fatur_table)} "
                    f"where {self._q(sku_col)} = :sku and extract(month from {self._q(date_col)}) = :m and extract(year from {self._q(date_col)}) = :y"
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
                    f"where {self._q(sku_col)} = :sku and extract(year from {self._q(date_col)}) = :y"
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
                f"select extract(month from {self._q(date_col)}) as month, extract(year from {self._q(date_col)}) as year, coalesce(sum({self._q(qty_col)}),0) as total "
                f"from {self._q(fatur_table)} where {self._q(sku_col)} = :sku group by year, month order by total desc limit 1"
            )
            with self.engine.connect() as conn:
                r = conn.execute(sql, {"sku": sku}).first()
                if not r:
                    return {"sku": sku, "best_month": None}
                month, year, total = int(r.month), int(r.year), int(r.total)
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
                f"select extract(year from {self._q(date_col)}) as year, extract(month from {self._q(date_col)}) as month, coalesce(sum({self._q(qty_col)}),0) as total "
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
            # sku filter optional
            if params.get("sku"):
                where.append(f"{self._q(sku_col)} = :sku")
                bind["sku"] = params["sku"]

            # build date range from start/end which may have month+year or only year
            start = params.get("start")
            end = params.get("end")
            if start and end:
                # if month+year provided
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
                r = conn.execute(sql, bind).scalar()
                return {"total": int(r or 0), "filters": bind}

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
                where.append(f"{self._q(client_col)} = :client")
                bind["client"] = int(params["client"])
            sql = text(
                f"select coalesce(sum({self._q(qty_col)}),0) as total from {self._q(table)} "
                + ("where " + " and ".join(where) if where else "")
            )
            with self.engine.connect() as conn:
                r = conn.execute(sql, bind).scalar()
                return {"total_stock_client": int(r or 0), "filters": bind}

        # Previsões com Prophet
        if intent in ["predict_stockout", "predict_top_sales", "predict_sku_sales"]:
            fatur_table = self._find_table(["faturamento", "venda", "sales", "fatur"])
            if not fatur_table:
                raise ValueError("Tabela de faturamento/vendas não encontrada")

            # Get column names
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

            # Get historical data with at least 2 points
            sql = text(
                f"""
                WITH daily_sales AS (
                    SELECT {self._q(date_col)}::date as ds,
                           {self._q(sku_col)} as sku,
                           coalesce(sum({self._q(qty_col)})::float,0.0) as y
                    FROM {self._q(fatur_table)}
                    WHERE {self._q(date_col)} >= current_date - interval '2 years'
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
                    # Prever quais SKUs terão estoque zero
                    results = []
                    for sku_group in df.groupby("sku"):
                        sku, sku_df = sku_group

                        try:
                            # Remover valores negativos e outliers
                            sku_df['y'] = sku_df['y'].clip(lower=0)
                            Q1 = sku_df['y'].quantile(0.25)
                            Q3 = sku_df['y'].quantile(0.75)
                            IQR = Q3 - Q1
                            sku_df = sku_df[
                                (sku_df['y'] >= Q1 - 1.5 * IQR) & 
                                (sku_df['y'] <= Q3 + 1.5 * IQR)
                            ]

                            if len(sku_df) < 2:
                                continue

                            m = self._get_prophet_model('multiplicative')
                            m.fit(sku_df[["ds", "y"]])
                            future = m.make_future_dataframe(periods=30)
                            forecast = m.predict(future)

                            # Verificar tendência de estoque zero
                            last_values = forecast.tail(7)['yhat']
                            if last_values.min() <= 0 or (last_values.mean() < sku_df['y'].mean() * 0.2):
                                zero_date = forecast.loc[forecast['yhat'].idxmin(), 'ds']
                                results.append({
                                    "sku": sku,
                                    "predicted_stockout": zero_date,
                                    "current_avg": float(sku_df['y'].mean()),
                                    "predicted_avg": float(last_values.mean())
                                })

                        except Exception as e:
                            print(f"Erro na previsão do SKU {sku}: {str(e)}")
                            continue

                    # Ordenar por data mais próxima de estoque zero
                    results.sort(key=lambda x: x["predicted_stockout"])
                    return {"predictions": results}

                elif intent == "predict_top_sales":
                    # Prever SKUs mais vendidos no próximo período
                    period = params.get("period", "next_month")
                    periods = 30 if period == "next_month" else 365

                    results = []
                    for sku_group in df.groupby("sku"):
                        sku, sku_df = sku_group

                        try:
                            # Remover valores negativos e outliers
                            sku_df['y'] = sku_df['y'].clip(lower=0)
                            Q1 = sku_df['y'].quantile(0.25)
                            Q3 = sku_df['y'].quantile(0.75)
                            IQR = Q3 - Q1
                            sku_df = sku_df[
                                (sku_df['y'] >= Q1 - 1.5 * IQR) & 
                                (sku_df['y'] <= Q3 + 1.5 * IQR)
                            ]

                            if len(sku_df) < 2:
                                continue

                            m = self._get_prophet_model('multiplicative')
                            m.fit(sku_df[["ds", "y"]])
                            future = m.make_future_dataframe(periods=periods)
                            forecast = m.predict(future)

                            # Calcular média das previsões para o período
                            last_predictions = forecast.tail(periods)['yhat']
                            avg_forecast = last_predictions.mean()
                            
                            results.append({
                                "sku": sku,
                                "predicted_sales": float(avg_forecast),
                                "current_avg": float(sku_df['y'].mean()),
                                "growth_rate": float((avg_forecast / sku_df['y'].mean() - 1) * 100)
                            })

                        except Exception as e:
                            print(f"Erro na previsão do SKU {sku}: {str(e)}")
                            continue

                    # Ordenar por vendas previstas e pegar os top 5
                    results.sort(key=lambda x: x["predicted_sales"], reverse=True)
                    return {"predictions": results[:5]}

                elif intent == "predict_sku_sales":
                    try:
                        sku = params.get("sku")
                        period = params.get("period", "next_month")
                        periods = 30 if period == "next_month" else 365

                        sku_df = df[df["sku"] == sku]
                        if sku_df.empty:
                            return {"error": f"Não há dados históricos para o SKU {sku}"}

                        # Remover valores negativos e outliers
                        sku_df['y'] = sku_df['y'].clip(lower=0)
                        Q1 = sku_df['y'].quantile(0.25)
                        Q3 = sku_df['y'].quantile(0.75)
                        IQR = Q3 - Q1
                        sku_df = sku_df[
                            (sku_df['y'] >= Q1 - 1.5 * IQR) & 
                            (sku_df['y'] <= Q3 + 1.5 * IQR)
                        ]

                        if len(sku_df) < 2:
                            return {
                                "error": f"Dados insuficientes para fazer previsões confiáveis para o SKU {sku}"
                            }

                        m = self._get_prophet_model('multiplicative')
                        m.fit(sku_df[["ds", "y"]])
                        future = m.make_future_dataframe(periods=periods)
                        forecast = m.predict(future)
                        
                        # Calcular estatísticas
                        last_predictions = forecast.tail(periods)
                        current_avg = float(sku_df['y'].mean())
                        predicted_avg = float(last_predictions['yhat'].mean())
                        growth_rate = (predicted_avg / current_avg - 1) * 100

                        return {
                            "sku": sku,
                            "predicted_sales": predicted_avg,
                            "current_avg": current_avg,
                            "growth_rate": float(growth_rate),
                            "confidence_interval": {
                                "lower": float(last_predictions['yhat_lower'].mean()),
                                "upper": float(last_predictions['yhat_upper'].mean())
                            }
                        }

                    except Exception as e:
                        return {
                            "error": f"Erro ao gerar previsões para o SKU {sku}: {str(e)}"
                        }

        raise ValueError(f"Intent '{intent}' não suportada")


def _demo(engine: Engine, text: str) -> None:
    classifier = RuleIntentClassifier()
    builder = SQLQueryBuilder(engine)
    try:
        intent, params = classifier.classify(text)
    except Exception as e:
        print("Erro ao classificar intenção:", e)
        print("Desculpe — não fui projetado para responder esse tipo de pergunta.")
        return

    print("Intent:", intent)
    print("Params:", params)
    try:
        out = builder.execute(intent, params)
    except Exception as e:
        print("Erro ao executar consulta:", e)
        print("Desculpe — ocorreu um erro ao buscar os dados.")
        return

    # Generate a friendly natural-language response
    rg = ResponseGenerator()
    reply = rg.generate(intent, params, out)
    print("Resposta:")
    print(reply)


class ResponseGenerator:
    """Create dynamic, natural-sounding Portuguese responses from intent+params+result.

    Uses templates with variations to make responses feel more natural and conversational.
    Each intent has a dedicated format method with multiple response patterns.
    New intents just need a new format method and templates added to _response_templates.
    """

    def __init__(self):
        # Maps intent names to their format methods
        self._response_handlers = {
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
        }

    def _format_predict_stockout(self, params: dict, result: Any) -> str:
        if "error" in result:
            return result["error"]

        predictions = result.get("predictions", [])
        if not predictions:
            return "Não foi identificado risco de estoque zero para nenhum SKU no próximo mês."

        # Formatação da resposta
        response = "SKUs com risco de estoque zero:\n\n"
        for p in predictions:
            stockout_date = p["predicted_stockout"].strftime("%d/%m/%Y")
            current_avg = int(p["current_avg"])
            predicted_avg = int(p["predicted_avg"])
            percent_drop = ((current_avg - predicted_avg) / current_avg * 100) if current_avg > 0 else 0
            
            response += (
                f"SKU: {p['sku']}\n"
                f"- Data prevista: {stockout_date}\n"
                f"- Média atual: {current_avg} unidades\n"
                f"- Média prevista: {predicted_avg} unidades\n"
                f"- Queda prevista: {percent_drop:.1f}%\n\n"
            )
        return response

    def _format_predict_top_sales(self, params: dict, result: Any) -> str:
        if "error" in result:
            return result["error"]

        predictions = result.get("predictions", [])
        if not predictions:
            return "Não foi possível fazer previsões de vendas no momento."

        period = "próximo mês" if params.get("period") == "next_month" else "próximo ano"
        response = f"Previsão dos SKUs mais vendidos para o {period}:\n\n"

        for i, p in enumerate(predictions, 1):
            predicted = int(p["predicted_sales"])
            current = int(p["current_avg"])
            growth = p["growth_rate"]
            
            growth_text = (
                f"crescimento de {growth:.1f}%" if growth > 0 
                else f"queda de {abs(growth):.1f}%" if growth < 0
                else "estável"
            )
            
            response += (
                f"{i}. SKU: {p['sku']}\n"
                f"   - Previsão: {predicted} unidades\n"
                f"   - Média atual: {current} unidades\n"
                f"   - Tendência: {growth_text}\n\n"
            )
        return response

    def _format_predict_sku_sales(self, params: dict, result: Any) -> str:
        if "error" in result:
            return result["error"]

        sku = result["sku"]
        predicted = int(result["predicted_sales"])
        current = int(result["current_avg"])
        growth = result["growth_rate"]
        period = "próximo mês" if params.get("period") == "next_month" else "próximo ano"

        growth_text = (
            f"crescimento de {growth:.1f}%" if growth > 0 
            else f"queda de {abs(growth):.1f}%" if growth < 0
            else "estável"
        )

        ci = result.get("confidence_interval", {})
        confidence_text = (
            f"\nIntervalo de confiança: entre {int(ci['lower'])} e {int(ci['upper'])} unidades"
            if ci else ""
        )

        return (
            f"Análise de vendas para o SKU {sku}:\n\n"
            f"- Período: {period}\n"
            f"- Média atual: {current} unidades\n"
            f"- Previsão: {predicted} unidades\n"
            f"- Tendência: {growth_text}{confidence_text}"
        )

    def generate(self, intent: str, params: dict[str, Any], result: Any) -> str:
        """Generate a natural response for the given intent and result.

        Args:
            intent: The classified intent name
            params: Parameters extracted during classification
            result: The raw query result from SQLQueryBuilder

        Returns:
            A friendly Portuguese response describing the result
        """
        handler = self._response_handlers.get(intent)
        if not handler:
            print(
                f"Aviso: Handler de resposta não encontrado para a intenção '{intent}'"
            )
            return f"Não tenho um formato de resposta específico para '{intent}', mas o resultado foi: {result}"

        try:
            return handler(params, result)
        except Exception as e:
            print(f"Erro ao gerar resposta para intent '{intent}': {e}")
            return "Desculpe — não consegui formular uma resposta amigável a partir dos dados retornados."

    def _format_total_stock(self, params: dict, result: Any) -> str:
        """Format response for total stock query."""
        # Verificar se result é um dicionário e se tem a chave total_stock
        if isinstance(result, dict) and "total_stock" in result:
            total = result["total_stock"]
            return f"O total de itens em estoque é {total}."

        return "Nenhum dado disponível sobre estoque."

    def _format_distinct_products_count(self, params: dict, result: Any) -> str:
        c = result.get("distinct_products") if isinstance(result, dict) else None
        return (
            f"Encontramos {c} produtos diferentes no estoque."
            if c is not None
            else "Não foi possível contar os produtos."
        )

    def _format_active_clients_count(self, params: dict, result: Any) -> str:
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

    def _format_sku_sales_compare(self, params: dict, result: Any) -> str:
        """Format response for SKU sales comparison using dynamic templates."""
        sku = params.get("sku", "o SKU solicitado")

        # Format intros
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

    def _format_sku_best_month(self, params: dict, result: Any) -> str:
        sku = result.get("sku", params.get("sku", "o SKU solicitado"))
        bm = result.get("best_month") if isinstance(result, dict) else None
        if bm:
            return f"O melhor mês de vendas para o SKU {sku} foi {bm['month']:02d}/{bm['year']}, com um total de {bm['total']} unidades."
        return f"Não encontrei registros de vendas para o SKU {sku} para determinar o melhor mês."

    def _format_sales_time_series(self, params: dict, result: Any) -> str:
        sku_info = f" para o SKU {params['sku']}" if params.get("sku") else ""
        if isinstance(result, list) and result:
            first = result[0]
            last = result[-1]
            return f"Encontrei {len(result)} registros de vendas mensais{sku_info}, indo de {first['month']:02d}/{first['year']} (Total: {first['total']}) até {last['month']:02d}/{last['year']} (Total: {last['total']})."
        return f"Não há dados de série temporal de vendas disponíveis{sku_info}."

    def _format_sales_between_dates(self, params: dict, result: Any) -> str:
        total = result.get("total") if isinstance(result, dict) else None
        filters = result.get("filters") if isinstance(result, dict) else {}
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

    def _format_top_n_skus(self, params: dict, result: Any) -> str:
        """Format response for top N SKUs query."""
        if not result:
            return "Desculpe, não consegui encontrar os SKUs mais vendidos."

        intro = "Os SKUs com melhor desempenho são:"

        # Format SKU list
        sku_lines = []
        for i, r in enumerate(result, 1):
            sku_lines.append(f"{i}. {r['sku']}: {r['total']} vendas")

        # Join with newlines
        formatted_skus = "\n".join(sku_lines)
        return f"{intro}\n{formatted_skus}"

    def _format_stock_by_client(self, params: dict, result: Any) -> str:
        total = result.get("total_stock_client") if isinstance(result, dict) else None
        filters = result.get("filters") if isinstance(result, dict) else {}
        if total is not None:
            if filters.get("client"):
                return f"O estoque total associado ao cliente {filters['client']} é de {total} unidades."
            return f"O estoque total (considerando todos os clientes/registros) é de {total} unidades."
        client_info = (
            f" para o cliente {params['client']}" if params.get("client") else ""
        )
        return f"Não foi possível calcular o estoque{client_info}."


if __name__ == "__main__":
    # CLI demo: requires a reachable DB configured in settings.DATABASE_URL
    engine = create_engine(settings.DATABASE_URL)
    examples = [
        "Qual o total de items em estoque?",
        "O item SKU_10 teve maior venda em janeiro de 2024 ou em janeiro de 2025?",
        "Qual o mes que SKU_10 mais vendeu?",
        "Quero quantos clientes ativos temos?",
        "Quantos produtos diferentes temos em estoque?",
        "Mostre o top 5 skus mais vendidos",
        "Qual a previsão do tempo para amanhã?",
        "Qual o total de vendas entre janeiro de 2024 e fevereiro de 2024?",
        "Qual o estoque do cliente 4967?",
        "Qual SKU vai ficar sem estoque?",
        "Quais produtos correm risco de acabar?",
        "Previsão de estoque zero",
    ]
    for q in examples:
        print("\nQuerying:", q)
        try:
            _demo(engine, q)
        except Exception as e:
            print("Erro:", e)
