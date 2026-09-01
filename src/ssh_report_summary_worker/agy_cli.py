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
        "You are a senior Korean equity research analyst. Analyze the attached PDF and "
        "return strict JSON using the supplied schema. The database summary must be "
        "decision-useful, evidence-based, and specific rather than a generic abstract.\n"
        "\nRequired analysis for every report:\n"
        "1) State the report's core thesis and the exact conclusion.\n"
        "2) Extract the key numerical evidence: dates/periods, growth or performance, "
        "flows, holdings, weights, target prices, valuation, and benchmark comparison "
        "when present. Preserve units and direction.\n"
        "3) Identify the named companies, ETFs, sectors, and the concrete catalyst or "
        "mechanism linking the evidence to the conclusion.\n"
        "4) Explain what changed versus the prior period or prevailing view, if stated.\n"
        "5) Give an actionable investor takeaway: beneficiary/watchlist, time horizon, "
        "what would confirm the thesis, and what would invalidate it. This is analysis, "
        "not personalized investment advice.\n"
        "6) List material risks, caveats, missing data, and any uncertainty.\n"
        "\nETF-specific requirements when applicable:\n"
        "- Separate ETF flow/inclusion data from price-performance results.\n"
        "- Name the relevant ETF and constituent stocks; include inclusion/exclusion "
        "direction, observation window, and counts/weights if available.\n"
        "- Distinguish reported results from the report author's proposed strategy.\n"
        "\nWriting requirements for the summary field:\n"
        "- Write in Korean, with compact headings: 핵심 결론 / 근거와 수치 / 수혜 종목·산업 / "
        "투자 체크포인트 / 리스크.\n"
        "- Do not start with boilerplate such as '본 보고서는 ... 분석합니다'.\n"
        "- Every important number, named stock, or causal claim must have a page citation "
        "in the form [p.N]. If the PDF does not support it, say '자료에 없음' rather than "
        "guessing.\n"
        "- Keep key_points focused on concrete findings and risks focused on falsifiable "
        "downside conditions. Use the supplied schema exactly.\n"
        f"Report ID: {report.report_id}\n"
        f"Report key: {report.report_unique_key}\n"
        f"Title: {report.article_title}\n"
        f"Firm: {report.firm_nm}\n"
        f"PDF file: {pdf_path}\n"
        "The output identifiers must exactly match the supplied report identifiers."
    )


class AgyClient:
    def __init__(self, command: str, schema_path: Path, timeout: int = 300, retries: int = 2, sleep=time.sleep, model: str | None = None):
        self.command = command
        self.schema_path = schema_path
        self.timeout = timeout
        self.retries = retries
        self.sleep = sleep
        self.model = model or os.getenv("AGY_MODEL", "gemini-3.1-pro-high")
        self.validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))

    def summarize(self, report: Report, pdf_path: Path) -> SummaryResult:
        command = [
            self.command, "--print", build_prompt(report, pdf_path),
            "--output-format", "json", "--json-schema", str(self.schema_path),
            "--add-dir", str(pdf_path.parent),
            "--model", self.model,
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
                    response = raw.get("response")
                    if value is None and isinstance(response, str) and response.strip():
                        value = json.loads(response)
                    if value is None and isinstance(response, dict):
                        value = response
                    # Some AGY responses omit structured_output and put the
                    # schema payload in response alongside tool metadata.
                    if isinstance(value, dict):
                        allowed = set(self.validator.schema.get("properties", {}))
                        value = {key: item for key, item in value.items() if key in allowed}
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
