"""v9.6 사람 평가 도구 테스트. 아래 평가 응답은 도구 동작 검증용 가짜이며 실제 평가가 아니다. 응답이 없으면 '미평가'가 유지되는지, 길이 편향을 분리하는지가 핵심."""
import csv
import io
import json

import pytest

from app import blind_eval as BE
from tools import blind_eval as T

ITEMS = [{"item_id": f"c{i}", "question": "질문", "years": [2030], "domains": ["overall"],
          "variants": {"v81": "짧은 문장입니다.", "v82": "조금 더 긴 문장입니다. 두 번째 문장도 있습니다.", "v95": "가장 긴 문장입니다. " * 6}} for i in range(12)]


def packet():
    return BE.build_packet(ITEMS, criteria=BE.CRITERIA_V96)


def csv_for(pk, key, rid, role="general", score_of=lambda v, n: 3, prefer=None, n_items=12):
    keys = BE.criteria_keys(pk)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(BE.csv_columns(keys))
    for it in pk["items"][:n_items]:
        slots = key["items"][it["id"]]["slots"]
        for slot, variant in slots.items():
            sc = score_of(variant, len(it["texts"][slot]))
            w.writerow([rid, role, it["id"], slot, *[sc] * len(keys), 1 if variant == prefer else "", "읽기 편해서" if variant == prefer else ""])
    return out.getvalue()


def test_v96_has_the_eight_requested_criteria_in_plain_words():
    assert [k for k, _ in BE.CRITERIA_V96] == ["understand", "specific", "domain_diff", "period_diff", "evidence", "natural", "fit", "cautious"]
    labels = " ".join(l for _, l in BE.CRITERIA_V96)
    for w in ("이해도", "명식별 구체성", "분야별 차이", "시기별 차이", "근거와의 일치", "자연스러움", "질문 적합성", "신중함"):
        assert w in labels
    assert "명리" not in labels.replace("명리학", "")          # 전문지식 없이 평가 가능한 표현
    pk, _ = packet()
    assert BE.criteria_keys(pk) == [k for k, _ in BE.CRITERIA_V96] and BE.criteria_keys(None) == BE.CRITERIA_KEYS


def test_no_responses_means_unevaluated_for_v96_too():
    pk, key = packet()
    agg = BE.aggregate(pk, key, [])
    assert BE.pilot_gate(agg)["status"] == "미평가" and not BE.gate(agg)["completed"]


def test_csv_roundtrip_with_eight_criteria_and_user_role():
    pk, key = packet()
    text = csv_for(pk, key, "u1", role="user", score_of=lambda v, n: {"v81": 2, "v82": 3, "v95": 4}[v], prefer="v95")
    ratings = BE.ratings_from_csv(text)
    assert ratings[0]["role"] == "user" and len(ratings[0]["ratings"]) == 12
    agg = BE.aggregate(pk, key, ratings)
    assert not agg["rejected"] and agg["criteria_keys"] == BE.criteria_keys(pk) and agg["overall"] == {"v81": 2.0, "v82": 3.0, "v95": 4.0}
    assert agg["preference"] == {"v95": 12} and agg["means"]["v95"]["cautious"] == 4.0
    rows = {r["variant"]: r for r in BE.summary_rows(agg)}
    assert rows["v95"]["fit"] == 4.0 and "trust" not in rows["v95"]


def test_pilot_five_criteria_csv_still_parses():
    pk5, key5 = BE.build_packet(ITEMS)
    text = csv_for(pk5, key5, "g1")
    assert text.splitlines()[0].split(",")[4:9] == BE.CRITERIA_KEYS
    agg = BE.aggregate(pk5, key5, BE.ratings_from_csv(text))
    assert not agg["rejected"] and agg["criteria_keys"] == BE.CRITERIA_KEYS


def test_out_of_range_score_in_v96_is_rejected():
    pk, key = packet()
    bad = csv_for(pk, key, "bad").replace(",3,3,3,3,3,3,3,3,", ",9,3,3,3,3,3,3,3,", 1)
    agg = BE.aggregate(pk, key, BE.ratings_from_csv(bad))
    assert agg["rejected"] and agg["raters"] == {}


# ---------------------------------------------------------------- 길이·문체 편향 분리
def test_length_bias_is_detected_when_scores_simply_follow_length():
    pk, key = packet()
    longer_is_better = lambda v, n: min(5, max(1, round(n / 20)))
    ratings = BE.ratings_from_csv(csv_for(pk, key, "r1", score_of=longer_is_better, prefer="v95"))
    cf = BE.confounds(pk, key, ratings)
    assert cf["length_score_corr"] > 0.8 and cf["length_bias_suspected"] is True
    assert cf["prefers_longest_share"] == 1.0 and cf["chance_prefers_longest"] == pytest.approx(1 / 3, abs=0.01)
    lbv = cf["length_by_variant"]
    assert lbv["v95"]["mean_chars"] > lbv["v82"]["mean_chars"] > lbv["v81"]["mean_chars"]
    adj = cf["length_adjusted_mean"]
    raw = BE.aggregate(pk, key, ratings)["overall"]
    assert (max(adj.values()) - min(adj.values())) < (max(raw.values()) - min(raw.values())) / 1.8      # 길이로 설명되는 차이는 보정 후 크게 줄어든다(점수가 1~5 로 잘려 완전히 0 은 아님)


def test_quality_difference_beyond_length_survives_adjustment_and_no_bias_flag_for_flat_scores():
    pk, key = packet()
    # v81(짧음)이 가장 높게, v95(김)가 가장 낮게 평가 → 길이로는 설명되지 않는 차이
    ratings = BE.ratings_from_csv(csv_for(pk, key, "r2", score_of=lambda v, n: {"v81": 5, "v82": 3, "v95": 1}[v]))
    cf = BE.confounds(pk, key, ratings)
    assert cf["length_score_corr"] < -0.5
    flat = BE.confounds(pk, key, BE.ratings_from_csv(csv_for(pk, key, "r3", score_of=lambda v, n: 3)))
    assert flat["length_bias_suspected"] is False and flat["length_score_corr"] is None


def test_confounds_note_forbids_blindly_scaling_up_well_rated_style():
    pk, key = packet()
    cf = BE.confounds(pk, key, [])
    assert "확대 적용하지 않는다" in cf["note"] and cf["n_scored"] == 0


# ---------------------------------------------------------------- 폼(독립 HTML)
def test_form_builds_instructions_and_csv_columns_from_the_packet():
    pk, _ = packet()
    html = T.FORM.replace("__PACKET__", json.dumps(pk, ensure_ascii=False))
    assert "ncrit" in html and "lcrit" in html and "C.map(c=>c.key)" in html and "'내 사주로 직접 써 본 사용자'" not in html and "내 사주로 직접 써 본 사용자" in html
    assert "http://" not in html and "https://" not in html and "fetch(" not in html and "XMLHttpRequest" not in html
    assert not any(x in json.dumps(pk, ensure_ascii=False) for x in ('"v81"', '"v82"', '"v95"'))     # 패킷에 변형 이름이 없다
