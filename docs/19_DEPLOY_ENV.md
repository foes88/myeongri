# 배포 환경변수와 Postgres 연결 (회원 기능)

회원 기능은 **영속 DB 가 연결되고 명시적으로 켜야** 운영에서 동작한다(서버리스 파일시스템은 휘발성).

| 변수 | 필수 | 설명 |
|---|---|---|
| `APP_ENV=production` | 운영 | 파일 키 자동 생성 금지, 회원 기능 기본 비활성 |
| `ACCOUNTS_ENABLED=1` | 운영에서 회원 기능을 켤 때 | DB·키가 준비된 뒤에만 설정 |
| `DATABASE_URL` | 운영 | `postgresql://…?sslmode=require`. 관리형 DB 의 **풀러** 주소 권장(서버리스는 호출마다 연결) |
| `DATABASE_SCHEMA` | 선택 | 지정하면 해당 스키마를 만들어 사용(환경 분리·테스트) |
| `APP_DATA_KEY` | 운영 | Fernet 키(44자 base64). 분실하면 저장 데이터를 복호화할 수 없다 → 비밀 관리자에 백업. 키 교체는 재암호화 절차 필요(미구현) |
| `TRUST_PROXY=1` | 프록시 뒤 | `X-Forwarded-For` 의 첫 IP 를 rate limit 에 사용 |
| `SESSION_TTL_SECONDS`, `FREE_DAILY_REPORTS` | 선택 | 기본 14일, 20건/일 |
| `CORS_ORIGINS` | 선택 | 쉼표 구분 허용 출처 |

## 로컬 검증 (Docker)
```
docker run -d --name myeongri-pg-test -e POSTGRES_PASSWORD=testpw -e POSTGRES_DB=myeongri_test -p 127.0.0.1:55499:5432 postgres:16-alpine
PG_TEST_URL=postgresql://postgres:testpw@127.0.0.1:55499/myeongri_test python -m pytest backend/tests/test_v72_accounts.py backend/tests/browser/test_oneshot_ui.py -m "browser or not browser"
```
`PG_TEST_URL` 이 없으면 Postgres 변형 테스트는 건너뛴다(SQLite 변형은 항상 실행).

## 아직 안 된 것 (BLOCKED / 미구현)
- 관리형 DB 계정(Neon·Supabase·RDS 등)과 실제 연결: 외부 계정 필요. 로컬 컨테이너(Postgres 16)로만 검증함.
- rate limit 공유 저장소: 현재 프로세스 메모리 → 서버리스·다중 인스턴스에서는 DB 또는 Redis 기반 구현으로 교체 필요.
- 스키마 마이그레이션 도구, 백업·복구 절차(공급자 기능 + 복구 리허설), 만료 세션 정리 작업 스케줄, 데이터 키 교체.
- 만료 세션 정리 함수(`purge_expired_sessions`)는 Postgres 구현에만 있으며 주기 실행은 미설정.
