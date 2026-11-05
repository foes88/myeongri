"""분야 '전체 선택': 모두 켜기/끄기, 일부만 고르면 중간 상태, 개별 해제 시 전체 선택 해제. 합성 입력만 사용."""
import pytest

from tests.browser.test_oneshot_ui import one, open_page  # noqa: F401

pytestmark = pytest.mark.browser


def test_select_all_toggles_every_domain_and_follows_individual_choices(browser, one):
    ctx, p, reqs, console = open_page(browser, one, "1440")
    n = p.locator("#doms input").count()
    assert n == 11
    p.check("#doms-all")
    assert p.locator("#doms input:checked").count() == n
    p.uncheck("#doms-all")
    assert p.locator("#doms input:checked").count() == 0
    p.check("#doms input[value=wealth]")
    assert p.evaluate("document.getElementById('doms-all').indeterminate") is True and not p.is_checked("#doms-all")
    p.check("#doms-all")
    p.uncheck("#doms input[value=luck]")
    assert not p.is_checked("#doms-all") and p.evaluate("document.getElementById('doms-all').indeterminate") is True
    assert p.evaluate("document.getElementById('doms-all').getBoundingClientRect().height") >= 44
    ctx.close()
