# ssh-report-summary-worker

독립 실행형 증권 리포트 PDF 요약 worker의 설계 저장소입니다.

현재 구현은 scheduler/Docker 배포 없이 단일 batch로 동작합니다. 기본 실행은 dry-run이며, `--write-db`를 명시해야만 검증된 요약을 저장합니다. 기존 `ssh-reports-scraper`와 `ssh_library`의 코드는 복사하지 않습니다.

## 범위

- PostgreSQL read view에서 아직 요약되지 않은 PDF 리포트 조회
- 기본적으로 `report_type=COMPANY` 종목 레포트만 조회 (`SUMMARY_REPORT_TYPE`으로 변경 가능)
- PDF 다운로드 및 `%PDF-`/파일 크기 검증
- AGY CLI subprocess 호출
- JSON schema 검증 후 `report_id` 또는 `report_unique_key`로 저장
- 기본 실행 모드는 `--dry-run`

## 실행

private `ssh_library`를 import할 수 있도록 library checkout을 `PYTHONPATH`에 추가합니다.
DB 설정은 Git 저장소 밖의
`/home/ubuntu/secrets/workspace/external.reports-hub/apps/scrapers/ssh-report-summary-worker/secrets.json`
에서 자동으로 읽습니다. `SUMMARY_SECRET_FILE`로 경로를 바꿀 수 있습니다.

```bash
PYTHONPATH=/home/ubuntu/workspace/lib/ssh_library:src \
  python3 -m ssh_report_summary_worker.cli --limit 10
```

실제 저장은 명시적으로만 활성화합니다.

```bash
PYTHONPATH=/home/ubuntu/workspace/lib/ssh_library:src \
  python3 -m ssh_report_summary_worker.cli --limit 10 --write-db
```

AGY는 설치된 CLI의 print 인터페이스(`agy --print ... --output-format json --json-schema ...`)를 사용합니다. API 호출은 하지 않습니다.

## CI/CD

- `.github/workflows/test.yml`: Python 3.10/3.12 deterministic test gate
- `.github/workflows/build-artifact.yml`: `main` push 또는 수동 실행 시 테스트 후 source artifact 생성
- `.github/workflows/deploy.yml`: `main` push 시 SSH로 서버에 source를 배포하고 AGY/외부 secrets/CLI runtime을 검증

현재 deploy workflow는 운영 DB write, AGY 요약 실행, scheduler 등록, 서버 재기동을 하지 않습니다. worker 실행 스케줄과 명시적 write 승인 후 실행 단계를 별도로 추가합니다.

## 저장소 경계

- 수정 금지: `ssh-reports-scraper`, `ssh_library`, 운영 DB, 배포 설정
- 운영 DB write는 별도 승인 전까지 실행하지 않음
- AGY는 이 저장소만 별도 프로젝트/세션 컨텍스트로 열어야 함

설계안은 [docs/IMPLEMENTATION_PROPOSAL.md](docs/IMPLEMENTATION_PROPOSAL.md), AGY 초기 컨텍스트는 [docs/AGY_CONTEXT.md](docs/AGY_CONTEXT.md)에 있습니다.
