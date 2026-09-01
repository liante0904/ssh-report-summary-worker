from pathlib import Path

import pytest

from ssh_report_summary_worker.pdf_downloader import PdfDownloadError, download_pdf


class Response:
    headers = {}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, _size):
        if hasattr(self, "done"): return b""
        self.done = True
        return b"%PDF-1.7\n" + b"x" * 1024


def test_download_validates_pdf_signature(tmp_path, monkeypatch):
    monkeypatch.setattr("ssh_report_summary_worker.pdf_downloader.urlopen", lambda *a, **k: Response())
    path = download_pdf("https://example.test/a.pdf", timeout=1, min_bytes=10, max_bytes=4096, directory=tmp_path)
    assert path.read_bytes().startswith(b"%PDF-")
    path.unlink()


def test_download_rejects_non_pdf(tmp_path, monkeypatch):
    class Bad(Response):
        def read(self, _size):
            if hasattr(self, "done"): return b""
            self.done = True
            return b"not-pdf"
    monkeypatch.setattr("ssh_report_summary_worker.pdf_downloader.urlopen", lambda *a, **k: Bad())
    with pytest.raises(PdfDownloadError):
        download_pdf("https://example.test/a", timeout=1, min_bytes=1, max_bytes=4096, directory=tmp_path)
