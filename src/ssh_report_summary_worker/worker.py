import json
import logging
from pathlib import Path

from .agy_cli import AgyClient
from .config import Config
from .db_adapter import ReportDbAdapter
from .models import Report
from .pdf_downloader import PdfDownloadError, download_pdf

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, config: Config, db: ReportDbAdapter, agy: AgyClient):
        self.config, self.db, self.agy = config, db, agy

    def run(self) -> dict:
        rows = self.db.fetch_pending(self.config.batch_limit)
        result = {"dry_run": self.config.dry_run, "selected": len(rows), "succeeded": 0, "skipped": 0, "failed": 0, "items": []}
        for row in rows:
            report = Report.from_row(row)
            item = {"report_id": report.report_id, "report_unique_key": report.report_unique_key}
            pdf_path = None
            try:
                pdf_path = download_pdf(report.pdf_url, timeout=self.config.pdf_timeout_seconds, min_bytes=self.config.pdf_min_bytes, max_bytes=self.config.pdf_max_bytes, directory=self.config.temp_dir)
                summary = self.agy.summarize(report, pdf_path)
                if self.config.dry_run:
                    item.update(status="dry_run", model=summary.model)
                else:
                    affected = self.db.save_summary(report.report_id, report.report_unique_key, summary.summary, summary.model)
                    item.update(status="saved" if affected == 1 else "skipped", affected_rows=affected)
                result["succeeded" if item["status"] in ("dry_run", "saved") else "skipped"] += 1
            except Exception as exc:
                result["failed"] += 1
                item.update(status="failed", error=f"{type(exc).__name__}: {exc}")
                logger.exception("summary failed for report_id=%s", report.report_id)
            finally:
                if pdf_path:
                    Path(pdf_path).unlink(missing_ok=True)
            result["items"].append(item)
        return result
