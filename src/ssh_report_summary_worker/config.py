from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil


DEFAULT_SECRET_FILE = Path("/home/ubuntu/secrets/workspace/external.reports-hub/apps/scrapers/ssh-report-summary-worker/secrets.json")


def load_external_secrets(path: Path | None = None) -> Path | None:
    """Load workspace secrets without putting them in the repository.

    Existing environment variables always win. The workspace service format
    stores database settings under ``common``; POSTGRES_REPORT_DB is accepted
    as the sibling service's name for compatibility with ssh_library's
    POSTGRES_DB setting.
    """
    secret_path = path or Path(os.getenv("SUMMARY_SECRET_FILE", DEFAULT_SECRET_FILE))
    if not secret_path.is_file():
        return None
    data = json.loads(secret_path.read_text(encoding="utf-8"))
    values = data.get("common", {}) if isinstance(data, dict) else {}
    if not isinstance(values, dict):
        raise ValueError("secret file common section must be an object")
    values = {**data, **values}
    if "POSTGRES_DB" not in values and "POSTGRES_REPORT_DB" in values:
        values["POSTGRES_DB"] = values["POSTGRES_REPORT_DB"]
    for key in ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        if values.get(key) is not None and not os.getenv(key):
            os.environ[key] = str(values[key])
    return secret_path


@dataclass(frozen=True)
class Config:
    batch_limit: int = 10
    report_type: str = "COMPANY"
    dry_run: bool = True
    agy_command: str = "agy"
    agy_timeout_seconds: int = 300
    agy_retries: int = 2
    pdf_timeout_seconds: int = 30
    pdf_max_bytes: int = 50 * 1024 * 1024
    pdf_min_bytes: int = 1024
    schema_path: Path = Path("schemas/summary_output.schema.json")
    temp_dir: Path | None = None

    @classmethod
    def from_env(cls, **overrides):
        load_external_secrets()
        values = {
            "batch_limit": int(os.getenv("SUMMARY_BATCH_LIMIT", "10")),
            "report_type": os.getenv("SUMMARY_REPORT_TYPE", "COMPANY"),
            "agy_command": os.getenv("AGY_COMMAND") or shutil.which("agy") or "/home/ubuntu/.local/bin/agy",
            "agy_timeout_seconds": int(os.getenv("AGY_TIMEOUT_SECONDS", "300")),
            "agy_retries": int(os.getenv("AGY_RETRIES", "2")),
            "pdf_timeout_seconds": int(os.getenv("PDF_TIMEOUT_SECONDS", "30")),
            "pdf_max_bytes": int(os.getenv("PDF_MAX_BYTES", str(50 * 1024 * 1024))),
            "pdf_min_bytes": int(os.getenv("PDF_MIN_BYTES", "1024")),
        }
        values.update(overrides)
        return cls(**values)
