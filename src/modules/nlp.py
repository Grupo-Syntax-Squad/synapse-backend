from typing import Any
from sqlalchemy.orm import Session

from src.logger_instance import logger


class ReportGenerator:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._log = logger

    def execute(self) -> None:
        try:
            data = self._get_necessary_processing_data()
            processed_data = self._process_data(data)
            report = self._build_report(processed_data)
            self._save_report(report)
        except Exception as e:
            self._log(f"Error generating report: {e}")

    def _get_necessary_processing_data(self) -> Any: ...

    def _process_data(self, data: Any) -> Any: ...

    def _build_report(self, processed_data: Any) -> dict[str, str]: ...

    def _save_report(self, report: dict[str, str]) -> None: ...
