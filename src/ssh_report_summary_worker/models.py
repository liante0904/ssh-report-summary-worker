from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class Report:
    report_id: int
    report_unique_key: str
    article_title: str
    firm_nm: str
    report_date: date | datetime | str | None
    pdf_url: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Report":
        return cls(
            report_id=int(row["report_id"]),
            report_unique_key=str(row["report_unique_key"]),
            article_title=str(row.get("article_title") or ""),
            firm_nm=str(row.get("firm_nm") or ""),
            report_date=row.get("report_date"),
            pdf_url=str(row["pdf_url"]).strip(),
        )


@dataclass(frozen=True)
class SummaryResult:
    report_id: int
    report_unique_key: str
    summary: str
    key_points: list[str]
    risks: list[str]
    model: str
    source_pages: list[int]
    confidence: float

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> "SummaryResult":
        return cls(
            report_id=int(value["report_id"]),
            report_unique_key=str(value["report_unique_key"]),
            summary=value["summary"].strip(),
            key_points=list(value["key_points"]),
            risks=list(value["risks"]),
            model=str(value["model"]),
            source_pages=list(value["source_pages"]),
            confidence=float(value["confidence"]),
        )
