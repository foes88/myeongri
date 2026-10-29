"""docs/09_CLASSICAL_RULES_VERIFICATION.md 를 golden 결과에서 생성한다(수치가 문서와 JSON 에서 어긋나지 않게). 실행: python -m tools.build_doc09"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V = json.loads((ROOT / "backend/golden/classical_verification.json").read_text(encoding="utf-8"))
DF = json.loads((ROOT / "backend/golden/classical_differences.json").read_text(encoding="utf-8"))["differences"]
R = V["rules"]
cnt = Counter(e["status"] for e in R.values())
partial = [k for k, e in R.items() if e["status"] == "text_confirmed" and e.get("coverage") == "partial"]

EIGHT = [
    ("MG-L1-DEUKRYEONG-BONGI", "location_confirmed 유지",
     "원문(滴天髓 月令論)은 '令星(月令에서 用事하는 人元)을 氣象·喜神(用神)이 얻으면 得令'이라 하며, 용사 일수(寅月 立春後 7일 戊 → 8~14일 丙 → 15일 後 甲)로 令星을 정한다. 評註(子平真詮 論十干得時不旺失時不弱)는 得令(秉令)과 強弱을 분리한다. 엔진은 '월지 본기가 일간의 비겁/인성이면 득령'(신강약식)이다. → 원문에 직접 대응하지 않아 승격하지 않음(MODERN_CONVENTION)."),
    ("MG-L1-DEUKRYEONG-SEASON", "location → text_confirmed(partial)",
     "徐樂吾 評註: '春木夏火秋金冬水為得時'(得時=旺, 比劫·印綬 通根 扶助=黨眾). 월령 오행==일간 오행인 경우는 일치. 월령이 일간을 '생'하는 경우도 득령 근거로 보는 엔진 확장은 확인 못함. 이전에 달았던 寒暖論 위치는 조후(한난) 구절이라 이 규칙의 근거가 아니었음."),
    ("MG-L2-HAP-HWA", "location → text_confirmed(partial) + 구현 오류 2건 수정",
     "沈孝瞻 論十干合而不合: 합 상대를 극하는 글자가 사이에 끼면 合而不敢合(有若無), 멀리 떨어지면 半合(길흉 영향 10분의 2~3), 合一留一·合官留煞는 無傷, 日干 자신의 合은 合去가 아님. 論外格用舍(從化): 化는 化神이 得時乘令·地支 局全이어야 함(丁壬化木은 亥卯未·寅卯辰 + 春月, 亥未月은 次等). 확인 못한 것: 쟁합·극신 천간 조건, 일간 합화 허용 여부. 엔진은 間隔을 보지 않았고 월령을 '같은/생하는 오행'으로만 판정해 辰·未·丑월을 놓쳤음 → 수정."),
    ("MG-L2-BANGHAP", "location → text_confirmed(partial)",
     "滴天髓 方局論 원문 '方是方兮局是局，方要得方莫混局' + 任氏曰이 方을 寅卯辰·巳午未·申酉戌·亥子丑 4조로 나열. 沈孝瞻의 '會'는 申子辰(현대 삼합)이고 評註는 寅卯辰을 '三會'라 불러 용어가 문헌마다 다름. 2글자 부분 방합은 원문에 없음(엔진은 contested 기록만)."),
    ("MG-L2-HYUNG", "location_confirmed 유지",
     "沈孝瞻: '刑者，三刑也，子卯巳申之類是也'(子卯·巳申을 예로 듦), '至於三刑取廡，姑且闕疑'(취의 보류). 任氏曰: 子卯一刑·寅巳申二刑·丑戌未三刑·自刑 분류를 소개한 뒤 '此皆俗謬，姑置之'. 원문이 규칙 내용을 긍정하지 않으므로 승격하지 않음. 자형 제외 프로필(no_self) 추가."),
    ("MG-L2-PA", "location_confirmed 유지",
     "三命通會 破煞(신살 맥락): '卯與午，丑與辰，子與酉，未與戌，皆相破。惟寅申巳亥原破，卻三合，故不取' → 4쌍만 취하고 寅亥·巳申은 취하지 않음. 任氏曰은 破 자체를 '不經，削之可也'라 함. 엔진 기본 프로필(modern_6)이 두 쌍을 포함해 원문과 충돌 → 승격하지 않음. sanmyeongtonghoe_4 프로필은 원문과 일치."),
    ("MG-L2-HAE", "location_confirmed 유지",
     "任氏曰(滴天髓闡微): '穿，即害也，六害由六合而來，沖我合神，故為之害' — 이 규칙으로 도출한 6쌍이 엔진 표와 같음(회귀 테스트). 그러나 같은 주석이 '害之義，尤為穿鑿'이라 비판하고, 예시에 '丑午寅亥'로 적어 도출(寅巳)과 표기가 어긋남. 滴天髓 본문에는 害 규정이 없음. 규칙을 긍정하는 근거가 아니므로 승격하지 않음."),
    ("MG-L4-GYEOKGUK-BONGI", "location → text_confirmed(partial)",
     "沈孝瞻 論用神變化: '即以寅論，甲為本主…不透甲而透丙，則如知府不臨郡，而同知得以作主'. 본기=本主, 본기 불투출·중기 투출이면 중기가 作主(=투출 우선). 엔진의 '항상 본기' 병렬 대안은 원문이 아닌 학파 대안(SCHOOL_VARIANT)이며 원문과 일치하는 쪽은 MG-L4-GYEOKGUK-CAND."),
]
CODE = {
    "MG-L2-HAP-HWA": "layer2.py: stem_gap()·month_tier() 추가, 천간합/합화 후보에 '사이 글자가 합 상대를 극하지 않음(間隔)' 조건, 월령 득시/次等 판정",
    "MG-L2-HYUNG": "layer2.py: hyung_profile=common|no_self (자형 제외)", "MG-L1-TONGGEUN": "layer1.py: tonggeun_profile=position_role|twelve_stage (沈孝瞻 十二運 기준)",
    "MG-L2-PA": "(기존) pa_profile=modern_6|sanmyeongtonghoe_4",
}

out = []
w = out.append
w("# 고전 규칙 37개 원문 검증 결과 (P0, v6.6 갱신)\n")
w("산출: `backend/golden/classical_verification.json`, `backend/golden/classical_differences.json`, 조회 API `app/mingli/classical.py`, 재실행 `python -m tools.verify_classical` · `python -m tools.build_classical_differences`(네트워크 필요), 문서 생성 `python -m tools.build_doc09`, 테스트 `tests/test_classical*.py`. 접근일 2026-10-29.")
w("`rules.py` 는 이 작업에서 수정하지 않았다(상태 병합은 부모 작업의 `_merge_classical()` 이 JSON 을 읽어 반영).\n")
w("## 상태 정의 (보수적)\n")
w("| 상태 | 의미 |\n|---|---|")
w("| pending | 확인하지 못함 |")
w("| location_confirmed | 출처 페이지에서 장·핵심어 위치만 확인. 구절이 규칙 내용을 직접 뒷받침하는지는 **판단하지 않음** (+ `content_gap` 으로 이유 기록) |")
w("| text_confirmed | 사람이 구절을 읽고 `scope_note` 범위에서 규칙 내용에 대응함을 확인. 발췌(≤40자)가 페이지 텍스트에 그대로 있는지 스크립트가 재검증(없으면 자동 강등). `coverage=partial` 이면 일부 조건만 확인된 것이고 `unconfirmed_parts` 에 미확인 부분이 적혀 있다 |")
w("| implementation_convention | 고전 주장 없음(구현자 규약) |\n")
w("`text_confirmed` 는 '고전과 일치한다'가 아니라 '표시한 범위에서 원문이 뒷받침한다'이다. **승격 원칙**: 규칙의 *주된 정의*가 원문에 직접 대응하면 부분 확인이라도 coverage=partial 로 승격하고, 원문이 규칙을 **부정·보류·다른 기준으로 서술**하면(BONGI, HYUNG, PA, HAE) location_confirmed 로 남긴다.\n")
w("## 결과 요약\n")
w("| 상태 | 개수 |\n|---|---|")
for st in ("text_confirmed", "location_confirmed", "implementation_convention", "pending"):
    w(f"| {st} | {cnt.get(st, 0)} |")
w(f"| 합계 | {sum(cnt.values())} |\n")
w(f"v6.5 → v6.6: text_confirmed 23 → {cnt['text_confirmed']}, location_confirmed 8 → {cnt['location_confirmed']}, implementation_convention 6 → {cnt['implementation_convention']}. 그중 범위 한정(partial) text_confirmed: {', '.join(partial)}.\n")
w("**CLASSICAL_RULES_PENDING 은 해제되지 않는다**: location_confirmed 4개가 남아 있고, text_confirmed 도 범위 한정이다. 판본 교감(영인본 대조)은 **미수행**이다.\n")
w("## 접속 실패한 출처\n")
fs = V.get("failed_sources", {})
w("- `donglishuzhai.net/chapter/3721.html`(子平真詮 卷一·八), `m.donglishuzhai.net/chapter/3722.html`(卷一·九): 30초 연결 시간 초과(재시도 포함)로 열지 못함. 이 두 URL 에 대한 대조는 **미수행**이며, 같은 원문을 담은 `libokang.com` 子平真詮評註(원문 + 평주)로 대신 확인했다." + (f" 실패 기록: {', '.join(fs)}" if fs else ""))
w("- 窮通寶鑑·淵海子平은 열리지만 이 작업의 규칙을 text_confirmed 로 올릴 구절은 찾지 못했다.\n")
w("## 위치만 확인되던 8개 규칙의 상세 조사 (v6.6)\n")
w("| 규칙 | 결과 | 조사 내용 (원문이 말하는 조건 / 후대 주석 / 엔진 구현 / 일치·불일치) |\n|---|---|---|")
for rid, res, txt in EIGHT:
    w(f"| {rid} | {res} | {txt} |")
w("")
w("공통: 원문 발췌는 `additional_excerpts`(JSON) 에 ≤40자로 저장, 모두 캐시 페이지에서 그대로 재확인(`verified_in_page`). 학파별 적용·예외는 각 항목 `school_conditions`.\n")
w("## 원문·구현 차이 13건 분류\n")
w("| 규칙 | 분류 | 보조 분류 | 요약 | 처리 | 상태 |\n|---|---|---|---|---|---|")
for rid, d in DF.items():
    w(f"| {rid} | **{d['classification']}** | {', '.join(d['secondary']) or '-'} | {d['summary'][:150].rstrip()}… | {d['handling'][:120].rstrip()}… | {d['status']} |")
c2 = Counter(d["classification"] for d in DF.values())
w("")
w("분류 합계: " + ", ".join(f"{k} {v}" for k, v in c2.items()) + ". IMPLEMENTATION_BUG 는 수정하고 회귀 테스트를 추가했다. SCHOOL_VARIANT 는 프로필로 분리했고, MODERN_CONVENTION 은 고전의 직접 주장으로 표시하지 않는다.\n")
w("### 수정·추가한 코드\n")
for k, v in CODE.items():
    w(f"- **{k}**: {v}")
w("- 회귀 테스트: `tests/test_classical_regressions.py` (間隔, 월령 득시/次等, 害 도출 일치, 자형 프로필, 십이운성 통근). 분류 검증: `tests/test_classical_diffs.py`.")
w("- 기본 프로필은 모두 기존 동작을 유지한다(`pa=modern_6`, `hyung=common`, `tonggeun=position_role`). `analyze_structure(profiles=...)` 로 새 프로필을 고르려면 `mingli/__init__.py` 의 전달 코드가 필요하다(부모 작업에 제안 diff 전달).\n")
w("## 규칙별 상태\n")
w("| 규칙 | 상태 | coverage | 근거 출처 | 비고(범위·한계) |\n|---|---|---|---|---|")
for rid, e in R.items():
    note = (e.get("scope_note") or e.get("notes") or "")[:110].rstrip()
    w(f"| {rid} | {e['status']} | {e.get('coverage') or '-'} | {(e.get('work') or '-')} {('· ' + e['section']) if e.get('section') else ''} | {note} |")
w("")
w("## 한계\n")
w("- 원문/주석 구분은 libokang 페이지의 '沈氏原文說·徐樂吾評註' 표지와 滴天髓闡微의 〈原註〉·〈任氏曰〉 표지에 의존한 분류다. 滴天髓輯要(wikisource)는 원문 게송과 주석 문장이 표지 없이 섞여 있어 `annotation` 으로 표기했다. **판본 교감은 미수행**이다.")
w("- 전사본 이용 조건은 확인하지 않았다. 저장소에는 ≤40자 발췌만 둔다.")
w("- 성립/불성립 가상 명식(합성)은 JSON 의 `positive_case`/`negative_case` 에 있고 `tests/test_classical.py` 가 엔진 출력으로 재검증한다. 일부 명식은 여러 규칙에 재사용된다.")
w("- `MG-L5-LUCK-STEM` 은 규칙만 등록되어 있고 엔진이 해당 rule_id 노드를 만들지 않는다.")
(ROOT / "docs/09_CLASSICAL_RULES_VERIFICATION.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("doc09 written", dict(cnt))
