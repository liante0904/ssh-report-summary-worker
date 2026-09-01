import json
import os
import random
import subprocess
import time
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .models import Report, SummaryResult


class AgyError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def build_prompt(report: Report, pdf_path: Path) -> str:
    return (
        "Summarize the attached Korean financial research report as strict JSON. "
        "Use the supplied schema exactly. Do not invent facts; cite source page numbers.\n"
        f"Report ID: {report.report_id}\n"
        f"Report key: {report.report_unique_key}\n"
        f"Title: {report.article_title}\n"
        f"Firm: {report.firm_nm}\n"
        f"PDF file: {pdf_path}\n"
        "The output identifiers must exactly match the supplied report identifiers."
    )


class AgyClient:
    def __init__(self, command: str, schema_path: Path, timeout: int = 300, retries: int = 2, sleep=time.sleep):
        self.command = command
        self.schema_path = schema_path
        self.timeout = timeout
        self.retries = retries
        self.sleep = sleep
        self.validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))

    def summarize(self, report: Report, pdf_path: Path) -> SummaryResult:
        command = [
            self.command, "--print", build_prompt(report, pdf_path),
            "--output-format", "json", "--json-schema", str(self.schema_path),
            "--add-dir", str(pdf_path.parent),
        ]
        log_file = os.getenv("AGY_LOG_FILE")
        if log_file:
            command.extend(["--log-file", log_file])
        for attempt in range(self.retries + 1):
            try:
                completed = subprocess.run(
                    command, shell=False, capture_output=True, text=True,
                    encoding="utf-8", timeout=self.timeout, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                if attempt < self.retries:
                    self.sleep(min(60, 2 ** attempt + random.random()))
                    continue
                raise AgyError("AGY timed out", retryable=True) from exc
            if completed.returncode == 0:
                try:
                    raw: dict[str, Any] = json.loads(completed.stdout)
                    status = str(raw.get("status", "")).lower()
                    if status not in ("", "success", "completed"):
                        retryable = status in {"canceled", "cancelled", "timeout"}
                        raise AgyError(f"AGY status: {raw.get('status')}", retryable=retryable)
                    # Current AGY print mode wraps structured output with run
                    # metadata. Keep support for a bare schema object too.
                    value = raw.get("structured_output")
                    if value is None and isinstance(raw.get("response"), str) and raw["response"].strip():
                        value = json.loads(raw["response"])
                    if value is None:
                        value = raw
                    if not isinstance(value, dict):
                        raise AgyError("AGY structured_output is not an object")
                    errors = sorted(self.validator.iter_errors(value), key=lambda e: list(e.path))
                    if errors:
                        raise AgyError(f"AGY schema validation failed: {errors[0].message}")
                    result = SummaryResult.from_json(value)
                    if (result.report_id, result.report_unique_key) != (report.report_id, report.report_unique_key):
                        raise AgyError("AGY identifiers do not match input")
                    return result
                except AgyError as exc:
                    if exc.retryable and attempt < self.retries:
                        self.sleep(min(60, 2 ** attempt + random.random()))
                        continue
                    raise
                except json.JSONDecodeError as exc:
                    raise AgyError("AGY stdout is not JSON") from exc
            stderr = (completed.stderr or "").strip()
            retryable = any(token in stderr.lower() for token in ("429", "rate limit", "timeout", "temporarily", "503", "502", "500"))
            if retryable and attempt < self.retries:
                self.sleep(min(60, 2 ** attempt + random.random()))
                continue
            raise AgyError(f"AGY failed ({completed.returncode}): {stderr[:500]}", retryable=retryable)
        raise AssertionError("unreachable")
