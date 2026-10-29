"""근거 그래프: 판단 노드(ClaimNode)와 노드 간 관계(edge). JSON 직렬화 가능, 그래프 DB 불필요.

원칙: 모든 노드는 찬성 근거와 반대 근거를 함께 가진다. 반대 근거를 '검토했으나 없음'이면 counter_checked=True 로 명시해야 하며,
그렇지 않으면 validate() 가 누락으로 표시한다. 점수·확률은 노드에 넣지 않는다(순서형 라벨만).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .rules import RULES

EDGE_TYPES = ("supports", "opposes", "conflicts", "depends_on")


@dataclass
class ClaimNode:
    claim_id: str
    chart_variant_id: str
    rule_id: str
    school_id: str
    supporting_evidence: list[str]
    counter_evidence: list[str]
    applicability: list[str]
    exclusions: list[str]
    conflicting_claims: list[str]
    source_references: list[dict]
    uncertainty: str
    interpretation_summary: str
    status: str = ""                 # 순서형/범주형 라벨 (예: 득령, 부분득령(논쟁), 존재만 확인)
    counter_checked: bool = False    # 반대 근거를 검토했는데 없었다면 True
    attributes: dict = field(default_factory=dict)


class EvidenceGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, ClaimNode] = {}
        self.edges: list[dict] = []
        self._seq: dict[str, int] = {}

    def new_id(self, prefix: str) -> str:
        self._seq[prefix] = self._seq.get(prefix, 0) + 1
        return f"{prefix}-{self._seq[prefix]:03d}"

    def add(self, node: ClaimNode) -> ClaimNode:
        if node.claim_id in self.nodes:
            raise ValueError(f"중복 claim_id: {node.claim_id}")
        self.nodes[node.claim_id] = node
        return node

    def link(self, src: str, dst: str, kind: str, note: str = "") -> None:
        if kind not in EDGE_TYPES:
            raise ValueError(kind)
        self.edges.append({"from": src, "to": dst, "type": kind, "note": note})
        if kind == "conflicts":
            for a, b in ((src, dst), (dst, src)):
                if b not in self.nodes[a].conflicting_claims:
                    self.nodes[a].conflicting_claims.append(b)

    def validate(self) -> list[dict]:
        """누락·불일치 자동 검사. 비어 있으면 통과."""
        problems = []
        for n in self.nodes.values():
            def bad(code, detail=""):
                problems.append({"claim_id": n.claim_id, "code": code, "detail": detail})
            if not n.supporting_evidence:
                bad("MISSING_SUPPORTING_EVIDENCE")
            if not n.counter_evidence and not n.counter_checked:
                bad("MISSING_COUNTER_EVIDENCE", "반대 근거가 없으면 counter_checked=True 로 검토 사실을 명시해야 함")
            if n.rule_id not in RULES:
                bad("UNKNOWN_RULE_ID", n.rule_id)
            elif not n.source_references:
                bad("MISSING_SOURCE_REFERENCES")
            if not n.uncertainty:
                bad("MISSING_UNCERTAINTY")
            for c in n.conflicting_claims:
                if c not in self.nodes:
                    bad("DANGLING_CONFLICT", c)
        for e in self.edges:
            if e["from"] not in self.nodes or e["to"] not in self.nodes:
                problems.append({"claim_id": e["from"], "code": "DANGLING_EDGE", "detail": e["to"]})
        return problems

    def to_dict(self) -> dict:
        return {"nodes": [asdict(n) for n in self.nodes.values()], "edges": self.edges}
