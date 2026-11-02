# v9.1 고전 규칙 검증 현황 (자동 생성)

`python -m tools.classical_audit --write docs/24_V91_CLASSICAL_AUDIT.md` 로 다시 만든다. 이 문서는 저장소에 이미 있는 검증 기록만 정리하며, **새 원문을 내려받거나 재배포하지 않았다.**

## 요약

- 전체 규칙 37개 — 원문 24, 후대 주석 3, 현대적 해석 0, 구현자 규약 6, 미확인 4
- 원문 대조 전(위치만 확인): 4개, pending: 0개 → 고전 대조가 끝나지 않은 규칙 4개
- 일부 조건만 확인된 규칙(범위 한정): 4개 — MG-L1-DEUKRYEONG-SEASON, MG-L2-BANGHAP, MG-L2-HAP-HWA, MG-L4-GYEOKGUK-BONGI
- 구현자 규약(고전 주장 없음): 6개 — 고전의 결론으로 쓰지 않는다.

‘원문 확인’은 고전과 일치한다는 뜻이 아니라 **표시한 범위에서 원문이 뒷받침한다**는 뜻이다. 외부 전사본은 판본 교감 전이며 짧은 발췌만 저장한다.

## 구분 정의

| 구분 | 뜻 |
|---|---|
| 원문 | 원전 구절(짧은 발췌)이 규칙 내용에 대응함을 사람이 확인 |
| 후대 주석 | 원문이 아니라 주석자(예: 任鐵樵, 徐樂吾)의 해설이 근거 |
| 현대적 해석 | 고전에 없는 현대 통용·확장(예: 반합·공합 범위) |
| 구현자 규약 | 구현 편의·단순화. 고전의 결론이 아님 |
| 미확인 | 위치만 확인했거나 확인 못함 |

## 우선 정리할 항목 (미확인·일부 확인·알려진 누락)

| 규칙 | 구분 | 상태 | 확인 못한 부분 | 필요한 자료 |
|---|---|---|---|---|
| MG-L1-DEUKRYEONG-BONGI | 미확인 | location_confirmed | 현대적 확장 포함; 위치(키워드)만 확인 — 구절이 규칙을 뒷받침하는지 미판단 | 滴天髓 · 月令論(令星得令) — 판본 확인 필요 |
| MG-L1-DEUKRYEONG-SEASON | 후대 주석 | text_confirmed | 월령 오행이 일간을 '생'하는 경우도 득령 근거로 보는 확장; 일부 조건만 확인(범위 한정); 현대적 확장 포함 | 子平真詮評註(徐樂吾 평주 포함) · 論十干得時不旺失時不弱(평주) — 판본 확인 필요 |
| MG-L2-HAP-HWA | 원문 | text_confirmed | 쟁합·투합 경쟁 없음 조건; 화신을 극하는 천간 없음 조건; 일간 합화 허용 여부(학파 논쟁); 일부 조건만 확인(범위 한정); 구현 오류 수정 이력 | 子平真詮評註(徐樂吾 평주 포함) · 論十干合而不合 — 판본 확인 필요 |
| MG-L2-BANGHAP | 원문 | text_confirmed | 2글자 부분 방합의 인정 여부(원문 없음 — 엔진은 contested 로만 기록); 일부 조건만 확인(범위 한정) | 滴天髓 · 滴天髓 方局論 — 판본 확인 필요 |
| MG-L2-HYUNG | 미확인 | location_confirmed | 학파 차이; 위치(키워드)만 확인 — 구절이 규칙을 뒷받침하는지 미판단 | 子平真詮評註(徐樂吾 평주 포함) · 論刑沖會合解法 — 판본 확인 필요 |
| MG-L2-PA | 미확인 | location_confirmed | 寅亥·巳申 포함(원문은 취하지 않음); 학파 차이; 위치(키워드)만 확인 — 구절이 규칙을 뒷받침하는지 미판단 | 三命通會 卷三 · 三命通會 卷三 破煞 — 판본 확인 필요 |
| MG-L2-HAE | 미확인 | location_confirmed | 위치(키워드)만 확인 — 구절이 규칙을 뒷받침하는지 미판단 | 滴天髓闡微(任鐵樵 注) · 滴天髓闡微(任氏曰) 刑沖害論 — 판본 확인 필요 |
| MG-L4-GYEOKGUK-BONGI | 원문 | text_confirmed | 투출과 무관하게 항상 본기로 격 이름을 짓는 병렬 대안; 일부 조건만 확인(범위 한정); 학파 차이 | 子平真詮評註(徐樂吾 평주 포함) · 論用神變化 — 판본 확인 필요 |
| MG-L4-SEONGPA | 원문 | text_confirmed | 傷官見官 + 財 통관 구응 누락(정관격·상관격); 刑沖 會合 해소 구응 누락; 合煞 구응 누락; 建祿·月劫·陽刃 격 성패 미구현; 현대적 확장 포함 | 子平真詮評註(徐樂吾 평주 포함) · 沈孝瞻 成敗救應 절이 격별 成/敗/救應 조건표를 직접  — 판본 확인 필요 |

## 전체 규칙

| 규칙 | 구분 | 상태 | 차이 분류 | 출처 |
|---|---|---|---|---|
| MG-L1-WOLRYEONG | 원문 | text_confirmed | - | 滴天髓 |
| MG-L1-DEUKRYEONG-BONGI | 미확인 | location_confirmed | MODERN_CONVENTION | 滴天髓 |
| MG-L1-DEUKRYEONG-SEASON | 후대 주석 | text_confirmed | MODERN_CONVENTION | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L1-HIDDEN-ROLE | 원문 | text_confirmed | - | 滴天髓 |
| MG-L1-TONGGEUN | 후대 주석 | text_confirmed | SCHOOL_VARIANT | 滴天髓闡微(任鐵樵 注) |
| MG-L1-TUGAN | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L1-SUPPORT-ORDINAL | 구현자 규약 | implementation_convention | - | - |
| MG-L2-STEM-HAP | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L2-HAP-HWA | 원문 | text_confirmed | IMPLEMENTATION_BUG | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L2-BRANCH-YUKHAP | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L2-SAMHAP | 원문 | text_confirmed | TRANSLATION_AMBIGUITY | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L2-BANGHAP | 원문 | text_confirmed | TRANSLATION_AMBIGUITY | 滴天髓 |
| MG-L2-CHUNG | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L2-HYUNG | 미확인 | location_confirmed | SCHOOL_VARIANT | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L2-PA | 미확인 | location_confirmed | SCHOOL_VARIANT | 三命通會 卷三 |
| MG-L2-HAE | 미확인 | location_confirmed | TRANSLATION_AMBIGUITY | 滴天髓闡微(任鐵樵 注) |
| MG-L2-GOGO | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L2-COMPETITION | 원문 | text_confirmed | SCHOOL_VARIANT | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L3-SIKSANG-SAENGJAE | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L3-JAE-SAENGGWAN | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L3-GWAN-INSAENG | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L3-SAL-INSAENG | 원문 | text_confirmed | - | 滴天髓闡微(任鐵樵 注) |
| MG-L3-SANGGWAN-GYEONGWAN | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L3-GUNGEOP-JAENGJAE | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L3-CHAIN | 구현자 규약 | implementation_convention | - | - |
| MG-L4-GYEOKGUK-CAND | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L4-GYEOKGUK-BONGI | 원문 | text_confirmed | SCHOOL_VARIANT | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L4-SEONGPA | 원문 | text_confirmed | MODERN_CONVENTION | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L4-GEUKGUK-YONGSHIN | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L4-EOKBU-YONGSHIN | 후대 주석 | text_confirmed | SCHOOL_VARIANT | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L4-JOHU-DIRECTION | 원문 | text_confirmed | - | 滴天髓 |
| MG-L4-YONGSHIN-CONFLICT | 구현자 규약 | implementation_convention | - | - |
| MG-L5-LUCK-STEM | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L5-LUCK-BRANCH | 원문 | text_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) |
| MG-L5-STRUCTURE-DELTA | 구현자 규약 | implementation_convention | - | - |
| MG-L5-SEGMENT | 구현자 규약 | implementation_convention | - | - |
| MG-L5-COMPARE | 구현자 규약 | implementation_convention | - | - |

## 출처 작품과 판본 확인이 필요한 항목

- **三命通會 卷三**: 1개 규칙 — 현재 근거는 외부 전사본(판본 교감 전). 어느 판본인지, 평주 부분(徐樂吾 평주, 任鐵樵 注)이 원문과 구분되어 인용되는지 확인해야 한다.
- **子平真詮評註(徐樂吾 평주 포함)**: 22개 규칙 — 현재 근거는 외부 전사본(판본 교감 전). 어느 판본인지, 평주 부분(徐樂吾 평주, 任鐵樵 注)이 원문과 구분되어 인용되는지 확인해야 한다.
- **滴天髓**: 5개 규칙 — 현재 근거는 외부 전사본(판본 교감 전). 어느 판본인지, 평주 부분(徐樂吾 평주, 任鐵樵 注)이 원문과 구분되어 인용되는지 확인해야 한다.
- **滴天髓闡微(任鐵樵 注)**: 3개 규칙 — 현재 근거는 외부 전사본(판본 교감 전). 어느 판본인지, 평주 부분(徐樂吾 평주, 任鐵樵 注)이 원문과 구분되어 인용되는지 확인해야 한다.

- **궁통보감(窮通寶鑑/欄江網)**: 현재 규칙 레지스트리에 근거로 올라 있지 않다. 일간 10개 × 월 12개 조후 서술을 쓰려면 판본(清 余春台 편 등)과 사용 권한을 먼저 확인한 뒤 별도 규칙으로 등록해야 한다. 지금은 조후를 구현자 규약 수준으로만 쓴다고 보아야 한다.

## 자료 접근 실패 기록

- zp: 접속 실패(시간 초과)
- zpc: 접속 실패(시간 초과)

## 자료 사용 원칙

- 사용 권한이 확인되지 않은 자료는 수집·재배포하지 않는다. 한글 번역본은 저작권을 확인하기 전에는 인용하지 않는다.
- 원문(한문 원전)도 전사본의 이용 조건을 확인한 뒤에만 짧은 발췌를 저장한다. 전문 복제는 하지 않는다.
- 이 상태에서 ‘고전 검증 완료’라고 표시하지 않는다.
