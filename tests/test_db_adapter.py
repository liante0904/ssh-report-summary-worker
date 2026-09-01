from ssh_report_summary_worker.db_adapter import ReportDbAdapter


class FakeManager:
    def __init__(self): self.calls = []
    def _fetchall(self, sql, params): self.calls.append(("read", sql, params)); return []
    def _execute(self, sql, params): self.calls.append(("write", sql, params)); return {"affected_rows": 1}


def test_read_is_bounded_and_excludes_missing_pdf():
    fake = FakeManager()
    ReportDbAdapter(fake).fetch_pending(7)
    assert fake.calls[0][2] == {"limit": 7, "report_type": "COMPANY"}
    assert "pdf_url" in fake.calls[0][1]
    assert "LIMIT %(limit)s" in fake.calls[0][1]
    assert "report_type = %(report_type)s" in fake.calls[0][1]


def test_write_uses_both_identifiers_and_empty_summary_guard():
    fake = FakeManager()
    assert ReportDbAdapter(fake).save_summary(3, "key-3", "text", "agy") == 1
    call = fake.calls[0]
    assert call[2] == ("text", "agy", 3, "key-3")
    assert "report_id = %s" in call[1]
    assert "report_unique_key = %s" in call[1]
    assert "gemini_summary" in call[1]


def test_single_report_query_uses_report_id():
    fake = FakeManager()
    ReportDbAdapter(fake).fetch_by_report_id(259835444)
    assert fake.calls[0][2]["report_id"] == 259835444
    assert "report_id = %(report_id)s" in fake.calls[0][1]
