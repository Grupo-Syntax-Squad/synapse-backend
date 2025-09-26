import json
from typing import Any
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from src.database.get_db import get_db
from src.database.models import Report
from src.logger_instance import logger


class ReportGenerator:
    def __init__(self) -> None:
        self._session: Session = get_db()
        self._log = logger

    def execute(self) -> None:
        try:
            self._log.info("Generating report")
            data = self._get_necessary_processing_data()
            processed_data = self._process_data(data)
            report = self._build_report(processed_data)
            self._save_report(report)
            self._log.info("Successfully generated report")
        except Exception as e:
            self._log.error(f"Error generating report: {e}")
            raise e

    def _get_necessary_processing_data(self) -> dict[str, Any]:
        try:
            queries = {
                "estoque_consumido": """
                    SELECT COALESCE(SUM(es_totalestoque),0) AS total
                    FROM estoque
                    WHERE data BETWEEN current_date - INTERVAL '364 days' AND current_date
                """,
                "frequencia_compra": """
                    SELECT \"SKU\", COUNT(DISTINCT date_trunc('month', data)) AS meses
                    FROM faturamento
                    WHERE data BETWEEN current_date - INTERVAL '364 days' AND current_date
                      AND zs_peso_liquido > 0
                    GROUP BY \"SKU\"
                """,
                "aging": """
                    SELECT AVG(FLOOR(EXTRACT(epoch FROM (current_date - data)) / (60*60*24*7))) AS idade_media
                    FROM estoque
                """,
                "clientes_sku1": """
                    SELECT COUNT(DISTINCT cod_cliente) AS clientes
                    FROM faturamento
                    WHERE \"SKU\" = 'SKU_1'
                      AND data BETWEEN current_date - INTERVAL '364 days' AND current_date
                      AND zs_peso_liquido > 0
                """,
                "skus_sem_estoque": """
                    SELECT f.\"SKU\"
                    FROM faturamento f
                    LEFT JOIN estoque e ON e.\"SKU\" = f.\"SKU\"
                    WHERE f.data BETWEEN current_date - INTERVAL '364 days' AND current_date
                    GROUP BY f.\"SKU\", e.es_totalestoque
                    HAVING SUM(f.zs_peso_liquido) > 0 AND COALESCE(SUM(e.es_totalestoque),0) = 0
                """,
                "itens_repor": """
                    WITH consumo_52 AS (
                        SELECT \"SKU\", SUM(zs_peso_liquido) AS total
                        FROM faturamento
                        WHERE data BETWEEN current_date - INTERVAL '364 days' AND current_date
                        GROUP BY \"SKU\"
                    ),
                    estoque_agg AS (
                        SELECT \"SKU\", SUM(es_totalestoque) AS total
                        FROM estoque
                        WHERE data BETWEEN current_date - INTERVAL '364 days' AND current_date
                        GROUP BY \"SKU\"
                    )
                    SELECT c.\"SKU\"
                    FROM consumo_52 c
                    LEFT JOIN estoque_agg e ON e.\"SKU\" = c.\"SKU\"
                    WHERE (c.total/52.0) > 0
                      AND COALESCE(e.total,0) / (c.total/52.0) < 4
                """,
                "risco_sku1": """
                    WITH consumo AS (
                        SELECT SUM(zs_peso_liquido) AS total
                        FROM faturamento
                        WHERE \"SKU\" = 'SKU_1'
                          AND data BETWEEN current_date - INTERVAL '364 days' AND current_date
                    ),
                    est AS (
                        SELECT SUM(es_totalestoque) AS total
                        FROM estoque
                        WHERE \"SKU\" = 'SKU_1'
                    )
                    SELECT 
                        CASE
                            WHEN c.total IS NULL OR c.total = 0 THEN 'Sem histórico'
                            WHEN COALESCE(e.total,0) = 0 THEN 'Alto risco'
                            WHEN COALESCE(e.total,0) / (c.total/52.0) < 2 THEN 'Alto risco'
                            WHEN COALESCE(e.total,0) / (c.total/52.0) < 4 THEN 'Risco médio'
                            ELSE 'Baixo risco'
                        END AS risco
                    FROM consumo c CROSS JOIN est e
                """,
            }

            results: dict[str, Any] = {}
            for key, sql in queries.items():
                res = self._session.execute(text(sql)).fetchall()
                results[key] = [dict(r._mapping) for r in res]

            return results
        except Exception as e:
            self._log.error(f"Error fetching necessary processing data: {str(e)}")
            raise e

    def _process_data(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            processed = {
                "estoque_consumido_ton": float(data["estoque_consumido"][0]["total"])
                / 1000.0,
                "freq_compra": {
                    row["SKU"]: row["meses"] for row in data["frequencia_compra"]
                },
                "aging_medio": data["aging"][0]["idade_media"],
                "clientes_sku1": data["clientes_sku1"][0]["clientes"],
                "skus_sem_estoque": [row["SKU"] for row in data["skus_sem_estoque"]],
                "itens_repor": [row["SKU"] for row in data["itens_repor"]],
                "risco_sku1": data["risco_sku1"][0]["risco"],
            }
            return processed
        except Exception as e:
            self._log.error(f"Error processing data: {str(e)}")
            raise e

    def _build_report(self, processed_data: dict[str, Any]) -> dict[str, str]:
        try:
            report_content = {
                "Estoque consumido (t)": f"{processed_data['estoque_consumido_ton']:.2f}",
                "Frequência de compra": json.dumps(processed_data["freq_compra"]),
                "Aging médio (semanas)": str(processed_data["aging_medio"]),
                "Clientes SKU_1": str(processed_data["clientes_sku1"]),
                "SKUs sem estoque": ", ".join(processed_data["skus_sem_estoque"])
                or "Nenhum",
                "Itens a repor": ", ".join(processed_data["itens_repor"]) or "Nenhum",
                "Risco SKU_1": processed_data["risco_sku1"],
            }
            return report_content
        except Exception as e:
            self._log.error(f"Error building report: {str(e)}")
            raise e

    def _save_report(self, report: dict[str, str]) -> None:
        try:
            new_report = Report(
                name=f"boletim_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                content=json.dumps(report, ensure_ascii=False, indent=2),
            )
            self._session.add(new_report)
            self._session.commit()
        except Exception as e:
            self._log.error(f"Error saving report in database: {str(e)}")
            self._session.rollback()
            raise e
