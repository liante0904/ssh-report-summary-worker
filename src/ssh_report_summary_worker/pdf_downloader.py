from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen


class PdfDownloadError(RuntimeError):
    pass


def download_pdf(url: str, *, timeout: int, min_bytes: int, max_bytes: int, directory: Path | None = None) -> Path:
    if not url.strip():
        raise PdfDownloadError("empty pdf URL")
    request = Request(url, headers={"User-Agent": "ssh-report-summary-worker/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise PdfDownloadError("PDF exceeds maximum size")
            with NamedTemporaryFile(prefix="summary-", suffix=".pdf", dir=directory, delete=False) as output:
                path = Path(output.name)
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise PdfDownloadError("PDF exceeds maximum size")
                    output.write(chunk)
    except PdfDownloadError:
        if "path" in locals():
            path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if "path" in locals():
            path.unlink(missing_ok=True)
        raise PdfDownloadError(str(exc)) from exc
    if total < min_bytes or path.read_bytes()[:5] != b"%PDF-":
        path.unlink(missing_ok=True)
        raise PdfDownloadError("downloaded file is not a valid PDF")
    return path
