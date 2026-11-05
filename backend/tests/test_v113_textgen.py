"""v11.3 종합운 문장 조합 수정: 10년 큰 흐름과 그해가 같은 기운을 들여오면 한 번만 말하고, 영역 이름은 ‘과’로 잇고, 화면용 story_parts 는 story 와 항상 같은 문장이다. 판정·톤은 바뀌지 않는다. 합성 입력만 사용."""
import re

import pytest

from app import cases as C
from app.consult import agent, explain as E
from tools.bias_probe import charts

DOMS = ["overall", "wealth", "career", "love_marriage", "family"]
KINDS = {"natal", "period", "relation", "relation2", "contrast", "counter", "timing", "cross", "emphasis", "where", "where2"}


def reason(evidence):
    period = {"segments": [{"from": "2027-01-01", "to": "2027-12-31", "struct_evidence": {"식상생재": evidence}}]}
    return E.period_reason(period, "식상생재", "능력이 수입으로 이어지는 흐름", {"ranges": [("2027-01-01", "2027-12-31")]})


def test_same_gods_from_luck_and_year_are_said_once_not_twice():
    t = reason(["대운간 丙(食神)", "세운간 丙(食神)"])
    assert "10년 큰 흐름과 그해가 함께 들여온 표현·기술의 기운" in t
    assert t.count("표현·기술의 기운") == 1                                                 # 같은 기운 이름을 되풀이하지 않는다
    assert "그해가 들여온" not in t and "10년 큰 흐름이 들여온" not in t


def test_different_gods_keep_their_own_source_and_read_naturally():
    t = reason(["대운간 丙(食神)", "세운간 戊(偏財)"])
    assert "10년 큰 흐름이 들여온 표현·기술의 기운" in t and "그해가 들여온 재물·현실 자원의 기운" in t
    assert "기운과 그해가 들여온" in t and t.count("과 ") <= 2                                  # 겹침이 없으면 ‘과’로 한 번 잇는다


def test_partial_overlap_is_split_into_shared_and_own_parts():
    t = reason(["대운간 丙(食神)", "대운간 戊(偏財)", "세운간 丙(食神)"])
    assert "10년 큰 흐름과 그해가 함께 들여온 표현·기술의 기운" in t and "10년 큰 흐름만 들여온 재물·현실 자원의 기운" in t
    assert "기운이 모두 타고난 사주의 기운과" in t                                            # ‘과’를 연달아 쓰지 않고 쉼표로 잇는다
    assert t.count("표현·기술의 기운") == 1 and t.count("재물·현실 자원의 기운") == 1


@pytest.mark.parametrize("seed", [3, 7, 44])
def test_story_parts_mirror_story_exactly_and_use_only_known_kinds_for_every_block(seed):
    for ci in charts(3, seed=seed):
        pre, _ = C.pre_for(ci, [2027])
        a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=[2027, 2028, 2029], depth="detailed")
        v = a["verdict"]
        for y, d in v["detail"].items():
            for b in d["blocks"]:
                if "story_parts" not in b:
                    continue                                                                   # 궁위 분야 블록은 칸 정보가 없다(화면은 story 를 그대로 쓴다)
                assert [p["text"] for p in b["story_parts"]] == b["story"], (y, b["domain"])   # 화면용 요약 데이터는 원문과 같은 문장·같은 순서
                assert {p["kind"] for p in b["story_parts"]} <= KINDS


@pytest.mark.parametrize("seed", [3, 7, 44])
def test_no_sentence_names_the_same_area_twice_with_a_dot_and_no_repeated_gods(seed):
    for ci in charts(3, seed=seed):
        pre, _ = C.pre_for(ci, [2027])
        a = agent.answer(pre, "종합 상담을 시작합니다", domains_=DOMS, years=[2027, 2028, 2029], depth="detailed")
        for d in a["verdict"]["detail"].values():
            for b in d["blocks"]:
                texts = list(b["story"]) + list((b.get("why") or {}).get("period") or []) + list((b.get("why") or {}).get("natal") or [])
                for t in texts:
                    assert not re.search(r"쪽\(태어난 [해달날시]\) · [^()]+쪽\(", t), t[:80]       # 영역 이름 사이를 ‘ · ’ 로 잇지 않는다
                    for god in ("표현·기술의 기운", "재물·현실 자원의 기운", "직책·규율의 기운", "압박·경쟁의 기운", "배움·보호의 기운"):
                        if "들여온" in t:
                            assert t.count(god) <= 1, (god, t[:120])                            # 같은 문장 안에 같은 기운 이름이 두 번 나오지 않는다

