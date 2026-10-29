"""상담 답변 지표(Track A, 자동). 사실표·출처·논리·차이는 자동으로 재고, 깊이·실제 도움은 사람 평가 영역이다(한계는 docs/12)."""
from __future__ import annotations

import re

from ..report_checks import FORBIDDEN_PATTERNS
from ..mingli.rules import RULES

BOILER_KINDS = {"closing"}
HEDGE = re.compile(r"후보|가능|다를 수|단정하지|존재만|견해|논쟁|알려진|전통|아닙니다|않습니다|보류|확인되지")
ASSERT = re.compile(r"반드시|확실(?!하지)|틀림없|보장(?!하지)|무조건|100%|분명히|결국 .{0,6}됩니다")  # '보장하지 않습니다' 같은 부정 고지는 단정이 아님
CLASSICAL_WORDS = re.compile(r"(고전|원전|원문|자평진전|적천수|궁통보감|삼명통회|연해자평)")
ANCHOR = re.compile(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]|\b[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}\b|(?<!\d)(19|20)\d{2}(?!\d)")
JARGON = ["식상생재", "재생관", "관인상생", "살인상생", "상관견관", "군겁쟁재", "격국", "용신", "통근", "투간", "득령", "실령", "대운", "세운", "합화", "천간합", "육합", "삼합", "방합", "개고", "입묘",
          "정관격", "칠살격", "정인격", "편인격", "식신격", "상관격", "정재격", "편재격", "건록격", "억부", "조후"]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?。])\s+|\n+", text) if s.strip()]


def content_sentences(ans: dict) -> list[str]:
    out = []
    for p in ans.get("paragraphs", []):
        if p["kind"] in BOILER_KINDS:
            continue
        out += sentences(p["text"])
    return out


def chart_tokens(pre: dict, ans: dict) -> set[str]:
    P = pre["natal_structure"]["pillars"]
    toks = set(P.values()) | set(P[k][0] for k in P) | set(P[k][1] for k in P)
    for pe in ans.get("periods", []):
        for s in pe["segments"]:
            toks |= {x for x in (s.get("luck"), s.get("sewun")) if x}
    return toks


def specificity(ans: dict, pre: dict) -> dict:
    """명식 고유성: 내용 문장 중 이 명식·연도·claim 에 묶인 문장의 비율."""
    cs = content_sentences(ans)
    toks = chart_tokens(pre, ans)
    labels = {s["name"] for s in pre["natal_structure"]["layer3"]["structures"] if s["rank"] > 0}
    def anchored(s):
        return bool(ANCHOR.search(s)) or any(t in s for t in toks if len(t) == 2) or any(f"'{l}'" in s for l in labels)
    n = sum(anchored(s) for s in cs)
    return {"content_sentences": len(cs), "anchored": n, "ratio": round(n / len(cs), 3) if cs else 0.0}


def evidence(ans: dict, pre: dict) -> dict:
    """복합 통변 근거: 인용한 claim 수와 그래프 연결성, 반대 근거 보유율, 고전 출처 상태."""
    g = pre["natal_structure"]["graph"]
    nodes = {n["claim_id"]: n for n in g["nodes"]}
    cited = {c for p in ans.get("paragraphs", []) for c in p["claim_ids"] if c in nodes}
    linked = {e["from"] for e in g["edges"]} | {e["to"] for e in g["edges"]}
    conn = len(cited & linked) / len(cited) if cited else 0.0
    counter = sum(1 for c in cited if nodes[c]["counter_evidence"] or nodes[c]["counter_checked"]) / len(cited) if cited else 0.0
    st: dict[str, int] = {}
    for c in cited:
        s = RULES[nodes[c]["rule_id"]]["classical_status"]
        st[s] = st.get(s, 0) + 1
    # 고전 단어를 쓴 문장이 text_confirmed 근거 없이 고전 근거처럼 서술하는지(과장)
    cited_status = set(st)
    over = [s for s in content_sentences(ans) if CLASSICAL_WORDS.search(s) and not re.search(r"대조 전|대조가 끝나지|확인되지|확인하지|않았|않습니다|전입니다", s)]
    return {"cited_claims": len(cited), "graph_connectivity": round(conn, 3), "counter_coverage": round(counter, 3), "classical_status_counts": st,
            "classical_overclaim_sentences": len(over), "only_confirmed": cited_status <= {"text_confirmed"}}


def domain_evidence(ans: dict) -> dict:
    blocks = ans.get("blocks", [])
    with_counter = sum(1 for b in blocks if b["evidence_against"])
    return {"domains": len(blocks), "with_counter": with_counter, "ratio": round(with_counter / len(blocks), 3) if blocks else 1.0}


def assertion(ans: dict) -> dict:
    cs = content_sentences(ans) + [x for x in ans.get("limits", [])]
    bad = sum(1 for s in cs if ASSERT.search(s) or any(re.search(p, s) for p in FORBIDDEN_PATTERNS))
    claim_like = [s for s in content_sentences(ans) if ANCHOR.search(s)]
    hedged = sum(1 for s in claim_like if HEDGE.search(s))
    return {"assertive_sentences": bad, "total": len(cs), "assertive_ratio": round(bad / len(cs), 3) if cs else 0.0,
            "hedged_claim_ratio": round(hedged / len(claim_like), 3) if claim_like else 1.0}


def readability(ans: dict) -> dict:
    """일반인 이해도의 자동 대리 지표(실제 이해도는 사람 평가 필요): 문장 길이, 전문용어 밀도, 용어 설명 포함률."""
    text = " ".join(p["text"] for p in ans.get("paragraphs", []))
    ss = sentences(text)
    used = [j for j in JARGON if j in text]
    gloss = set(ans.get("glossary", {}))
    cov = len([j for j in used if any(j in g or g in j for g in gloss)]) / len(used) if used else 1.0
    toks = re.findall(r"[가-힣]+", text)
    dens = sum(text.count(j) for j in JARGON) / max(len(toks), 1)
    return {"avg_sentence_chars": round(sum(map(len, ss)) / len(ss), 1) if ss else 0, "jargon_density": round(dens, 3), "glossary_coverage": round(cov, 3),
            "proxy_only": True}


def signature(ans: dict, pre: dict) -> set:
    """해석의 의미 서명: (규칙, 상태) 인용 + 구조 라벨 + 운 관계 종류. 문장 표현이 아니라 판단 내용을 비교한다."""
    nodes = {n["claim_id"]: n for n in pre["natal_structure"]["graph"]["nodes"]}
    sig = {(nodes[c]["rule_id"], nodes[c]["status"]) for p in ans.get("paragraphs", []) for c in p["claim_ids"] if c in nodes}
    for b in ans.get("blocks", []):
        sig |= {("L3", i["structure"], i["label"]) for i in b["structures"]}
        sig.add(("DOM", b["domain"]))
        sig |= {("EV", b["domain"], e) for e in b["evidence_for"]}
    for pe in ans.get("periods", []):
        for s in pe["segments"]:
            sig |= {("REL", pe["year"], r["who"], r["type"], r["with"]) for r in s.get("relations", [])}
            sig.add(("LUCK", pe["year"], s.get("luck"), s.get("sewun")))
    for f in ans.get("natal_feature_items", []):
        sig.add(("FEAT", f["kind"], f["text"]))
    return sig


def jacc_dist(a: set, b: set) -> float:
    u = a | b
    return round(1 - len(a & b) / len(u), 3) if u else 0.0


def token_dist(t1: str, t2: str) -> float:
    a, b = set(re.findall(r"\w+", t1)), set(re.findall(r"\w+", t2))
    return jacc_dist(a, b)


FACET_OF_KIND = {"month": "month", "deukryeong": "deukryeong", "strength": "strength", "gyeokguk": "gyeokguk", "tonggeun": "tonggeun", "structure": "structure", "relations": "relations"}


def changed_facets(a1: dict, a2: dict) -> set[str]:
    f1 = {f["kind"]: f["text"] for f in a1["natal_feature_items"]}
    f2 = {f["kind"]: f["text"] for f in a2["natal_feature_items"]}
    out = {FACET_OF_KIND[k] for k in set(f1) | set(f2) if f1.get(k) != f2.get(k) and k in FACET_OF_KIND}
    if (a1.get("school_view") or {}).get("per_school") != (a2.get("school_view") or {}).get("per_school"):
        out.add("schools")
    p1 = [(pe["year"], [(s["luck"], s["sewun"], s["text"]) for s in pe["segments"]]) for pe in a1["periods"]]
    p2 = [(pe["year"], [(s["luck"], s["sewun"], s["text"]) for s in pe["segments"]]) for pe in a2["periods"]]
    if p1 != p2:
        out.add("period")
    if [b["domain"] for b in a1["blocks"]] != [b["domain"] for b in a2["blocks"]] or [b["structures"] for b in a1["blocks"]] != [b["structures"] for b in a2["blocks"]] \
            or [b["evidence_for"] for b in a1["blocks"]] != [b["evidence_for"] for b in a2["blocks"]]:
        out.add("domain")
    return out
