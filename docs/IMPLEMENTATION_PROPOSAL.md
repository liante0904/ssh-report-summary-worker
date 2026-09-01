# 구현 전 설계안

## 1. 새 repo 디렉터리 구조

```text
ssh-report-summary-worker/
├── README.md
├── pyproject.toml                 # 구현 단계에서 추가
├── src/ssh_report_summary_worker/
│   ├── __init__.py
│   ├── cli.py                     # --dry-run 기본 진입점
│   ├── config.py
│   ├── models.py                  # 입력/출력 typed model
│   ├── db_adapter.py              # read/write 경계
│   ├── pdf_downloader.py          # 다운로드와 PDF 검증
│   ├── agy_cli.py                 # subprocess 격리
│   └── worker.py                  # 단일 batch orchestration
├── schemas/
│   ├── summary_input.schema.json
│   └── summary_output.schema.json
├── tests/
│   ├── test_agy_cli.py
│   ├── test_db_adapter.py
│   ├── test_pdf_downloader.py
│   └── test_worker.py
└── docs/
```

## 2. ssh_library 재사용 계약

읽기 전용으로만 `ssh_library.database.BasePostgreSQLManager`를 의존합니다.

- `__init__(db_name=None, user=None)`: 환경변수/secret 기반 접속 설정
- `_fetchall(sql, params=None)`: `RealDictCursor` 기반 bounded SELECT
- `_execute(sql, params=None)`: 승인된 저장 단계의 parameterized UPDATE에 한정
- `get_connection()`: adapter가 트랜잭션 경계를 직접 관리해야 할 때만 사용

기존 `SecReportsManager`, `gemini_summary_batch.py`는 import하거나 복사하지 않습니다. 특히 URL 기준 update 메서드는 사용하지 않습니다.

## 3. DB read/write 계약

### Read

가능하면 `public.v_sec_reports_canonical`을 기준으로 하고, 요약 상태/저장 대상 컬럼은 live catalog와 versioned migration을 구현 착수 시 재확인합니다. 물리 테이블 컬럼을 snapshot에서 추정하지 않습니다.

논리 입력:

```sql
SELECT r.report_id, r.report_unique_key, r.article_title,
       r.firm_nm, r.report_date, r.pdf_url
FROM public.v_sec_reports_canonical AS r
WHERE COALESCE(btrim(r.pdf_url), '') <> ''
  AND COALESCE(btrim(r.gemini_summary), '') = ''
ORDER BY r.report_id
LIMIT %(limit)s
```

위 SQL은 계약 예시이며, `gemini_summary`가 canonical view에 없거나 별도 요약 테이블이 권위인 경우 live catalog 확인 후 adapter SQL만 조정합니다. URL이 없는 row는 애초에 대상에서 제외합니다.

### Write

- 저장 키 우선순위: `report_id`, 보조 식별자 `report_unique_key`
- URL을 WHERE 조건이나 dedupe 키로 사용하지 않음
- 검증된 summary만 parameterized UPDATE
- `--dry-run`에서는 UPDATE를 호출하지 않고 계획/결과만 출력
- 첫 단계에서는 DDL/migration을 만들거나 실행하지 않음

권장 저장 형태는 기존 요약 컬럼(`gemini_summary`, `summary_time`, `summary_model`)을 live schema가 확인된 경우에만 사용합니다. 별도 `tbl_report_ai_summaries` 사용 여부는 기존 운영 계약을 확인한 뒤 결정하며, 임의 테이블을 새로 만들지 않습니다.

## 4. AGY CLI 호출 방식

`agy_cli.py`가 PDF 경로와 프롬프트를 받아 `subprocess.run`으로 실행합니다. API 호출은 없습니다.

```text
agy run --input <pdf_path> --prompt <prompt_path> \
  --output-format json --schema schemas/summary_output.schema.json
```

위 flag 이름은 AGY 설치본의 `agy --help`로 구현 착수 시 확정하고, worker 내부에는 command builder를 한 곳만 둡니다. 기본 안전 규칙:

- `shell=False`, argument list 사용
- timeout 설정
- stdout만 JSON으로 파싱하고 stderr는 오류 로그로 분리
- exit code 0이 아니거나 JSON/schema 검증 실패면 저장하지 않음
- 429/timeout/일시 오류만 bounded exponential backoff 재시도
- 인증 오류, schema 오류, PDF 오류는 즉시 실패

## 5. JSON schema

### 입력 (`schemas/summary_input.schema.json`)

필수: `report_id`, `report_unique_key`, `article_title`, `firm_nm`, `pdf_path`.
`pdf_url`은 참고 메타데이터이며 다운로드가 끝난 뒤 AGY에는 로컬 `pdf_path`를 전달합니다.

### 출력 (`schemas/summary_output.schema.json`)

필수 필드:

```json
{
  "report_id": 123,
  "report_unique_key": "stable-key",
  "summary": "검증 가능한 요약 본문",
  "key_points": ["핵심 내용 1"],
  "risks": ["위험 요인 1"],
  "model": "agy",
  "source_pages": [1],
  "confidence": 0.0
}
```

`additionalProperties: false`, `summary` 비공백, `confidence`는 0 이상 1 이하, `source_pages`는 양의 정수 배열로 강제합니다. 입력의 식별자와 출력 식별자가 일치하지 않으면 저장하지 않습니다.

## 6. 실패·재시도·중복 실행 방지

- PDF: HTTP 오류, 빈 파일, 파일 크기 하한 미달, 첫 5바이트가 `%PDF-`가 아니면 실패
- AGY: timeout/429/5xx 계열만 최대 재시도 횟수 제한
- 영구 실패는 report key와 원인을 결과에 남기고 다음 row로 진행
- 저장은 `WHERE report_id = %s AND COALESCE(btrim(gemini_summary), '') = ''`처럼 비어 있을 때만 수행
- 저장 직전/직후 식별자를 다시 확인해 다른 row 오염 방지
- 동일 report의 동시 실행은 DB row lock 또는 claim 계약을 구현 단계에서 선택하되, DDL 없이 가능한 기존 컬럼/트랜잭션을 먼저 검토
- 첫 구현은 scheduler 없이 단일 프로세스 batch와 명시적 limit만 지원

## 7. 최소 구현 파일

`pyproject.toml`, `src/ssh_report_summary_worker/{cli,config,models,db_adapter,pdf_downloader,agy_cli,worker}.py`, 두 JSON schema, 그리고 네 개의 mock 기반 테스트만 추가합니다. 실제 AGY 호출과 운영 DB 연결은 테스트에서 금지하고 subprocess/DB adapter를 mock합니다.
