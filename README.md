# ssh-report-summary-worker

독립 실행형 증권 리포트 PDF 요약 worker의 설계 저장소입니다.

현재 단계에서는 구현 코드, scheduler, Docker 배포, 운영 DB write를 포함하지 않습니다. 기존 `ssh-reports-scraper`와 `ssh_library`는 읽기 전용 참고 대상입니다.

## 범위

- PostgreSQL read view에서 아직 요약되지 않은 PDF 리포트 조회
- PDF 다운로드 및 `%PDF-`/파일 크기 검증
- AGY CLI subprocess 호출
- JSON schema 검증 후 `report_id` 또는 `report_unique_key`로 저장
- 기본 실행 모드는 `--dry-run`

## 저장소 경계

- 수정 금지: `ssh-reports-scraper`, `ssh_library`, 운영 DB, 배포 설정
- 운영 DB write는 별도 승인 전까지 실행하지 않음
- AGY는 이 저장소만 별도 프로젝트/세션 컨텍스트로 열어야 함

설계안은 [docs/IMPLEMENTATION_PROPOSAL.md](docs/IMPLEMENTATION_PROPOSAL.md), AGY 초기 컨텍스트는 [docs/AGY_CONTEXT.md](docs/AGY_CONTEXT.md)에 있습니다.
