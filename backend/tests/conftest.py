"""백엔드 테스트 공통 설정. 기본 API 응답은 사용자용(결론형)이라 내부 근거가 없다. 기존 엔진·API 시험은 내부 근거가 필요하므로 EXPOSE_INTERNAL=1 로 실행하고,
사용자용 응답을 확인하는 시험(@pytest.mark.public_view)은 이 값을 끈다. 브라우저 시험은 별도 서버를 사용자용 응답 그대로 띄운다."""
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "public_view: 사용자용(내부 근거 제외) API 응답을 확인하는 시험 — EXPOSE_INTERNAL 을 끈다")


@pytest.fixture(autouse=True)
def _internal_exposed_for_engine_tests(request, monkeypatch):
    if request.node.get_closest_marker("browser"):
        return
    if request.node.get_closest_marker("public_view"):
        monkeypatch.delenv("EXPOSE_INTERNAL", raising=False)
    else:
        monkeypatch.setenv("EXPOSE_INTERNAL", "1")
