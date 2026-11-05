"""v11.2c 의미 중복·도식화 회귀: 기본 화면의 요약 단위들이 서로 같은 의미(글자 2-그램 유사도 0.4 이상)로 겹치지 않고, 건너뛴 문장은 접힘 안에 원문으로 남으며, 아이콘은 장식(aria-hidden)이고 제목이 의미를 전달한다. 합성 입력만 사용."""
import pytest

from tests.browser.test_dashboard import analyze
from tests.browser.test_motion import settle
from tests.browser.test_oneshot_ui import fill, one, open_page  # noqa: F401

pytestmark = pytest.mark.browser
PAIRS = """()=>{const g=t=>{const s=String(t).replace(/[\s·.,!?‘’“”()\-—:]/g,''),o=new Set();for(let i=0;i<s.length-1;i++)o.add(s.slice(i,i+2));return o};
  const dice=(a,b)=>{const A=g(a),B=g(b);if(!A.size||!B.size)return 0;let c=0;A.forEach(x=>{if(B.has(x))c++});return 2*c/(A.size+B.size)};
  const u=[document.querySelector('.concl-text').textContent,document.querySelector('.hero-sub').textContent];
  document.querySelectorAll('.chg-item').forEach(e=>u.push(e.querySelector(':scope > p').textContent));
  const out=[];for(let i=0;i<u.length;i++)for(let j=i+1;j<u.length;j++)out.push([i,j,dice(u[i],u[j]),u[i].slice(0,24),u[j].slice(0,24)]);return out}"""


def test_no_two_default_summaries_say_the_same_thing_in_any_year(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    for y in (2027, 2028, 2029, 2030, 2031):
        p.locator(f"#verdict .tl-node[data-year='{y}']").click()
        for i, j, d, a_, b_ in p.evaluate(PAIRS):
            assert d < 0.4, (y, a_, b_, d)                                                                               # 핵심 해석·보조·변화 카드는 서로 같은 의미를 되풀이하지 않는다
    ctx.close()


def test_skipped_change_candidates_are_still_readable_in_the_page(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    for y in (2027, 2029):
        p.locator(f"#verdict .tl-node[data-year='{y}']").click()
        res = p.evaluate("""()=>{const keys=(document.querySelector('.dash-changes').dataset.dropped||'').split('|').filter(Boolean);
          const all=document.getElementById('dash').textContent.replace(/\s+/g,'');return keys.filter(k=>all.indexOf(k)<0)}""")
        assert res == [], (y, res)                                                                                      # 건너뛴 문장은 해 패널(자세한 해석)에 그대로 있다
    p.locator("#verdict .tl-node[data-year='2027']").click()
    assert p.evaluate("(document.querySelector('.dash-changes').dataset.dropped||'').length") > 0                       # 2027년에는 실제로 겹치는 문장이 있어 건너뛴다
    ctx.close()


def test_change_cards_use_decorative_icons_with_text_titles_and_accordion_headers_preview_their_content(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    analyze(p)
    settle(p)
    p.locator("#verdict .tl-node[data-year='2027']").click()
    cards = p.locator(".dash-changes .chg-item")
    assert 1 <= cards.count() <= 3
    for i in range(cards.count()):
        ic = cards.nth(i).locator("h3 .chg-ic")
        assert ic.get_attribute("aria-hidden") == "true"                                                               # 아이콘은 장식
        title = cards.nth(i).locator("h3").inner_text().replace(ic.inner_text(), "").strip()
        assert len(title) >= 4                                                                                          # 의미는 글자 제목이 전달
    assert "핵심 해석 전문" in p.locator(".hero-more > summary").text_content() and "자세한 풀이" in p.locator(".hero-more > summary").text_content()
    p.locator("#verdict .dtab[data-domain=wealth]").click()
    assert "원문" in p.locator("#dash-dom-panel .dp-more > summary").text_content() and "근거" in p.locator("#dash-dom-panel .dp-more > summary").text_content()
    assert p.evaluate("document.querySelector('.hero-more').tagName") == "DETAILS"                                       # 네이티브 details: 펼침 상태가 보조기기에 전달되고 Enter/Space 로 열림
    ctx.close()
