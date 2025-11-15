from datetime import datetime

from jinja2 import Template

from src.logger_instance import logger
from src.settings import settings


class EmailBuilder:
    def __init__(
        self, report_name: str, report_date: datetime, metrics: dict[str, str]
    ):
        self._log = logger
        self._template_path = settings.EMAIL_TEMPLATE_PATH
        self._github_url = settings.GITHUB_URL
        self._metrics = metrics
        self._report_name = report_name
        self._report_date = report_date

    def execute(self) -> str:
        email_template = self._load_html_template()
        metrics_html = self._build_html_metrics()
        email_html = email_template.render(
            subject=self._report_name,
            report_date=self._report_date.strftime("%d/%m/%Y %H:%M"),
            metrics=metrics_html,
            current_year=self._report_date.strftime("%Y"),
            github_url=self._github_url,
        )
        return email_html

    def _load_html_template(self) -> Template:
        try:
            with open(self._template_path, "r", encoding="utf-8") as template_file:
                content = template_file.read()
            return Template(content)
        except Exception as e:
            self._log.error(f"Error loading html template: {str(e)}")
            raise e

    def _build_html_metrics(self) -> str:
        metric_cards: list[str] = []

        metric_configs = {
            "Estoque consumido (t): ": {
                "title": "Estoque Consumido",
                "icon": "📦",
                "description": "Total de estoque consumido nos últimos 12 meses",
                "unit": "toneladas",
            },
            "Frequência de compra: ": {
                "title": "Frequência de Compras",
                "icon": "🛒",
                "description": "Distribuição mensal de registros de compra",
                "unit": "",
            },
            "Aging médio (semanas): ": {
                "title": "Aging Médio",
                "icon": "⏱️",
                "description": "Tempo médio de permanência do estoque",
                "unit": "semanas",
            },
            "Clientes SKU_1: ": {
                "title": "Clientes SKU_1",
                "icon": "👥",
                "description": "Número de clientes únicos que compraram SKU_1",
                "unit": "clientes",
            },
            "SKUs sem estoque: ": {
                "title": "SKUs sem Estoque",
                "icon": "⚠️",
                "description": "Produtos com demanda mas sem estoque disponível",
                "unit": "itens",
            },
            "Itens a repor: ": {
                "title": "Itens para Reposição",
                "icon": "🔄",
                "description": "Produtos que precisam de reposição urgente",
                "unit": "itens",
            },
            "Risco SKU_1: ": {
                "title": "Status de Risco SKU_1",
                "icon": "🎯",
                "description": "Nível de risco de desabastecimento do produto principal",
                "unit": "",
            },
        }

        for key, value in self._metrics.items():
            config = metric_configs.get(
                key,
                {
                    "title": key.replace(": ", ""),
                    "icon": "📊",
                    "description": "Métrica do sistema",
                    "unit": "",
                },
            )

            if key == "Frequência de compra: ":
                card_html = f"""
                <div class="metric-card">
                    <h3>{config["icon"]} {config["title"]}</h3>
                    <div class="description">{config["description"]}</div>
                    <div style="margin-top: 15px;">
                        {value}
                    </div>
                </div>
                """
            elif key == "Risco SKU_1: ":
                status_class = self._get_risk_status_class(str(value))
                card_html = f"""
                <div class="metric-card">
                    <h3>{config["icon"]} {config["title"]}</h3>
                    <div class="value">
                        <span class="status-indicator {status_class}">{value}</span>
                    </div>
                    <div class="description">{config["description"]}</div>
                </div>
                """
            else:
                formatted_value = self._format_metric_value(str(value), config["unit"])
                card_html = f"""
                <div class="metric-card">
                    <h3>{config["icon"]} {config["title"]}</h3>
                    <div class="value">{formatted_value}</div>
                    <div class="description">{config["description"]}</div>
                </div>
                """

            metric_cards.append(card_html)

        return "\n".join(metric_cards)

    def _get_risk_status_class(self, risk_value: str) -> str:
        risk_lower = risk_value.lower()
        if "alto risco" in risk_lower:
            return "status-high-risk"
        elif "risco médio" in risk_lower or "médio" in risk_lower:
            return "status-medium-risk"
        elif "baixo risco" in risk_lower:
            return "status-low-risk"
        else:
            return "status-medium-risk"

    def _format_metric_value(self, value: str, unit: str) -> str:
        try:
            if value.replace(".", "").replace(",", "").isdigit():
                num_value = float(value)
                if num_value == int(num_value):
                    formatted = f"{int(num_value):,}".replace(",", ".")
                else:
                    formatted = (
                        f"{num_value:,.2f}".replace(",", "X")
                        .replace(".", ",")
                        .replace("X", ".")
                    )

                if unit:
                    return f"{formatted} <small>{unit}</small>"
                return formatted
            else:
                return value
        except Exception:
            return value
