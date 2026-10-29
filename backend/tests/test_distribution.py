"""공개 배포 점검: 재배포 불명확 자료 미추적, 데이터 파일 분류, 의존성 라이선스."""
import json

from tools import check_distribution as CD


def test_tracked_files_pass_distribution_check():
    assert CD.check() == []


def test_forbidden_and_unclassified_files_are_detected():
    man = json.loads(CD.MANIFEST.read_text(encoding="utf-8"))
    probs = CD.check(files=["backend/data_private/external/hko_lunar_terms.json", "backend/golden/new_table.json", "backend/data/de421.bsp"], manifest=man)
    text = " ".join(probs)
    assert "추적 금지 경로" in text and "매니페스트에 없는 데이터 파일: new_table.json" in text


def test_external_aggregate_cannot_hide_row_level_tables():
    man = json.loads(CD.MANIFEST.read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(man))
    bad["files"]["lunar_check.json"]["row_level"] = True
    assert any("row_level=false" in p for p in CD.check(files=[], manifest=bad))
    bad2 = json.loads(json.dumps(man))
    bad2["files"]["x.json"] = {"class": "EXTERNAL_RAW", "redistribution": "ok"}
    assert any("허용되지 않은 분류" in p for p in CD.check(files=[], manifest=bad2))


def test_sxtwl_and_unknown_license_dependencies_are_flagged(monkeypatch, tmp_path):
    man = json.loads(CD.MANIFEST.read_text(encoding="utf-8"))
    req = tmp_path / "requirements.txt"
    req.write_text("fastapi\nsxtwl\nmystery-lib\n", encoding="utf-8")
    monkeypatch.setattr(CD, "BACKEND", tmp_path)
    (tmp_path / "golden").mkdir()
    probs = CD.check(files=[], manifest=man)
    assert any("sxtwl" in p for p in probs) and any("mystery-lib" in p for p in probs)


def test_history_scanner_detects_forbidden_paths_and_birth_data(tmp_path, monkeypatch):
    import subprocess

    from tools import scan_history as SH
    r = tmp_path
    run = lambda *a: subprocess.run(["git", *a], cwd=r, check=True, capture_output=True)
    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    (r / "backend" / "data_private").mkdir(parents=True)
    (r / "backend" / "data_private" / "x.json").write_text("{}", encoding="utf-8")
    (r / "notes.md").write_text("생일 1990-05-05 10:30 입니다", encoding="utf-8")  # 의도적 탐지 대상(예시 표시 없음)
    run("add", "-A")
    run("commit", "-q", "-m", "x")
    monkeypatch.setattr(SH, "ROOT", r)
    res = SH.scan("HEAD")
    text = " ".join(res["problems"])
    assert "금지 경로" in text and "possible_birth_datetime" in text
