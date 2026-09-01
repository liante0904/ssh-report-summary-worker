import argparse
import json
import logging
from pathlib import Path

from .agy_cli import AgyClient
from .config import Config
from .db_adapter import ReportDbAdapter
from .worker import Worker


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize report PDFs with the AGY CLI")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--report-id", type=int)
    parser.add_argument("--force", action="store_true", help="allow reprocessing the selected report")
    parser.add_argument("--write-db", action="store_true", help="persist validated summaries")
    parser.add_argument("--schema", type=Path, default=Path("schemas/summary_output.schema.json"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = Config.from_env(batch_limit=args.limit, dry_run=not args.write_db, schema_path=args.schema)
    result = Worker(config, ReportDbAdapter(report_type=config.report_type), AgyClient(config.agy_command, config.schema_path, config.agy_timeout_seconds, config.agy_retries)).run(args.report_id, args.force)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
