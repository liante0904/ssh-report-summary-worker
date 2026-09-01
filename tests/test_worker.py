from pathlib import Path

from ssh_report_summary_worker.config import Config
from ssh_report_summary_worker.models import SummaryResult
from ssh_report_summary_worker.worker import Worker


class FakeDb:
    def __init__(self): self.saved = []
    def fetch_pending(self, limit):
        return [{"report_id": 1, "report_unique_key": "k", "article_title": "t", "firm_nm": "f", "report_date": None, "pdf_url": "https://example.test/a.pdf"}]
    def save_summary(self, *args): self.saved.append(args); return 1


class FakeAgy:
    def summarize(self, report, pdf_path):
        return SummaryResult(report.report_id, report.report_unique_key, "summary", [], [], "agy", [1], 0.9)


def test_dry_run_never_writes(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7\n" + b"x" * 1024)
    monkeypatch.setattr("ssh_report_summary_worker.worker.download_pdf", lambda *a, **k: pdf)
    db = FakeDb()
    result = Worker(Config(dry_run=True, temp_dir=tmp_path), db, FakeAgy()).run()
    assert result["succeeded"] == 1
    assert db.saved == []


def test_write_mode_updates_once(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7\n" + b"x" * 1024)
    monkeypatch.setattr("ssh_report_summary_worker.worker.download_pdf", lambda *a, **k: pdf)
    db = FakeDb()
    result = Worker(Config(dry_run=False, temp_dir=tmp_path), db, FakeAgy()).run()
    assert result["succeeded"] == 1
    assert db.saved == [(1, "k", "summary", "agy")]
