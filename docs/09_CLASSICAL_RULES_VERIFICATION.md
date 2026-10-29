# 고전 규칙 37개 원문 검증 결과 (P0, v6.6 갱신)

산출: `backend/golden/classical_verification.json`, `backend/golden/classical_differences.json`, 조회 API `app/mingli/classical.py`, 재실행 `python -m tools.verify_classical` · `python -m tools.build_classical_differences`(네트워크 필요), 문서 생성 `python -m tools.build_doc09`, 테스트 `tests/test_classical*.py`. 접근일 2026-10-29.
`rules.py` 는 이 작업에서 수정하지 않았다(상태 병합은 부모 작업의 `_merge_classical()` 이 JSON 을 읽어 반영).

## 상태 정의 (보수적)

| 상태 | 의미 |
|---|---|
| pending | 확인하지 못함 |
| location_confirmed | 출처 페이지에서 장·핵심어 위치만 확인. 구절이 규칙 내용을 직접 뒷받침하는지는 **판단하지 않음** (+ `content_gap` 으로 이유 기록) |
| text_confirmed | 사람이 구절을 읽고 `scope_note` 범위에서 규칙 내용에 대응함을 확인. 발췌(≤40자)가 페이지 텍스트에 그대로 있는지 스크립트가 재검증(없으면 자동 강등). `coverage=partial` 이면 일부 조건만 확인된 것이고 `unconfirmed_parts` 에 미확인 부분이 적혀 있다 |
| implementation_convention | 고전 주장 없음(구현자 규약) |

`text_confirmed` 는 '고전과 일치한다'가 아니라 '표시한 범위에서 원문이 뒷받침한다'이다. **승격 원칙**: 규칙의 *주된 정의*가 원문에 직접 대응하면 부분 확인이라도 coverage=partial 로 승격하고, 원문이 규칙을 **부정·보류·다른 기준으로 서술**하면(BONGI, HYUNG, PA, HAE) location_confirmed 로 남긴다.

## 결과 요약

| 상태 | 개수 |
|---|---|
| text_confirmed | 27 |
| location_confirmed | 4 |
| implementation_convention | 6 |
| pending | 0 |
| 합계 | 37 |

v6.5 → v6.6: text_confirmed 23 → 27, location_confirmed 8 → 4, implementation_convention 6 → 6. 그중 범위 한정(partial) text_confirmed: MG-L1-DEUKRYEONG-SEASON, MG-L2-HAP-HWA, MG-L2-BANGHAP, MG-L4-GYEOKGUK-BONGI.

**CLASSICAL_RULES_PENDING 은 해제되지 않는다**: location_confirmed 4개가 남아 있고, text_confirmed 도 범위 한정이다. 판본 교감(영인본 대조)은 **미수행**이다.

## 접속 실패한 출처

- `donglishuzhai.net/chapter/3721.html`(子平真詮 卷一·八), `m.donglishuzhai.net/chapter/3722.html`(卷一·九): 30초 연결 시간 초과(재시도 포함)로 열지 못함. 이 두 URL 에 대한 대조는 **미수행**이며, 같은 원문을 담은 `libokang.com` 子平真詮評註(원문 + 평주)로 대신 확인했다. 실패 기록: zp, zpc
- 窮通寶鑑·淵海子平은 열리지만 이 작업의 규칙을 text_confirmed 로 올릴 구절은 찾지 못했다.

## 위치만 확인되던 8개 규칙의 상세 조사 (v6.6)

| 규칙 | 결과 | 조사 내용 (원문이 말하는 조건 / 후대 주석 / 엔진 구현 / 일치·불일치) |
|---|---|---|
| MG-L1-DEUKRYEONG-BONGI | location_confirmed 유지 | 원문(滴天髓 月令論)은 '令星(月令에서 用事하는 人元)을 氣象·喜神(用神)이 얻으면 得令'이라 하며, 용사 일수(寅月 立春後 7일 戊 → 8~14일 丙 → 15일 後 甲)로 令星을 정한다. 評註(子平真詮 論十干得時不旺失時不弱)는 得令(秉令)과 強弱을 분리한다. 엔진은 '월지 본기가 일간의 비겁/인성이면 득령'(신강약식)이다. → 원문에 직접 대응하지 않아 승격하지 않음(MODERN_CONVENTION). |
| MG-L1-DEUKRYEONG-SEASON | location → text_confirmed(partial) | 徐樂吾 評註: '春木夏火秋金冬水為得時'(得時=旺, 比劫·印綬 通根 扶助=黨眾). 월령 오행==일간 오행인 경우는 일치. 월령이 일간을 '생'하는 경우도 득령 근거로 보는 엔진 확장은 확인 못함. 이전에 달았던 寒暖論 위치는 조후(한난) 구절이라 이 규칙의 근거가 아니었음. |
| MG-L2-HAP-HWA | location → text_confirmed(partial) + 구현 오류 2건 수정 | 沈孝瞻 論十干合而不合: 합 상대를 극하는 글자가 사이에 끼면 合而不敢合(有若無), 멀리 떨어지면 半合(길흉 영향 10분의 2~3), 合一留一·合官留煞는 無傷, 日干 자신의 合은 合去가 아님. 論外格用舍(從化): 化는 化神이 得時乘令·地支 局全이어야 함(丁壬化木은 亥卯未·寅卯辰 + 春月, 亥未月은 次等). 확인 못한 것: 쟁합·극신 천간 조건, 일간 합화 허용 여부. 엔진은 間隔을 보지 않았고 월령을 '같은/생하는 오행'으로만 판정해 辰·未·丑월을 놓쳤음 → 수정. |
| MG-L2-BANGHAP | location → text_confirmed(partial) | 滴天髓 方局論 원문 '方是方兮局是局，方要得方莫混局' + 任氏曰이 方을 寅卯辰·巳午未·申酉戌·亥子丑 4조로 나열. 沈孝瞻의 '會'는 申子辰(현대 삼합)이고 評註는 寅卯辰을 '三會'라 불러 용어가 문헌마다 다름. 2글자 부분 방합은 원문에 없음(엔진은 contested 기록만). |
| MG-L2-HYUNG | location_confirmed 유지 | 沈孝瞻: '刑者，三刑也，子卯巳申之類是也'(子卯·巳申을 예로 듦), '至於三刑取廡，姑且闕疑'(취의 보류). 任氏曰: 子卯一刑·寅巳申二刑·丑戌未三刑·自刑 분류를 소개한 뒤 '此皆俗謬，姑置之'. 원문이 규칙 내용을 긍정하지 않으므로 승격하지 않음. 자형 제외 프로필(no_self) 추가. |
| MG-L2-PA | location_confirmed 유지 | 三命通會 破煞(신살 맥락): '卯與午，丑與辰，子與酉，未與戌，皆相破。惟寅申巳亥原破，卻三合，故不取' → 4쌍만 취하고 寅亥·巳申은 취하지 않음. 任氏曰은 破 자체를 '不經，削之可也'라 함. 엔진 기본 프로필(modern_6)이 두 쌍을 포함해 원문과 충돌 → 승격하지 않음. sanmyeongtonghoe_4 프로필은 원문과 일치. |
| MG-L2-HAE | location_confirmed 유지 | 任氏曰(滴天髓闡微): '穿，即害也，六害由六合而來，沖我合神，故為之害' — 이 규칙으로 도출한 6쌍이 엔진 표와 같음(회귀 테스트). 그러나 같은 주석이 '害之義，尤為穿鑿'이라 비판하고, 예시에 '丑午寅亥'로 적어 도출(寅巳)과 표기가 어긋남. 滴天髓 본문에는 害 규정이 없음. 규칙을 긍정하는 근거가 아니므로 승격하지 않음. |
| MG-L4-GYEOKGUK-BONGI | location → text_confirmed(partial) | 沈孝瞻 論用神變化: '即以寅論，甲為本主…不透甲而透丙，則如知府不臨郡，而同知得以作主'. 본기=本主, 본기 불투출·중기 투출이면 중기가 作主(=투출 우선). 엔진의 '항상 본기' 병렬 대안은 원문이 아닌 학파 대안(SCHOOL_VARIANT)이며 원문과 일치하는 쪽은 MG-L4-GYEOKGUK-CAND. |

공통: 원문 발췌는 `additional_excerpts`(JSON) 에 ≤40자로 저장, 모두 캐시 페이지에서 그대로 재확인(`verified_in_page`). 학파별 적용·예외는 각 항목 `school_conditions`.

## 원문·구현 차이 13건 분류

| 규칙 | 분류 | 보조 분류 | 요약 | 처리 | 상태 |
|---|---|---|---|---|---|
| MG-L2-PA | **SCHOOL_VARIANT** | TRANSLATION_AMBIGUITY | 三命通會는 子酉·丑辰·卯午·未戌만 破로 취하고 寅申巳亥(寅亥·巳申)는 原破이나 合이므로 취하지 않는다. 任氏曰은 破 자체를 삭제 가능(不經)이라 한다. 엔진 기본 프로필은 6쌍 전부를 破로 기록.… | 학파 프로필로 분리됨(기존). sanmyeongtonghoe_4 만 원문과 일치. 기본값 modern_6 은 현대 통용 표이며 고전 원문과 같다고 표시하지 않는다(반대 근거에 '원문 대조(conflict)' 자동 부… | resolved |
| MG-L2-HYUNG | **SCHOOL_VARIANT** | SOURCE_UNVERIFIED | 沈孝瞻은 刑을 三刑('子卯巳申之類')으로 정의하되 취의는 闕疑로 두고, 任氏曰은 刑·自刑을 俗謬로 배척한다. 엔진은 子卯·寅巳申·丑戌未·자형을 모두 '존재 후보'로만 기록(작용 미확정).… | 자형(辰午酉亥)을 hyung_profile 로 분리: common(기본, 자형 기록) / no_self(任氏曰에 따라 제외). 任氏曰의 刑 전면 배척은 규칙 자체를 지우는 것이라 프로필로 만들지 않음(SOURCE_U… | resolved |
| MG-L2-HAE | **TRANSLATION_AMBIGUITY** | SCHOOL_VARIANT | 任氏曰은 害(穿)를 '六合의 상대를 沖하는 글자'로 정의한다. 이 규칙으로 도출한 6쌍은 엔진 표(子未·丑午·寅巳·卯辰·申亥·酉戌)와 정확히 같다(회귀 테스트로 확인). 다만 같은 주석의 예시 문구 '丑午寅亥'는 도출 결과(寅巳)와 어긋나 판본·표기 모호성이 있고, 주… | 구현 오류 없음(도출 일치). 예시 표기 차이는 TRANSLATION_AMBIGUITY 로 기록하고 표는 유지. 害 취의 비판은 반대 근거로 자동 부착. 원문(滴天髓 본문)에는 害 규정이 없다.… | documented |
| MG-L2-HAP-HWA | **IMPLEMENTATION_BUG** | MODERN_CONVENTION, SOURCE_UNVERIFIED | 원문 조건 중 구현에서 빠지거나 과하게 엄격했던 두 가지를 발견해 수정: ① 間隔(합 상대를 극하는 글자가 사이에 끼면 合而不敢合) 누락 ② 월령 조건이 '화신 오행과 같은/생하는 월지'로만 판정되어 辰·未·丑 같은 계절 월(木의 辰, 火의 未, 水의 丑)을 놓침(原文… | 수정 완료. 천간합 노드와 합화 후보에 '사이 글자가 합 상대를 극하지 않음(間隔)' 조건 추가(극하면 '합 존재하나 間隔으로 합이 안 됨'), 월령 조건을 得時(계절)/次等(생하는 월·庫月)로 확장. 쟁합·극신 조… | resolved |
| MG-L2-BANGHAP | **TRANSLATION_AMBIGUITY** | MODERN_CONVENTION | 용어가 문헌마다 다르다: 滴天髓는 '方(寅卯辰)'과 '局(亥卯未)'을 구분하고, 任氏曰은 方을 寅卯辰·巳午未·申酉戌·亥子丑 4조로 나열한다. 沈孝瞻의 '會'는 申子辰(현대 삼합)을 가리키고 評註는 寅卯辰을 '三會'라 부른다. 2글자 부분 방합은 원문에 없다.… | 엔진 동작은 원문(3글자 方)과 일치. 용어 차이는 문서화. 부분 방합은 '인정 여부 논쟁'으로만 기록하고 존재 확정에 쓰지 않음(현대 확장).… | documented |
| MG-L2-SAMHAP | **TRANSLATION_AMBIGUITY** | MODERN_CONVENTION | 沈孝瞻 원문은 申子辰을 '三會'라 부른다(현대 용어 '삼합'). 반합·공합의 구분과 인정 범위는 현대 확장이다.… | 용어 매핑을 문서화하고 반합·공합은 MODERN_CONVENTION 으로 표시. 구현 변경 없음.… | documented |
| MG-L2-COMPETITION | **SCHOOL_VARIANT** | - | 沈孝瞻은 합이 충·형을 푼다는 입장(합 우선)이면서, 합신이 다른 局에 끌려가면 풀지 못한다는 단서를 둔다. 엔진은 합 우선/충 우선/인접·월령 우선을 '논쟁'으로 병렬 기록하며 어느 쪽도 확정하지 않는다.… | 학파 차이를 병렬 기록하는 현행 처리를 유지. '합신이 다른 局에 끌려가는 경우'는 미구현이며 기록만 남김(구현 확장 후보).… | documented |
| MG-L1-DEUKRYEONG-BONGI | **MODERN_CONVENTION** | - | 원문의 得令은 月令에서 用事하는 人元(令星)을 氣象·喜神(用神)이 얻는가의 문제이고, 評註도 得令(秉令)과 強弱을 분리한다. '월지 본기가 일간의 비겁/인성이면 득령'은 후대 신강약식 정의다.… | 고전 직접 주장으로 표시하지 않는다(location_confirmed 유지, content_gap 기록). 학파 병렬 평가는 유지.… | documented |
| MG-L1-DEUKRYEONG-SEASON | **MODERN_CONVENTION** | - | 評註는 春木夏火秋金冬水를 得時(旺)라 하므로 '월령 오행 == 일간 오행'은 원문 계통과 일치한다. 엔진이 추가로 '월령이 일간을 생해도 득령 근거'로 보는 확장은 근거를 확인하지 못했다.… | 핵심(같은 오행)은 text_confirmed(범위 한정), 생 확장은 MODERN_CONVENTION 으로 표시(coverage=partial).… | documented |
| MG-L4-GYEOKGUK-BONGI | **SCHOOL_VARIANT** | - | 원문은 본기를 本主로 하되 본기가 투출하지 않고 중기가 투출하면 중기가 作主한다(투출 우선). 엔진의 '항상 본기로 격 이름' 병렬 대안은 원문이 아닌 학파 대안이다.… | 현행 병렬 기록 유지. 원문과 일치하는 쪽은 투출 우선(MG-L4-GYEOKGUK-CAND).… | documented |
| MG-L4-SEONGPA | **MODERN_CONVENTION** | SOURCE_UNVERIFIED | 원문 成敗救應 절의 조건표를 구현자가 단순화했다. 확인된 생략: 傷官見官의 財 통관 구응(원문 있음), 刑沖의 會合 해소, 合煞 구응, 建祿·月劫·陽刃 격의 성패. 세부 위치(地位配置) 판단도 없음.… | 동작 변경 없음(기존 테스트가 현 표를 기준으로 함). 생략 항목은 known_gaps 로 기록해 상담문·UI 에서 '구현자 단순화'로 표시. 재물 통관 구응 추가는 후속 과제(제안).… | documented |
| MG-L4-EOKBU-YONGSHIN | **SCHOOL_VARIANT** | - | 억부론은 滴天髓 衰旺論('旺則宜洩宜傷，衰則喜幫喜助')과 徐樂吾 評註의 扶抑 분류에 있는 학파 입장이다. 沈孝瞻의 격국론(月令 用神)과 묻는 질문이 다르다. 따라서 '沈孝瞻 원문이 아님'만으로 후대 개념(later_concept)이라고 단정할 수 없다.… | SCHOOL_VARIANT 로 재분류(제안: rules.py ENGINE_VS_CLASSICAL kind later_concept → school_variant). 강약 후보 판정 규칙 자체는 구현 규약.… | documented |
| MG-L1-TONGGEUN | **SCHOOL_VARIANT** | MODERN_CONVENTION | 沈孝瞻은 通根의 重·輕을 十二運으로 가른다: 長生·祿·旺=根之重, 墓庫·餘氣=根之輕, 陰干 長生은 明根(餘氣 정도). 엔진 기본값은 지장간 위치(본기=강·중기=중·여기=약)로 등급을 매긴다. 예: 甲이 亥(甲은 중기)에 있어도 원문은 長生=重根.… | 신규 tonggeun 프로필 twelve_stage 로 분리(analyze_layer1(tonggeun_profile=...)). 기본값 position_role 은 구현 규약으로 표시 유지.… | resolved |

분류 합계: SCHOOL_VARIANT 6, TRANSLATION_AMBIGUITY 3, IMPLEMENTATION_BUG 1, MODERN_CONVENTION 3. IMPLEMENTATION_BUG 는 수정하고 회귀 테스트를 추가했다. SCHOOL_VARIANT 는 프로필로 분리했고, MODERN_CONVENTION 은 고전의 직접 주장으로 표시하지 않는다.

### 수정·추가한 코드

- **MG-L2-HAP-HWA**: layer2.py: stem_gap()·month_tier() 추가, 천간합/합화 후보에 '사이 글자가 합 상대를 극하지 않음(間隔)' 조건, 월령 득시/次等 판정
- **MG-L2-HYUNG**: layer2.py: hyung_profile=common|no_self (자형 제외)
- **MG-L1-TONGGEUN**: layer1.py: tonggeun_profile=position_role|twelve_stage (沈孝瞻 十二運 기준)
- **MG-L2-PA**: (기존) pa_profile=modern_6|sanmyeongtonghoe_4
- 회귀 테스트: `tests/test_classical_regressions.py` (間隔, 월령 득시/次等, 害 도출 일치, 자형 프로필, 십이운성 통근). 분류 검증: `tests/test_classical_diffs.py`.
- 기본 프로필은 모두 기존 동작을 유지한다(`pa=modern_6`, `hyung=common`, `tonggeun=position_role`). `analyze_structure(profiles=...)` 로 새 프로필을 고르려면 `mingli/__init__.py` 의 전달 코드가 필요하다(부모 작업에 제안 diff 전달).

## 규칙별 상태

| 규칙 | 상태 | coverage | 근거 출처 | 비고(범위·한계) |
|---|---|---|---|---|
| MG-L1-WOLRYEONG | text_confirmed | scoped | 滴天髓 · 月令=提綱 개념 확인 | 月令=提綱 개념 확인. 이 구현의 '월령 사실 기록' 범위와 일치. |
| MG-L1-DEUKRYEONG-BONGI | location_confirmed | - | 滴天髓 · 月令論(令星得令) | 핵심어가 해당 출처 페이지에 존재함(위치 확인). 구절이 규칙 내용을 직접 뒷받침하는지는 판단하지 않음. |
| MG-L1-DEUKRYEONG-SEASON | text_confirmed | partial | 子平真詮評註(徐樂吾 평주 포함) · 論十干得時不旺失時不弱(평주) | 徐樂吾 평주(논십간득시불왕실시불약): 春木夏火秋金冬水=得時(월령 오행이 일간과 같음). 단 得時=旺일 뿐 強은 아님. 엔진이 추가로 '월령이 일간을 생해도 득령 근거'로 보는 부분은 확인 못함. |
| MG-L1-HIDDEN-ROLE | text_confirmed | scoped | 滴天髓 · 寅月 한 예(戊→丙→甲, 즉 여기→중기→본기 순)만 확 | 寅月 한 예(戊→丙→甲, 즉 여기→중기→본기 순)만 확인. 12지 전체 표와 사령 일수는 이 구현이 사용하지 않으며 확인하지 않음. |
| MG-L1-TONGGEUN | text_confirmed | scoped | 滴天髓闡微(任鐵樵 注) · 任氏曰(주석) | 任氏曰(주석). 천간 木에 지지 寅卯=통근. 지장간 동일글자 엄격/관대 구분, 강·중·약 등급은 구현 규약. 沈孝瞻 원문은 長生·祿·旺·庫를 有根으로 봄(十二運 기준, 미구현). |
| MG-L1-TUGAN | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 투출 여부가 작용하는 글자를 바꾼다는 내용 확인 | 투출 여부가 작용하는 글자를 바꾼다는 내용 확인. 연·월·시간만 보고 일간 제외하는 세부 규칙은 구현 규약. |
| MG-L1-SUPPORT-ORDINAL | implementation_convention | - | -  | 구현자 규약. 고전이 이렇게 말한다고 주장하지 않는다. |
| MG-L2-STEM-HAP | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 甲己土·乙庚金·丙辛水·丁壬木·戊癸火 5쌍 확인(同節 前 | 甲己土·乙庚金·丙辛水·丁壬木·戊癸火 5쌍 확인(同節 前문 甲己 포함). |
| MG-L2-HAP-HWA | text_confirmed | partial | 子平真詮評註(徐樂吾 평주 포함) · 論十干合而不合 | 沈孝瞻 論十干合而不合: 사이에 합 상대를 극하는 글자가 끼면 합이 안 됨(間隔), 멀리 떨어지면 半合. 論外格用舍(從化): 化는 得時乘令·四支局全이 요건(additional_excerpts). 쟁합 |
| MG-L2-BRANCH-YUKHAP | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 六合 개념과 대표쌍(子丑)만 확인 | 六合 개념과 대표쌍(子丑)만 확인. 6쌍 전체 나열은 이 구절에 없음. |
| MG-L2-SAMHAP | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 원문은 申子辰을 '三會'로 부름(평주는 三合會局으로 풀 | 원문은 申子辰을 '三會'로 부름(평주는 三合會局으로 풀이). 용어 차이 있음. 반합·공합의 인정 범위는 확인하지 않음. |
| MG-L2-BANGHAP | text_confirmed | partial | 滴天髓 · 滴天髓 方局論 | 滴天髓 方局論 원문 구절: 方(방합)과 局(삼합)을 구분하고 섞지 말라. 方의 구성(寅卯辰 등 4조)은 任氏曰(commentary_excerpt)이 나열. 2글자 방합(부분)은 원문에 없음(엔진은 |
| MG-L2-CHUNG | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 六沖 개념과 대표쌍(子午·卯酉)만 확인 | 六沖 개념과 대표쌍(子午·卯酉)만 확인. |
| MG-L2-HYUNG | location_confirmed | - | 子平真詮評註(徐樂吾 평주 포함) · 論刑沖會合解法 | 핵심어가 해당 출처 페이지에 존재함(위치 확인). 구절이 규칙 내용을 직접 뒷받침하는지는 판단하지 않음. |
| MG-L2-PA | location_confirmed | - | 三命通會 卷三 · 三命通會 卷三 破煞 | 핵심어가 해당 출처 페이지에 존재함(위치 확인). 구절이 규칙 내용을 직접 뒷받침하는지는 판단하지 않음. |
| MG-L2-HAE | location_confirmed | - | 滴天髓闡微(任鐵樵 注) · 滴天髓闡微(任氏曰) 刑沖害論 | 핵심어가 해당 출처 페이지에 존재함(위치 확인). 구절이 규칙 내용을 직접 뒷받침하는지는 판단하지 않음. |
| MG-L2-GOGO | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 원문은 '庫는 반드시 沖해야 연다'는 속설을 부정하고  | 원문은 '庫는 반드시 沖해야 연다'는 속설을 부정하고 沖이 오히려 印을 해칠 수 있다고 함 → 개고 성립이 학파 논쟁이라는 본 규칙의 처리와 부합. 辰=水庫 등 庫 대응표 자체는 별도 구절. |
| MG-L2-COMPETITION | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 원문은 합이 충·형을 푼다는 입장(합 우선설) | 원문은 합이 충·형을 푼다는 입장(합 우선설). 본 규칙의 '합 우선/충 우선/인접·월령 우선' 중 합 우선설만 직접 뒷받침. 나머지 학설은 확인하지 않음. |
| MG-L3-SIKSANG-SAENGJAE | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 食神生財→食格成 | 食神生財→食格成. 傷官生財→傷官格成도 같은 절에 있음. |
| MG-L3-JAE-SAENGGWAN | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 財旺生官=美格이나 身弱이면 破格(반례)이라는 점까지 확 | 財旺生官=美格이나 身弱이면 破格(반례)이라는 점까지 확인. |
| MG-L3-GWAN-INSAENG | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 官印雙全이 印格成의 한 형태로 나옴 | 官印雙全이 印格成의 한 형태로 나옴. '관인상생'이라는 용어 자체는 任氏曰(滴天髓闡微)에 있음. |
| MG-L3-SAL-INSAENG | text_confirmed | scoped | 滴天髓闡微(任鐵樵 注) · 滴天髓 원문 구절(原註 앞) | 滴天髓 원문 구절(原註 앞). 殺印相生 용어와 사례. 殺強身弱에 印綬化殺은 任氏曰. |
| MG-L3-SANGGWAN-GYEONGWAN | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 상관견관=格忌이며 財가 통관하면 해소된다는 구응까지 확 | 상관견관=格忌이며 財가 통관하면 해소된다는 구응까지 확인(본 규칙의 반대 근거 처리와 부합). |
| MG-L3-GUNGEOP-JAENGJAE | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 財輕比重=財格敗 확인 | 財輕比重=財格敗 확인. '群劫爭財' 용어는 任氏曰 사례 구절(commentary_excerpt)에 있음. 구응(食傷으로 化)은 救應 절 '財逢劫而透食以化之'. |
| MG-L3-CHAIN | implementation_convention | - | -  | 구현자 규약. 고전이 이렇게 말한다고 주장하지 않는다. |
| MG-L4-GYEOKGUK-CAND | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 본기 미투출 시 중기 투출이 용신이 되는 '用神變化'  | 본기 미투출 시 중기 투출이 용신이 되는 '用神變化' 확인. 투출 우선 순서의 모든 세부 규칙은 구현 단순화. |
| MG-L4-GYEOKGUK-BONGI | text_confirmed | partial | 子平真詮評註(徐樂吾 평주 포함) · 論用神變化 | 沈孝瞻 論用神變化: 본기(甲)=本主. 단 본기 불투출·중기 투출이면 중기가 作主(additional_excerpts). 엔진의 '항상 본기로 격 이름' 대안은 원문이 아니라 병렬 대안이며 원문 규칙 |
| MG-L4-SEONGPA | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 沈孝瞻 成敗救應 절이 격별 成/敗/救應 조건표를 직접  | 沈孝瞻 成敗救應 절이 격별 成/敗/救應 조건표를 직접 제시. 구현 조건표는 이를 단순화(예: 刑沖破害·合煞 등 세부 생략)한 것으로 원문과 동일하지 않음. |
| MG-L4-GEUKGUK-YONGSHIN | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 격국용신=월령에서 구함 확인 | 격국용신=월령에서 구함 확인. 억부·조후용신과 분리한다는 점은 후대 구분. |
| MG-L4-EOKBU-YONGSHIN | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 徐樂吾 평주의 용신 5분류 중 (一)扶抑 | 徐樂吾 평주의 용신 5분류 중 (一)扶抑. 沈孝瞻 원문이 아니라 20세기 평주. 강/약 후보 판정 규칙은 구현 규약. |
| MG-L4-JOHU-DIRECTION | text_confirmed | scoped | 滴天髓 · 寒暖論 원문 | 寒暖論 원문. 한난 방향 개념 확인. 窮通寶鑑 일간×월지 개별 표는 확인·구현하지 않음. 평주(徐樂吾)의 調候 분류도 존재. |
| MG-L4-YONGSHIN-CONFLICT | implementation_convention | - | -  | 구현자 규약. 고전이 이렇게 말한다고 주장하지 않는다. |
| MG-L5-LUCK-STEM | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 운의 간을 원국 喜忌에 맞춰 본다는 내용 확인 | 운의 간을 원국 喜忌에 맞춰 본다는 내용 확인. 주의: 현재 엔진은 이 rule_id 를 쓰는 claim 노드를 만들지 않음(규칙만 등록). |
| MG-L5-LUCK-BRANCH | text_confirmed | scoped | 子平真詮評註(徐樂吾 평주 포함) · 운 글자를 원국 간지와 함께 본다는 일반 원칙 확인 | 운 글자를 원국 간지와 함께 본다는 일반 원칙 확인. 합충 세부 분류는 Layer 2 규칙 참조. |
| MG-L5-STRUCTURE-DELTA | implementation_convention | - | -  | 구현자 규약. 고전이 이렇게 말한다고 주장하지 않는다. |
| MG-L5-SEGMENT | implementation_convention | - | -  | 구현자 규약. 고전이 이렇게 말한다고 주장하지 않는다. |
| MG-L5-COMPARE | implementation_convention | - | -  | 구현자 규약. 고전이 이렇게 말한다고 주장하지 않는다. |

## 한계

- 원문/주석 구분은 libokang 페이지의 '沈氏原文說·徐樂吾評註' 표지와 滴天髓闡微의 〈原註〉·〈任氏曰〉 표지에 의존한 분류다. 滴天髓輯要(wikisource)는 원문 게송과 주석 문장이 표지 없이 섞여 있어 `annotation` 으로 표기했다. **판본 교감은 미수행**이다.
- 전사본 이용 조건은 확인하지 않았다. 저장소에는 ≤40자 발췌만 둔다.
- 성립/불성립 가상 명식(합성)은 JSON 의 `positive_case`/`negative_case` 에 있고 `tests/test_classical.py` 가 엔진 출력으로 재검증한다. 일부 명식은 여러 규칙에 재사용된다.
- `MG-L5-LUCK-STEM` 은 규칙만 등록되어 있고 엔진이 해당 rule_id 노드를 만들지 않는다.
