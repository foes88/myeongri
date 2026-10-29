# 고전 규칙 37개 원문 검증 결과 (P0)

산출: `backend/golden/classical_verification.json`, 조회 API `app/mingli/classical.py`, 재실행 `python -m tools.verify_classical` (네트워크 필요), 테스트 `tests/test_classical.py`. 접근일 2026-10-29.
`rules.py` 는 수정하지 않았다(각 규칙의 `classical_verification: pending` 표기는 그대로이며, 병합은 별도 작업).

## 상태 정의 (보수적)
| 상태 | 의미 |
|---|---|
| pending | 확인하지 못함 |
| location_confirmed | 출처 페이지에서 장·핵심어(2글자 이상) 위치만 확인. 구절이 규칙 내용을 직접 뒷받침하는지는 **판단하지 않음** |
| text_confirmed | 사람이 구절을 읽고, `scope_note` 에 적은 **범위에서** 규칙 내용에 대응함을 확인. 발췌(≤40자)가 페이지 텍스트에 그대로 있는지 스크립트가 재검증하며, 없으면 자동 강등 |
| implementation_convention | 고전 주장 없음(구현자 규약) |

`text_confirmed` 는 "고전과 일치한다"가 아니라 "표시한 범위에서 원문이 뒷받침한다"이다. 범위·한계는 항목마다 `scope_note` 에 있다.

## 결과 요약
| 상태 | 개수 |
|---|---|
| text_confirmed | 23 |
| location_confirmed | 8 |
| implementation_convention | 6 |
| pending | 0 |
| 합계 | 37 |

**CLASSICAL_RULES_PENDING 은 해제되지 않는다**: location_confirmed 8개가 남아 있고, text_confirmed 도 범위 한정이다. 판본 교감(영인본 대조)은 하지 않았다.

## 접속 실패한 출처
- `donglishuzhai.net/chapter/3721.html`(子平真詮 卷一·八), `m.donglishuzhai.net/chapter/3722.html`(卷一·九): 30초 연결 시간 초과로 열지 못함. 대신 `libokang.com` 의 子平真詮評註(원문 + 평주)를 사용했다. 두 URL 에 대한 대조는 **미수행**.

## 규칙별 상태
| 규칙 | 상태 | 근거 출처 | 비고(범위·한계) |
|---|---|---|---|
| MG-L1-WOLRYEONG | text_confirmed | 滴天髓 月令論 | 月令=提綱 |
| MG-L1-DEUKRYEONG-BONGI | location_confirmed | 滴天髓 月令論 | 得令 개념어만. '본기 비겁·인성이면 득령'은 후대 신강약 개념, 원문 대응 미확인 |
| MG-L1-DEUKRYEONG-SEASON | location_confirmed | 滴天髓 寒暖論 | 계절 오행 기준 득령은 원문 대응 미확인 |
| MG-L1-HIDDEN-ROLE | text_confirmed | 滴天髓 月令論 | 寅月 한 예(戊→丙→甲)만. 12지 표·사령 일수는 미확인 |
| MG-L1-TONGGEUN | text_confirmed(주석) | 滴天髓闡微 任氏曰 | 寅卯=木 통근. 엄격/관대/강중약은 구현 규약 |
| MG-L1-TUGAN | text_confirmed | 子平真詮 用神變化 | 투출이 작용 글자를 바꿈 |
| MG-L1-SUPPORT-ORDINAL | convention | - | 억부론 관점 구현 규칙 |
| MG-L2-STEM-HAP | text_confirmed | 子平真詮 論十干配合 | 5쌍 화오행 확인 |
| MG-L2-HAP-HWA | location_confirmed | 子平真詮 論十干合而不合 | '間隔이면 합이 안 됨'만 대응. 5개 조건 전체는 미확인 |
| MG-L2-BRANCH-YUKHAP | text_confirmed | 子平真詮 論刑沖會合解法 | 대표쌍 子丑만 |
| MG-L2-SAMHAP | text_confirmed | 同上 | 원문은 申子辰을 '三會'라 부름(용어 차이) |
| MG-L2-BANGHAP | location_confirmed | 同上 | '三方為會' 문구만. 방합 조합 나열 없음 |
| MG-L2-CHUNG | text_confirmed | 同上 | 대표쌍 子午·卯酉만 |
| MG-L2-HYUNG | location_confirmed | 同上 | 저자가 三刑을 **闕疑(보류)** 로 둠 |
| MG-L2-PA | location_confirmed | 三命通會 卷三 | **불일치**: 원문은 寅亥·巳申을 三合/六合이므로 破로 취하지 않음. 본 구현 표(6쌍)와 다름 |
| MG-L2-HAE | location_confirmed | 滴天髓闡微 任氏曰 | 害(穿)에 회의적. 寅亥/寅巳 분류가 자료마다 다름 |
| MG-L2-GOGO | text_confirmed | 子平真詮 論墓庫刑沖之說 | 원문은 '庫는 반드시 沖해야 열린다'를 속설로 부정 → 개고를 논쟁으로 두는 처리와 부합 |
| MG-L2-COMPETITION | text_confirmed | 子平真詮 論刑沖會合解法 | 합이 충을 푼다는 입장(합 우선설)만 직접 뒷받침 |
| MG-L3-SIKSANG-SAENGJAE | text_confirmed | 子平真詮 論用神成敗救應 | 食神生財→食格成 |
| MG-L3-JAE-SAENGGWAN | text_confirmed | 同上 | 財旺生官=美格, 身弱이면 破格(반례 포함) |
| MG-L3-GWAN-INSAENG | text_confirmed | 同上 | 官印雙全. '관인상생' 용어는 任氏曰 |
| MG-L3-SAL-INSAENG | text_confirmed | 滴天髓闡微(원문 구절) | 殺印相生. 殺強身弱 印綬化殺은 任氏曰 |
| MG-L3-SANGGWAN-GYEONGWAN | text_confirmed | 子平真詮 | 傷官見官=格忌, 財 통관 구응까지 |
| MG-L3-GUNGEOP-JAENGJAE | text_confirmed | 同上 | 財輕比重=財格敗. '群劫爭財'는 任氏曰 사례 |
| MG-L3-CHAIN | convention | - | |
| MG-L4-GYEOKGUK-CAND | text_confirmed | 子平真詮 論用神變化 | 본기 미투출 시 중기 투출이 작용. 세부 순서는 단순화 |
| MG-L4-GYEOKGUK-BONGI | location_confirmed | 同上 | '甲為本主'. 본기 중심 학파 자체는 구현상 병렬 대안 |
| MG-L4-SEONGPA | text_confirmed | 子平真詮 論用神成敗救應 | 격별 成/敗/救應 표를 직접 제시. **구현 표는 단순화**이며 동일하지 않음 |
| MG-L4-GEUKGUK-YONGSHIN | text_confirmed | 同上 | 用神專尋月令 |
| MG-L4-EOKBU-YONGSHIN | text_confirmed(주석) | 徐樂吾 평주 | 20세기 평주의 5분류 중 扶抑. 沈孝瞻 원문 아님 |
| MG-L4-JOHU-DIRECTION | text_confirmed | 滴天髓 寒暖論 | 한난 방향만. 窮通寶鑑 일간×월지 표는 미확인·미구현 |
| MG-L4-YONGSHIN-CONFLICT | convention | - | |
| MG-L5-LUCK-STEM | text_confirmed | 子平真詮 論行運 | 운 간을 원국 喜忌에 대조. **엔진이 이 rule_id 노드를 만들지 않음** |
| MG-L5-LUCK-BRANCH | text_confirmed | 同上 | 일반 원칙만 |
| MG-L5-STRUCTURE-DELTA / SEGMENT / COMPARE | convention | - | |

## 한계
- 원문/주석 구분은 libokang 페이지의 '沈氏原文說·徐樂吾評註' 표지와 滴天髓闡微의 〈原註〉·〈任氏曰〉 표지에 의존한 분류다. 판본 교감은 하지 않았다.
- 전사본 이용 조건은 확인하지 않았다. 저장소에는 ≤40자 발췌만 둔다.
- 성립/불성립 가상 명식(합성)은 JSON 의 `positive_case`/`negative_case` 에 있고, `tests/test_classical.py` 가 엔진 출력으로 재검증한다. 일부 사례 명식은 여러 규칙에 재사용된다.
