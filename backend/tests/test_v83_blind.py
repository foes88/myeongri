"""블라인드 평가 파일럿 도구 테스트. 아래 응답 데이터는 도구 동작 검증용 가짜이며 실제 평가가 아니다. 응답이 없으면 '미평가'가 유지되는지가 핵심."""
import csv
import io
import json

import pytest

from app import blind_eval as BE

ITEMS = [{"item_id": f"c{i}", "question": "질문", "years": [2030], "domains": ["overall"], "variants": {"v70": f"a{i}", "v81": f"b{i}", "v82": f"c{i}"}} for i in range(12)]


def csv_for(pk, key, rid, role="general", prefer="v82", n=12, reason="읽기 편해서"):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(BE.CSV_COLUMNS)
    for it in pk["items"][:n]:
        slots = key["items"][it["id"]]["slots"]
        for slot, variant in slots.items():
            base = {"v82": 4, "v81": 3, "v70": 2}[variant]
            w.writerow([rid, role, it["id"], slot, base, base, base, base, base, 1 if variant == prefer else "", reason if variant == prefer else ""])
    return out.getvalue()


def agg_of(csvs, pk, key):
    ratings = []
    for c in csvs:
        ratings += BE.ratings_from_csv(c)
    return BE.aggregate(pk, key, ratings)


def test_no_responses_means_unevaluated_and_never_complete():
    pk, key = BE.build_packet(ITEMS)
    agg = BE.aggregate(pk, key, [])
    g = BE.pilot_gate(agg)
    assert g["status"] == "미평가" and not g["pilot_complete"] and not g["validation_complete"] and g["reasons"] == ["유효한 평가 응답 0건"]
    assert not BE.gate(agg)["completed"]


def test_criteria_are_the_five_pilot_items_in_plain_words():
    assert BE.CRITERIA_KEYS == ["understand", "specific", "useful", "natural", "trust"]
    labels = " ".join(l for _, l in BE.CRITERIA)
    assert all(w in labels for w in ("이해도", "구체성", "유용성", "자연스러움", "신뢰도")) and "명리" not in labels  # 전문지식 없이 평가 가능한 표현


def test_csv_roundtrip_maps_slots_back_to_versions_and_collects_reasons():
    pk, key = BE.build_packet(ITEMS)
    agg = agg_of([csv_for(pk, key, f"r{i}", prefer="v82") for i in range(3)], pk, key)
    assert agg["overall"] == {"v82": 4.0, "v81": 3.0, "v70": 2.0} and agg["preference"] == {"v82": 36} and agg["agreement"] == 1.0
    assert agg["raters"] == {"general": 3} and len(agg["reasons"]["v82"]) == 36 and agg["reasons"]["v82"][0] == "읽기 편해서"
    rows = {r["variant"]: r for r in BE.summary_rows(agg)}
    assert rows["v82"]["understand"] == 4.0 and rows["v70"]["trust"] == 2.0 and rows["v82"]["preferred_count"] == 36


def test_pilot_status_progression_and_it_never_claims_validation_complete():
    pk, key = BE.build_packet(ITEMS)
    one = BE.pilot_gate(agg_of([csv_for(pk, key, "r1")], pk, key))
    assert one["status"] == "진행 중" and "평가자 1/5명" in one["reasons"][0]
    five = BE.pilot_gate(agg_of([csv_for(pk, key, f"r{i}") for i in range(5)], pk, key))
    assert five["pilot_complete"] and five["status"].startswith("파일럿 완료") and not five["validation_complete"] and "통계적 결론이 아니다" in five["note"]
    few_items = BE.pilot_gate(agg_of([csv_for(pk, key, f"r{i}", n=4) for i in range(5)], pk, key))
    assert not few_items["pilot_complete"] and any("10항목 미만" in r for r in few_items["reasons"])
    experts = [csv_for(pk, key, f"e{i}", role="expert") for i in range(3)] + [csv_for(pk, key, f"g{i}") for i in range(3)]
    full = BE.pilot_gate(agg_of(experts, pk, key))
    assert full["validation_complete"]   # 전문가 3 + 일반 3 + 항목 기준을 모두 채웠을 때만(도구 검증용 가짜 응답)


def test_invalid_rows_are_rejected_not_silently_counted():
    pk, key = BE.build_packet(ITEMS)
    bad = csv_for(pk, key, "bad").replace(",4,4,4,4,4,", ",9,4,4,4,4,", 1)
    agg = agg_of([bad, csv_for(pk, key, "ok")], pk, key)
    assert [r["rater_id"] for r in agg["rejected"]] == ["bad"] and agg["raters"] == {"general": 1}
    unknown = BE.aggregate(pk, key, BE.ratings_from_csv("rater_id,role,item_id,slot,understand,specific,useful,natural,trust,preferred,reason\nx,alien,zzz,X,3,3,3,3,3,1,r\n"))
    assert unknown["rejected"] and unknown["raters"] == {}


def test_packet_has_no_source_labels_and_form_is_standalone_with_plain_instructions():
    from tools import blind_eval as T
    pk, key = BE.build_packet(ITEMS)
    html = T.FORM.replace("__PACKET__", json.dumps(pk, ensure_ascii=False))
    assert "명리학을 몰라도 됩니다" in html and "가상의 사주" in html and "정답은 없고" in html and "서버로 전송되는 것은 없습니다" in html
    for w in ("이해도", "구체성", "유용성", "자연스러움", "신뢰도"):
        assert w in html or w in json.dumps(pk, ensure_ascii=False)
    assert "http://" not in html and "https://" not in html and 'src="' not in html and "fetch(" not in html and "XMLHttpRequest" not in html  # 독립 HTML, 전송 없음
    assert not any(x in json.dumps(pk, ensure_ascii=False) for x in ("v70", "v81", "v82"))
