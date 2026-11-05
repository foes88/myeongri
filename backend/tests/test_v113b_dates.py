"""v11.3b 날짜 구간 설명 정확성: 입춘 전 설명은 입춘 전 기간에만 붙고, 이어진 범위만 하나로 합치며, 입춘 전 구간은 엔진 구간(세운)에서 구한다.
독립 감사에서 ‘2월 4일~5월 24일까지 합쳐진 범위 전체가 입춘 전’처럼 말한 오류의 회귀 테스트. 합성 입력만 사용."""
import re

import pytest

from app import cases as C
from app.consult import agent, facts as F, verdict as V
from tools.bias_probe import charts

DOMS = ["overall", "wealth", "career", "love_marriage", "family"]
PRE = "(입춘 전이라 전해의 기운이 적용되는 기간)"


def seg(a, b, luck="甲子", sewun="丁卯"):
    return {"from": a, "to": b, "luck": luck, "sewun": sewun}


# ---------------- 단위: 구간·범위 규칙 ----------------
def test_pre_ipchun_end_comes_from_the_engine_segments_not_a_fixed_date():
    # 입춘 전 / 입춘 후 / 대운 교체(5월)
    segs = [seg("2027-01-01", "2027-02-03", sewun="丙寅"), seg("2027-02-04", "2027-05-24"), seg("2027-05-25", "2027-12-31", luck="乙丑")]
    assert F.pre_ipchun_end(segs) == "2027-02-03"
    # 대운 교체가 입춘 전에 끼어 구간이 둘 이상이어도 입춘 전 끝은 입춘 전날
    segs = [seg("2029-01-01", "2029-02-01", sewun="丁卯"), seg("2029-02-02", "2029-02-02", luck="乙丑", sewun="丁卯"), seg("2029-02-03", "2029-12-31", luck="乙丑", sewun="戊辰")]
    assert F.pre_ipchun_end(segs) == "2029-02-02"
    # 입춘이 다른 날이면 끝도 다르다(하드코딩이 아니다)
    assert F.pre_ipchun_end([seg("2028-01-01", "2028-02-04", sewun="丁卯"), seg("2028-02-05", "2028-12-31", sewun="戊辰")]) == "2028-02-04"
    assert F.pre_ipchun_end([seg("2027-01-01", "2027-12-31")]) is None


def test_only_truly_adjacent_ranges_are_merged_and_gaps_stay_gaps():
    assert F.contiguous_ranges([("2027-01-01", "2027-02-03"), ("2027-02-04", "2027-05-24")]) == [("2027-01-01", "2027-05-24")]
    assert F.contiguous_ranges([("2027-01-01", "2027-02-03"), ("2027-05-25", "2027-12-31")]) == [("2027-01-01", "2027-02-03"), ("2027-05-25", "2027-12-31")]   # 사이를 메우지 않는다
    assert F.contiguous_ranges([("2027-05-25", "2027-12-31"), ("2027-01-01", "2027-02-03")])[0][0] == "2027-01-01"          # 순서와 무관


def test_pre_ipchun_note_is_attached_only_to_the_pre_ipchun_part_of_a_merged_range():
    # 감사 사례: 입춘 전 1/1~2/3 + 입춘 후 2/4~5/24 가 이어져 있음 → 둘로 나누어 각각 말한다
    t = V._rng([("2027-01-01", "2027-02-03"), ("2027-02-04", "2027-05-24")], "2027-02-03")
    assert t == f"1월 1일~2월 3일{PRE}과 2월 4일~5월 24일"
    assert "1월 1일~5월 24일" not in t                                                                                 # 전체가 입춘 전인 것처럼 말하지 않는다
    # 입춘 후만 있으면 설명을 붙이지 않는다
    assert V._rng([("2027-02-04", "2027-05-24"), ("2027-05-25", "2027-12-31")], "2027-02-03") == "2월 4일~12월 31일"
    # 떨어진 범위: 이어 붙이지 않는다(1월 1일~12월 31일 처럼 말하지 않는다)
    assert V._rng([("2027-01-01", "2027-02-03"), ("2027-05-25", "2027-12-31")], "2027-02-03") == f"1월 1일~2월 3일{PRE}과 5월 25일~12월 31일"
    # 입춘 전 마지막 날까지만이면 그대로 설명
    assert V._rng([("2029-01-01", "2029-02-02")], "2029-02-02") == f"1월 1일~2월 2일{PRE}"
    # 입춘 전 구간이 없으면 설명 없음
    assert V._rng([("2027-01-01", "2027-03-01")], None) == "1월 1일~3월 1일"


def test_segments_public_marks_the_pre_ipchun_part_even_when_luck_changes_before_ipchun():
    period = {"segments": [seg("2029-01-01", "2029-02-01", luck="甲子", sewun="丁卯"), seg("2029-02-02", "2029-02-02", luck="乙丑", sewun="丁卯"),
                           seg("2029-02-03", "2029-12-31", luck="乙丑", sewun="戊辰")]}
    out = V.segments_public(period)
    assert out[0]["note"] == "입춘 전: 전해의 기운이 적용되는 기간" and out[0]["before_ipchun"] is True
    assert out[1]["note"] == "이 날부터 10년 큰 흐름이 바뀜" and out[1]["before_ipchun"] is True                          # 입춘 전 기간 안의 대운 교체
    assert out[2]["note"] == "입춘부터 그해의 기운이 적용" and out[2]["before_ipchun"] is False
    # 입춘과 대운 교체가 같은 날이면 둘 다 말한다
    period = {"segments": [seg("2030-01-01", "2030-02-03", luck="甲子", sewun="己巳"), seg("2030-02-04", "2030-12-31", luck="乙丑", sewun="庚午")]}
    out = V.segments_public(period)
    assert out[0]["note"] == "입춘 전: 전해의 기운이 적용되는 기간" and out[1]["note"] == "입춘부터 그해의 기운이 적용 · 이 날부터 10년 큰 흐름도 바뀜"


# ---------------- 성질: 모든 합성 명식·연도의 모든 문장 ----------------
RNG = re.compile(r"(\d+)월 (\d+)일~(\d+)월 (\d+)일(\(입춘 전이라 전해의 기운이 적용되는 기간\))?")


def sentences(v):
    out = []
    for y, d in (v.get("detail") or {}).items():
        for b in d["blocks"]:
            out += [b["headline"]] + list(b["story"]) + list((b.get("why") or {}).get("period") or []) + list((b.get("why") or {}).get("natal") or [])
    for b in v.get("blocks") or []:
        out += [b["headline"]] + list(b["story"]) + list((b.get("why") or {}).get("period") or [])
    for r in (v.get("period") or {}).get("years", []):
        out += [r.get("change") or "", r.get("why") or "", r.get("caution") or ""]
    out += list((v.get("period") or {}).get("summary") or [])
    return out


@pytest.mark.parametrize("seed", [3, 4, 7, 44])
def test_no_sentence_says_a_range_is_before_ipchun_unless_it_ends_at_the_real_pre_ipchun_day(seed):
    checked = labeled = 0
    for ci in charts(6, seed=seed):
        pre, _ = C.pre_for(ci, [2026])
        a = agent.answer(pre, "종합", domains_=DOMS, years=[2026, 2027, 2028, 2029, 2030], depth="detailed")
        v = a["verdict"]
        ends = {}
        for p in a["periods"]:
            e = F.pre_ipchun_end(p["segments"])
            ends[p["year"]] = e
            assert e is not None and e[5:] in ("02-02", "02-03", "02-04")                                              # 입춘은 달력상 2월 3~5일(독립 확인)
        for y, d in v["detail"].items():
            ytxt = []
            for b in d["blocks"]:
                ytxt += [b["headline"]] + list(b["story"]) + list((b.get("why") or {}).get("period") or [])
            for t in ytxt:
                assert "입춘 전이라 전해의 기운이 적용되는 기간입니다" not in t                                        # 범위와 떨어져 붙던 옛 꼬리 문구
                for m in RNG.finditer(t):
                    a_, b_ = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}", f"{int(m.group(3)):02d}-{int(m.group(4)):02d}"
                    checked += 1
                    if m.group(5):
                        labeled += 1
                        assert f"{y}-{b_}" <= ends[int(y)], (y, t[:100], ends[int(y)])                                  # 입춘 전 설명이 붙은 범위는 입춘 전 기간 안에 있다
                    else:
                        assert f"{y}-{a_}" > ends[int(y)], (y, t[:120], ends[int(y)])                                    # 설명이 없는 범위는 입춘 전 기간과 겹치지 않는다
    assert checked > 0


def test_every_year_with_a_pre_ipchun_part_marks_the_first_public_segment():
    for ci in charts(6, seed=4):
        pre, _ = C.pre_for(ci, [2026])
        a = agent.answer(pre, "종합", domains_=["overall"], years=[2026, 2027, 2028, 2029, 2030], depth="detailed")
        for y, segs in a["verdict"]["segments"].items():
            assert segs[0]["note"] and segs[0]["note"].startswith("입춘 전") and segs[0]["before_ipchun"] is True, (y, segs[:2])
            assert segs[-1]["before_ipchun"] is False
            assert sum(s["days"] for s in segs) in (365, 366)


def test_period_text_for_a_known_three_segment_year_names_each_part_correctly():
    """입춘 + 대운 교체가 있는 해(합성 명식 seed 44 #5, 2026): 문장 안 모든 ‘입춘 전’ 범위가 1월 1일~2월 3일."""
    ci = list(charts(6, seed=44))[5]
    pre, _ = C.pre_for(ci, [2026])
    a = agent.answer(pre, "종합", domains_=DOMS, years=[2026], depth="detailed")
    segs = a["verdict"]["segments"]["2026"]
    assert [s["label"] for s in segs][0] == "1월 1일~2월 3일" and len(segs) == 3
    for t in sentences(a["verdict"]):
        for m in RNG.finditer(t):
            if m.group(5):
                assert (m.group(1), m.group(2), m.group(3), m.group(4)) == ("1", "1", "2", "3"), t[:120]


# ---------------- 구조화 신호(signals): 판정에 쓰인 구조 변화를 그대로 옮긴 것 ----------------
def test_signals_are_engine_structure_themes_without_duplicates_and_not_invented():
    from app.consult import synthesis as S
    shorts = {v["short"] for v in S.STRUCT.values()}
    for seed in (3, 44):
        for ci in charts(3, seed=seed):
            pre, _ = C.pre_for(ci, [2026])
            a = agent.answer(pre, "종합", domains_=DOMS, years=[2026, 2027, 2028], depth="detailed")
            for d in a["verdict"]["detail"].values():
                for b in d["blocks"]:
                    if "signals" not in b:
                        continue
                    sg = b["signals"]
                    assert set(sg) == {"support", "tension"}
                    for k in ("support", "tension"):
                        assert len(sg[k]) == len(set(sg[k])) and set(sg[k]) <= shorts                                          # 엔진 구조 이름 목록에서만, 중복 없음
