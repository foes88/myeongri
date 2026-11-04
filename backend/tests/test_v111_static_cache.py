"""로컬 서버의 화면 파일은 no-cache(ETag 재검증)로 내보낸다. 코드를 고친 뒤 새로고침해도 옛 화면이 남지 않게 하며, 변경이 없으면 304 로 가볍게 응답한다."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import NoCacheStaticFiles


def test_static_files_are_revalidated_not_blindly_cached(tmp_path):
    (tmp_path / "a.js").write_text("console.log(1)", encoding="utf-8")
    app = FastAPI()
    app.mount("/", NoCacheStaticFiles(directory=str(tmp_path), html=True))
    c = TestClient(app)
    r = c.get("/a.js")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache" and r.headers.get("etag")
    r2 = c.get("/a.js", headers={"If-None-Match": r.headers["etag"]})
    assert r2.status_code == 304                                                          # 바뀌지 않았으면 다시 받지 않는다
    (tmp_path / "a.js").write_text("console.log(2)", encoding="utf-8")
    r3 = c.get("/a.js", headers={"If-None-Match": r.headers["etag"]})
    assert r3.status_code == 200 and r3.text == "console.log(2)"                           # 바뀌면 새 파일
