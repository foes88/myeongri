# 공개 Git 이력 정리 준비 (로컬 전용 — 원격 변경 없음)

## 상태
- 이 문서는 **로컬 브랜치 준비 결과**다. 원격 push, 원격 브랜치 삭제·교체, force push, main 병합, Vercel 배포는 실행하지 않았다(별도 승인 대상).
- 기존 브랜치 `feature/v6.1-verification-mingli-l345`는 그대로 보존되어 있다(로컬·원격, 로컬이 원격보다 앞섬). 정리용 브랜치는 `clean/v6.6-history-prep`.

## 만든 방식
1. 기존 브랜치 보존 — 변경하지 않음.
2. `main`(`cb7be0a`)에서 새 로컬 브랜치 `clean/v6.6-history-prep` 생성.
3. 작업 트리를 비운 뒤 개발 브랜치의 **최종 파일 상태만** 반영(`git rm -rq .` → `git checkout <feature> -- .`). 중간 커밋 이력은 가져오지 않음.
4. 제외 확인: `data_private/`, HKO·KASI 원자료(`hko_lunar_terms.json`, `kasi_calendar.json`, `kasi_almanac.json`, `kasi_service.json`), 외부 파생 케이스(`cases_external.json`), 천문 데이터(`*.bsp`), 임시 WSL 산출물은 인덱스에 없음 (`git ls-files` 검사, `tools/check_distribution.py`).
5. 단일 커밋으로 기록. 부모는 `cb7be0a` 하나.

## 검증 결과 (정리 브랜치에서 실행)
| 항목 | 결과 |
|---|---|
| 변경 파일 | main 대비 약 105개 파일(추가 대부분, 수정 5개: `.gitignore`, `main.py`, `privacy_scan.py`, `requirements.txt`, `docs/03`) |
| 개인정보 검사 `python -m app.privacy_scan` | clean (이 검사에서 문서 한 줄을 고쳤다) |
| 배포·라이선스 검사 `python -m tools.check_distribution` | clean: 추적 금지 경로 없음, `golden/*` 전 파일이 `DATA_MANIFEST.json`에 분류됨, 외부 집계 파일에 행 단위 표 없음, 의존성 라이선스 표 일치, sxtwl 미포함 |
| 전체 테스트 | 803 통과, 16 건너뜀(브라우저 마커). 비공개 외부 자료가 없는 새 클론에서는 외부 파생 케이스 366건이 건너뛰어짐(로컬 재현 명령은 docs/08) |
| 이력에 `943ea23` 포함 여부 | **포함되지 않음** (`git merge-base --is-ancestor 943ea23 HEAD` → 아님). `c2f55f0`, `664f830`, `e3165f5`도 없음 |

## 공개 노출 현황(변경 없음)
- 원격 브랜치 `feature/v6.1-verification-mingli-l345`의 커밋 `943ea23`에 HKO/KASI 추출 자료와 외부 파생 케이스가 남아 있다. 이 브랜치는 공개 저장소에서 여전히 열람 가능하다.
- 포크 0, PR 0, 태그 0(2026-10-29 조사). `main`은 `cb7be0a` 그대로.

## Vercel 연동 상태 (기록)
- GitHub 커밋 상태에 Vercel 프로젝트 2개(`myeongri`, `backend`)가 보고됨: **어떤 브랜치든 push 하면 두 프로젝트에서 미리보기 배포가 자동 생성될 수 있다.**
- 따라서 정리 브랜치를 새 이름으로 push 하는 것도 배포를 유발한다. 승인 시 push 전에 (a) Vercel 프로젝트의 Git 연동/미리보기 보호 설정, (b) `backend` 프로젝트의 Root Directory·공개 여부를 확인할 것.
- `web/`의 `vercel.json`은 정적 서비스(`outputDirectory: web`)이며 `X-Robots-Tag: noindex`를 설정한다.

## 승인 후 실행안 (실행하지 않음)
선택 A — 새 브랜치로 교체(가장 단순):
```
# 0) Vercel 미리보기 영향 확인 후
git push origin clean/v6.6-history-prep:feature/v6.6-clean      # 새 원격 브랜치(배포 유발 가능)
# 1) 확인 후 구 브랜치 삭제 (파괴적)
git push origin --delete feature/v6.1-verification-mingli-l345
```
선택 B — 같은 이름 유지(force push 필요, 파괴적):
```
git push --force-with-lease origin clean/v6.6-history-prep:feature/v6.1-verification-mingli-l345
```
공통 주의: 삭제·교체 후에도 GitHub가 참조 없는 객체를 GC 하기 전까지 커밋 SHA 직접 접근이 가능할 수 있고, 캐시·외부 스냅샷은 회수할 수 없다. 이용 조건이 허용으로 확인되면 정리 자체가 불필요할 수 있다.

## 남은 결정 사항
1. HKO·KASI 이용 조건 확인 결과(허용이면 정리 불필요).
2. 위 선택 A/B 또는 현상 유지.
3. Vercel `backend` 프로젝트 처리.
