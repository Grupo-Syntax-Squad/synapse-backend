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
            with open(self._template_path, "r") as template_file:
                content = template_file.read()
            return Template(content)
        except Exception as e:
            self._log.error(f"Error loading html template: {str(e)}")
            raise e

    def _build_html_metrics(self) -> str:
        metrics_li: list[str] = []
        for key, value in self._metrics.items():
            metrics_li.append(f"<li><strong>{key}</strong> {value}</li>")
        return "\n".join(metrics_li)
