"""Layer 3 — 생극제화: 식상생재·재생관·관인상생·살인상생·상관견관·군겁쟁재.

구조의 '존재 정도'를 순서형 라벨로만 표현한다(뚜렷 > 보통 > 약함 > 없음). 점수·확률 없음.
같은 구조에 대한 반례(편인도식·비겁 탈재·재극인 등)를 항상 함께 기록하고, 경로(예: 식상→재→관)는 근거 그래프 간선으로 남긴다.
"""
from __future__ import annotations

from ..chart_analysis import GROUP_OF
from ..report_checks import ten_god
from .evidence import ClaimNode, EvidenceGraph
from .layer1 import POS, POS_KO, hidden_with_roles
from .rules import RULES

RANK_LABEL = {3: "뚜렷(천간 노출)", 2: "보통(지지 본기 암장)", 1: "약함(중기·여기 암장)", 0: "없음"}


def occurrences(pillars: dict[str, str], extra: dict[str, str] | None = None) -> list[dict]:
    """일간 기준 십성 출현 목록. extra: {'luck':'甲子','year':'乙丑'} 같은 외부 기둥(대운·세운)."""
    day_stem = pillars["day"][0]
    out = []
    items = [(p, pillars[p]) for p in POS if p in pillars] + list((extra or {}).items())
    for pos, gz in items:
        if pos != "day":
            g = ten_god(day_stem, gz[0])
            out.append({"kind": "stem", "pos": pos, "char": gz[0], "god": g, "group": GROUP_OF[g], "role": "", "rank": 3})
        for h in hidden_with_roles(gz[1]):
            g = ten_god(day_stem, h["stem"])
            out.append({"kind": "hidden", "pos": pos, "char": h["stem"], "god": g, "group": GROUP_OF[g], "role": h["role"],
                        "rank": 2 if h["role"] == "본기" else 1, "branch": gz[1]})
    return out


def find(occ: list[dict], *keys: str) -> list[dict]:
    return [o for o in occ if o["group"] in keys or o["god"] in keys]


def best(occs: list[dict]) -> int:
    return max((o["rank"] for o in occs), default=0)


def _fmt(o: dict) -> str:
    where = POS_KO.get(o["pos"], {"luck": "대운", "year": "세운", "month_luck": "월운"}.get(o["pos"], o["pos"]))
    return f"{where}{'간' if o['kind'] == 'stem' else '지 지장간'} {o['char']}({o['god']}{'·' + o['role'] if o['role'] else ''})"


def _node(g, vid, rule_id, prefix, **kw) -> ClaimNode:
    return g.add(ClaimNode(claim_id=g.new_id(prefix), chart_variant_id=vid, rule_id=rule_id, school_id=RULES[rule_id]["school_id"],
                           source_references=RULES[rule_id]["sources"], counter_checked=True, **kw))


def _rel_notes(occs: list[dict], relations: list[dict]) -> list[str]:
    """관여한 지지가 충·형·파·해 관계에 있다는 '사실'만 반례 후보로 남긴다(손상 확정 아님)."""
    pos = {o["pos"] for o in occs if o["kind"] == "hidden"}
    notes = []
    for r in relations or []:
        if r["relation_type"] in ("충", "삼형", "형(부분)", "무례지형(子卯)", "자형", "파", "해") and pos & set(r["pillars"]):
            notes.append(f"관여 지지가 {r['relation_type']} 관계에 있음(존재만 확인, 구조 손상은 확정하지 않음) [{r['claim_id']}]")
    return notes


def analyze_layer3(pillars: dict[str, str], g: EvidenceGraph, vid: str = "v1", relations: list[dict] | None = None,
                   l1_label: str | None = None, extra: dict[str, str] | None = None, tag: str = "L3") -> dict:
    occ = occurrences(pillars, extra)
    S = lambda *k: find(occ, *k)

    def build(name, rule_id, src_keys, dst_keys, counters, path, note=""):
        src, dst = S(*src_keys), S(*dst_keys)
        rank = min(best(src), best(dst))
        label = RANK_LABEL[rank]
        cnt = [c for c in counters if c is not None]
        sup = ([f"{_fmt(o)}" for o in src if o["rank"] >= 1][:6] + [f"→ {_fmt(o)}" for o in dst if o["rank"] >= 1][:6]) if rank else []
        cnt += _rel_notes(src + dst, relations)
        if rank and rank < 3:
            cnt.append(f"한쪽 이상이 암장이라 천간에 드러난 구조보다 약하다고 보는 견해: {label}")
        n = _node(g, vid, rule_id, tag, supporting_evidence=sup or [f"{'/'.join(src_keys)} 또는 {'/'.join(dst_keys)} 출현 없음"],
                  counter_evidence=cnt, applicability=[f"경로 {path}", "출현 순위: 천간 > 본기 > 중·여기"] + ([note] if note else []),
                  exclusions=["합충으로 인한 글자 변화는 Layer 2 관계로 별도 평가", "대운·세운 유입은 Layer 5"],
                  conflicting_claims=[], uncertainty="구조의 존재와 그 구조가 현실에서 작용하는 방식은 다르며, 학파별 성립 조건이 다름. 길흉을 말하지 않음",
                  interpretation_summary=f"{name}: {label}" + (" (반례 있음)" if cnt else ""), status=label,
                  attributes={"name": name, "path": path, "rank": rank})
        return {"claim_id": n.claim_id, "name": name, "label": label, "rank": rank, "path": path, "supporting": n.supporting_evidence,
                "counter": n.counter_evidence}

    cnt_bigeop = [o for o in S("비겁") if o["rank"] >= 2]
    out = []
    # 식상생재
    out.append(build("식상생재", "MG-L3-SIKSANG-SAENGJAE", ("식상",), ("재성",),
                     [("편인도식: 偏印과 食神이 함께 있어 식신이 눌린다는 견해" if S("偏印") and S("食神") else None),
                      ("비겁이 재를 다툼(군겁쟁재 후보와 겹침)" if len(cnt_bigeop) >= 2 and S("재성") else None),
                      ("식상이 암장뿐이라 생재의 원천이 약하다는 견해" if S("식상") and best(S("식상")) < 3 else None)], "식상→재성"))
    out.append(build("재생관", "MG-L3-JAE-SAENGGWAN", ("재성",), ("관성",),
                     [("비겁이 재성을 탈취(탈재)" if cnt_bigeop else None), ("상관이 있어 관을 해친다는 견해(상관견관과 겹침)" if S("傷官") and S("관성") else None)],
                     "재성→관성"))
    out.append(build("관인상생", "MG-L3-GWAN-INSAENG", ("관성",), ("인성",),
                     [("재성이 인성을 극함(재극인)" if S("재성") and best(S("재성")) >= 2 else None),
                      ("식상이 관성을 극함(식상극관)" if S("식상") and best(S("식상")) >= 2 else None)], "관성→인성"))
    out.append(build("살인상생", "MG-L3-SAL-INSAENG", ("七殺",), ("인성",),
                     [("食神이 함께 있어 식신제살 경로와 병존(어느 경로를 우선하는지 학파별 논쟁)" if S("食神") else None),
                      ("재성이 살을 생함(재자약살)" if S("재성") and best(S("재성")) >= 2 else None)], "七殺→인성"))
    sg = build("상관견관", "MG-L3-SANGGWAN-GYEONGWAN", ("傷官",), ("正官",),
               [("인성이 있어 상관을 제어(상관패인) — 구응 후보" if S("인성") else None),
                ("재성이 있어 상관을 설기하여 통관(상관생재) — 구응 후보" if S("재성") else None)], "傷官 ↔ 正官",
               note="이 구조는 충돌형이며, 라벨은 두 십성이 모두 존재하는 정도를 뜻함")
    out.append(sg)
    kg_rank = best(cnt_bigeop) if len(cnt_bigeop) >= 2 else 0
    rank = min(kg_rank, best(S("재성")))
    kg = build("군겁쟁재", "MG-L3-GUNGEOP-JAENGJAE", ("비겁",), ("재성",),
               [("관성이 있어 비겁을 제어(제겁)" if S("관성") else None), ("식상이 있어 비겁을 설기하며 재를 생함(화겁생재)" if S("식상") else None),
                ("일간이 약하면 비겁은 오히려 일간을 돕는 용도로 보는 억부론 견해" if l1_label == "약 후보" else None),
                ("비겁 본기 이상 출현이 2개 미만이면 '군겁'이라 부르기 어렵다는 견해" if len(cnt_bigeop) < 2 else None)], "비겁→재성(탈취)")
    if len(cnt_bigeop) < 2:
        kg["label"] = "없음"; kg["rank"] = 0
        g.nodes[kg["claim_id"]].status = "없음"
    out.append(kg)
    del rank

    # 경로(연쇄) — 간선으로 기록
    byname = {s["name"]: s for s in out}
    chains = []
    for a, b in (("식상생재", "재생관"), ("재생관", "관인상생"), ("재생관", "상관견관")):
        if byname[a]["rank"] and byname[b]["rank"]:
            c = _node(g, vid, "MG-L3-CHAIN", tag, supporting_evidence=[f"{a}({byname[a]['label']}) 와 {b}({byname[b]['label']}) 이 모두 존재"],
                      counter_evidence=["연쇄가 끊기는 합·충·극 개입 여부는 Layer 2 관계와 Layer 4 에서 별도 확인", "구조 존재가 곧 순환·길함을 뜻하지 않음"],
                      applicability=["두 구조의 순위가 모두 '약함' 이상"], exclusions=[], conflicting_claims=[],
                      uncertainty="연쇄의 질(통관 여부)은 학파별로 평가가 다름", interpretation_summary=f"경로: {a} → {b}", status="경로 존재(후보)")
            g.link(c.claim_id, byname[a]["claim_id"], "depends_on")
            g.link(c.claim_id, byname[b]["claim_id"], "depends_on")
            chains.append({"claim_id": c.claim_id, "from": a, "to": b})
    # 충돌 구조 간 연결
    if sg["rank"] and byname["상관견관"]["rank"] and byname["재생관"]["rank"]:
        g.link(byname["상관견관"]["claim_id"], byname["재생관"]["claim_id"], "conflicts", "상관이 관을 해치는 경로와 재생관 경로 병존")
    if kg["rank"] and byname["식상생재"]["rank"]:
        g.link(kg["claim_id"], byname["식상생재"]["claim_id"], "opposes", "비겁의 탈재가 식상생재 결실을 약화한다고 보는 견해")
    return {"ruleset": "L3", "occurrence_count": len(occ), "structures": out, "chains": chains,
            "note": "라벨은 구조의 출현 정도이며 성패·길흉이 아님. 성격·파격은 Layer 4"}
