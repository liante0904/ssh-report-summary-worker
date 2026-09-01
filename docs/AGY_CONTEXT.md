# AGY 초기 프로젝트 컨텍스트

이 프로젝트는 `ssh-report-summary-worker` 신규 저장소다.

목표: 기존 `ssh-reports-scraper`의 deprecated `gemini_summary_batch.py`를 복사하지 않고, PostgreSQL의 미요약 PDF 레포트를 조회한 뒤 AGY CLI로 PDF를 직접 요약하고, 검증된 결과만 `report_id` 또는 `report_unique_key` 기준으로 저장하는 독립 worker를 구현한다.

읽기 전용 참고:

- `/home/ubuntu/workspace/lib/ssh_library`
- `/home/ubuntu/workspace/external.reports-hub/apps/scrapers/ssh-reports-scraper/run/gemini_summary_batch.py`
- `/home/ubuntu/workspace/external.reports-hub/apps/scrapers/ssh-reports-scraper/models/SecReportsManager.py`
- `/home/ubuntu/workspace/external.reports-hub/apps/scrapers/ssh-reports-scraper/docs/LLM_GUIDE.md`

절대 수정하지 말 것:

- `ssh_library`
- 기존 `ssh-reports-scraper`
- 운영 DB
- 배포 설정

구현 원칙:

1. API 호출 코드를 작성하지 말고 `agy` CLI를 `subprocess`로 호출한다.
2. PDF URL이 없는 row는 조회 대상에서 제외한다.
3. 다운로드 후 `%PDF-`와 파일 크기를 검증한다.
4. AGY 출력은 JSON schema로 강제한다.
5. DB 저장은 URL 기준이 아니라 `report_id` 또는 `report_unique_key` 기준으로 한다.
6. 기본 실행은 `--dry-run`이다.
7. 첫 구현에서는 scheduler, Docker 배포, 운영 DB write를 추가하지 않는다.
8. 테스트는 AGY 실제 호출 없이 subprocess와 DB adapter를 mock한다.

지금은 구현하지 말고 `docs/IMPLEMENTATION_PROPOSAL.md`의 계약과 최소 파일 목록을 검토·보완하라. 별도 task markdown, Git 조작, 기존 repo 수정은 금지한다.
