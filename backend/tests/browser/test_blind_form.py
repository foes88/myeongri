"""평가 폼(독립 HTML) 브라우저 테스트: 입력 → 자동 저장 → CSV 내려받기 → 집계. 응답 값은 도구 검증용 가짜."""
import csv
import io
import json
import re

import pytest

from app import blind_eval as BE
from tools import blind_eval as T

pytestmark = pytest.mark.browser
ITEMS = [{"item_id": f"c{i}", "question": f"질문 {i}", "years": [2030], "domains": ["overall"], "variants": {"v70": f"문장 A{i}\n둘째 줄", "v81": f"문장 B{i}", "v82": f"문장 C{i}"}} for i in range(12)]


@pytest.fixture()
def form(tmp_path):
    pk, key = BE.build_packet(ITEMS)
    f = tmp_path / "rater_form.html"
    f.write_text(T.FORM.replace("__PACKET__", json.dumps(pk, ensure_ascii=False)), encoding="utf-8")
    return f, pk, key


@pytest.mark.parametrize("size", [(360, 800), (1440, 900)])
def test_form_fill_autosave_export_and_aggregate(browser, form, size):
    f, pk, key = form
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, accept_downloads=True)
    p = ctx.new_page()
    reqs = []
    p.on("request", lambda r: reqs.append(r.url))
    p.goto(f.as_uri())
    assert "명리학을 몰라도 됩니다" in p.inner_text("body") and p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    p.fill("#rid", "평가자1")
    for i in range(10):
        sec = p.locator("section.box").nth(i)
        for k, sel in enumerate(sec.locator("select").all()):
            sel.select_option("4" if k % 5 != 2 else "5")
        sec.locator("input[type=radio]").nth(i % 3).check()
        sec.locator("textarea").fill(f"이유 {i}: 이해하기 쉬웠다")
    assert "완료 10 / 12" in p.inner_text("#prog")
    p.reload()  # 자동 저장: 새로고침해도 입력이 남는다
    assert "완료 10 / 12" in p.inner_text("#prog") and p.locator("section.box").first.locator("textarea").input_value().startswith("이유 0")
    p.fill("#rid", "평가자1")
    with p.expect_download() as dl:
        p.get_by_role("button", name=re.compile(r"내려받기\(CSV\)")).click()
    text = open(dl.value.path(), encoding="utf-8-sig").read()
    rows = list(csv.DictReader(io.StringIO(text)))
    assert list(rows[0].keys()) == BE.CSV_COLUMNS and len(rows) == 10 * 3 and {r["rater_id"] for r in rows} == {"평가자1"}
    assert sum(1 for r in rows if r["preferred"] == "1") == 10 and all(r["reason"] for r in rows if r["preferred"] == "1")
    ratings = BE.ratings_from_csv(text)
    agg = BE.aggregate(pk, key, ratings)
    assert agg["raters"] == {"general": 1} and not agg["rejected"] and agg["n_preferences"] == 10
    assert BE.pilot_gate(agg)["status"] == "진행 중"            # 1명이므로 파일럿 미완료
    assert not [u for u in reqs if not u.startswith("file:")]   # 네트워크 요청 없음(서버 전송 없음)
    ctx.close()


def test_export_requires_a_rater_id_and_warns_when_fewer_than_ten(browser, form):
    f, pk, key = form
    ctx = browser.new_context(accept_downloads=True)
    p = ctx.new_page()
    msgs = []
    p.on("dialog", lambda d: (msgs.append(d.message), d.dismiss()))
    p.goto(f.as_uri())
    p.get_by_role("button", name=re.compile(r"내려받기\(CSV\)")).click()
    assert any("별명" in m for m in msgs)
    p.fill("#rid", "평가자2")
    sec = p.locator("section.box").first
    for sel in sec.locator("select").all():
        sel.select_option("3")
    sec.locator("input[type=radio]").first.check()
    p.get_by_role("button", name=re.compile(r"내려받기\(CSV\)")).click()
    assert any("완료한 항목이 1개" in m for m in msgs)  # 10개 미만이면 확인을 묻고, 취소하면 내려받지 않는다
    ctx.close()
