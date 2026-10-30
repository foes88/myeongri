"""블라인드 평가 도구 테스트. 평가 점수 fixture 는 도구 검증용 합성 값이며 실제 사람 평가가 아니다."""
import json

from app import blind_eval as BE

ITEMS = [{"item_id": f"c{i}", "question": "질문", "years": [2030], "domains": ["overall"], "variants": {"legacy": f"기존 문장 {i}", "synthesis": f"종합 문장 {i}"}} for i in range(12)]


def test_packet_hides_source_and_is_reproducible_and_balanced():
    pk, key = BE.build_packet(ITEMS)
    blob = json.dumps(pk, ensure_ascii=False)
    assert "legacy" not in blob and "synthesis" not in blob and "c1" not in blob  # 변형 이름·명식 이름 비공개
    assert BE.build_packet(ITEMS)[0] == pk
    first = [next(iter(v["slots"].values())) for v in key["items"].values()]
    assert 3 <= first.count("legacy") <= 9  # 위치 편향 방지: X 슬롯이 한쪽 변형으로 쏠리지 않음
    for it in pk["items"]:
        assert set(it["texts"]) == {"X", "Y"}


def rating(pk, key, rid, role, prefer_variant, n=12, bad=False):
    out = []
    for it in pk["items"][:n]:
        slots = key["items"][it["id"]]["slots"]
        inv = {v: s for s, v in slots.items()}
        sc = {inv["synthesis"]: {k: 4 for k in BE.CRITERIA_KEYS}, inv["legacy"]: {k: 2 for k in BE.CRITERIA_KEYS}}
        if bad:
            sc[inv["legacy"]]["understand"] = 9
        out.append({"id": it["id"], "scores": sc, "preferred": inv[prefer_variant]})
    return {"rater_id": rid, "role": role, "ratings": out}


def test_aggregate_maps_slots_back_to_variants_and_rejects_invalid():
    pk, key = BE.build_packet(ITEMS)
    rs = [rating(pk, key, f"e{i}", "expert", "synthesis") for i in range(3)] + [rating(pk, key, f"l{i}", "lay", "synthesis") for i in range(3)] + [rating(pk, key, "x", "lay", "synthesis", bad=True)]
    agg = BE.aggregate(pk, key, rs)
    assert agg["overall"]["synthesis"] == 4.0 and agg["overall"]["legacy"] == 2.0
    assert agg["preference"]["synthesis"] == 72 and "legacy" not in agg["preference"]
    assert agg["rejected"] and agg["rejected"][0]["rater_id"] == "x"
    assert agg["raters"] == {"expert": 3, "lay": 3} and agg["agreement"] == 1.0
    assert BE.gate(agg)["completed"]  # 도구 검증용 합성 입력일 때만 통과


def test_gate_never_completes_without_enough_human_raters():
    pk, key = BE.build_packet(ITEMS)
    assert not BE.gate(BE.aggregate(pk, key, []))["completed"]
    one = BE.aggregate(pk, key, [rating(pk, key, "e1", "expert", "synthesis")])
    g = BE.gate(one)
    assert not g["completed"] and any("전문가" in r for r in g["reasons"]) and any("일반" in r for r in g["reasons"])
    few = BE.aggregate(pk, key, [rating(pk, key, f"e{i}", "expert", "synthesis", n=3) for i in range(3)] + [rating(pk, key, f"l{i}", "lay", "synthesis", n=3) for i in range(3)])
    assert not BE.gate(few)["completed"]  # 평가자 수가 충분해도 항목 수가 모자라면 미완료
