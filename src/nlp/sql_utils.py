from typing import Any
from sqlalchemy import Engine, Row, inspect, text
from collections.abc import Sequence


class SQLUtils:
    def __init__(self, engine: Engine):
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
                type_name = type(t).__name__.lower() if t else ""
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

    def execute_query(
        self, sql: str, bind: dict[str, object] | None = None
    ) -> Sequence[Row[Any]]:
        with self.engine.connect() as conn:
            return conn.execute(text(sql), bind or {}).fetchall()
