from app import report_checks as rc

GOOD = """## 성격
일간 옆 편재가 눈에 띕니다. [전통해석] (근거: 03 월령 우선)
## 재물
재성이 약한 편으로 읽힙니다. [현대추론]
격국용신, 억부용신, 조후용신은 각각 따로 봅니다.
명리학은 과학적으로 검증된 미래 예측 방법이 아닙니다.
"""


def test_ten_gods_matches_kb_examples():  # 14 S01 / 03 / 09 합성 예
    assert rc.ten_god("甲", "庚") == "七殺"
    assert rc.ten_god("甲", "辛") == "正官"
    assert rc.ten_god("甲", "己") == "正財"
    assert rc.ten_god("甲", "戊") == "偏財"
    assert rc.ten_god("甲", "丙") == "食神"
    assert rc.ten_god("甲", "甲") == "比肩"


def test_l01_detects_wrong_claim():
    assert rc.l01_ten_gods("甲", {"庚": "七殺"}).ok
    assert not rc.l01_ten_gods("甲", {"庚": "正官"}).ok


def test_l02_l03():
    assert rc.l02_hidden_stems({"寅": "甲丙戊"}).ok
    assert not rc.l02_hidden_stems({"寅": "甲"}).ok
    assert rc.l03_month_season("寅", "봄").ok
    assert not rc.l03_month_season("亥", "여름").ok


def test_l04_blocks_verified_claim_without_v1():
    assert not rc.l04_verification_claims("만세력으로 확인했습니다", "V2").ok
    assert rc.l04_verification_claims("만세력으로 확인했습니다", "V1").ok


def test_l05_blocks_luck_age_when_unset():
    assert not rc.l05_luck_numbers("대운은 8세부터 시작합니다", "unset").ok
    assert rc.l05_luck_numbers("대운은 산출하지 못했습니다", "unset").ok


def test_l06_l07_l12():
    assert rc.l06_three_yongshin(GOOD).ok
    assert not rc.l06_three_yongshin("용신은 木입니다").ok
    assert not rc.l07_forbidden("반드시 성공할 것입니다").ok
    assert rc.l12_disclaimer(GOOD)


def test_l08_requires_labels():
    assert rc.l08_labels(GOOD).ok
    assert not rc.l08_labels("## 재물\n재물이 많습니다.\n").ok


def test_l09_l10():
    assert rc.l09_quotes("「八字用神，專求月令」").ok
    assert not rc.l09_quotes("「甲木參天」").ok
    assert not rc.l10_held_quotes("청탁을 논할 때 「淸者」 라 했다").ok


def test_l11_checks_real_headings():
    assert rc.l11_source_refs("(근거: 06 월령에서 용신 구함)").ok
    assert not rc.l11_source_refs("(근거: 99 없는 항목)").ok


def test_good_report_passes_all_text_checks():
    assert all(f.ok for f in rc.run_text_checks(GOOD, "V2", "unset"))
