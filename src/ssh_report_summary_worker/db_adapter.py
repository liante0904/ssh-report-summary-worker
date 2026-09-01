from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ssh_library.database import BasePostgreSQLManager


class ReportDbAdapter:
    read_sql = """
        SELECT report_id, report_unique_key, article_title, firm_nm,
               report_date, pdf_url
        FROM public.v_sec_reports_canonical
        WHERE COALESCE(btrim(pdf_url), '') <> ''
          AND COALESCE(btrim(gemini_summary), '') = ''
          AND report_unique_key IS NOT NULL
          AND report_type = %(report_type)s
        ORDER BY report_id DESC
        LIMIT %(limit)s
    """

    def __init__(self, manager: "BasePostgreSQLManager | None" = None, report_type: str = "COMPANY"):
        if manager is None:
            from ssh_library.database import BasePostgreSQLManager
            manager = BasePostgreSQLManager()
        self.manager = manager
        self.report_type = report_type

    def fetch_pending(self, limit: int) -> list[dict[str, Any]]:
        return self.manager._fetchall(self.read_sql, {"limit": limit, "report_type": self.report_type})

    def fetch_by_report_id(self, report_id: int, force: bool = False) -> list[dict[str, Any]]:
        sql = self.read_sql.replace(
            "AND report_unique_key IS NOT NULL",
            "AND report_unique_key IS NOT NULL\n          AND report_id = %(report_id)s",
        )
        if force:
            sql = sql.replace("AND COALESCE(btrim(gemini_summary), '') = ''", "")
        return self.manager._fetchall(
            sql,
            {"limit": 1, "report_type": self.report_type, "report_id": report_id},
        )

    def save_summary(self, report_id: int, report_unique_key: str, summary: str, model: str) -> int:
        result = self.manager._execute(
            """
            UPDATE tbl_sec_reports
               SET gemini_summary = %s,
                   summary_time = CURRENT_TIMESTAMP,
                   summary_model = %s
             WHERE report_id = %s
               AND report_unique_key = %s
               AND COALESCE(btrim(gemini_summary), '') = ''
            """,
            (summary, model, report_id, report_unique_key),
        )
        affected = int(result.get("affected_rows", 0)) if isinstance(result, dict) else 0
        if affected > 1:
            raise RuntimeError(f"unexpected update rowcount: {affected}")
        return affected
