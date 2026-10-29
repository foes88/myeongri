"""브랜치 전체 이력 검사: 도달 가능한 모든 커밋의 모든 파일(blob)에서 금지 경로·개인정보·비밀 패턴을 검사한다.
실행: python -m tools.scan_history [<rev>=HEAD] [--forbidden-commit <sha>]  (종료코드 1 = 문제 있음)
"""
import re
import subprocess
import sys
from pathlib import Path

from app import privacy_scan as ps
from tools.check_distribution import FORBIDDEN

ROOT = Path(__file__).resolve().parents[2]


def git(*a, binary=False):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True)
    return r.stdout if binary else r.stdout.decode("utf-8", errors="replace")


def scan(rev="HEAD", forbidden_commits=()):
    problems = []
    commits = git("rev-list", rev).split()
    anc = [c for c in forbidden_commits if subprocess.run(["git", "merge-base", "--is-ancestor", c, rev], cwd=ROOT).returncode == 0]
    problems += [f"금지 커밋이 조상에 있음: {c}" for c in anc]
    seen = set()
    for c in commits:
        for line in git("ls-tree", "-r", c).splitlines():
            meta, path = line.split("\t", 1)
            sha = meta.split()[2]
            path = path.strip('"')
            if FORBIDDEN.search(path):
                problems.append(f"{c[:7]} 금지 경로: {path}")
            if (sha, path) in seen or Path(path).suffix.lower() not in ps.TEXT_SUFFIX:
                continue
            seen.add((sha, path))
            if any(path.startswith("/".join(d) + "/") for d in ps.SYNTHETIC_DATA_DIRS):
                hits = ps.scan_text(git("cat-file", "-p", sha), path, check_birth=False)
            else:
                hits = ps.scan_text(git("cat-file", "-p", sha), path)
            problems += [f"{c[:7]} {h}" for h in hits]
    return {"commits": len(commits), "blobs_scanned": len(seen), "problems": sorted(set(problems))}


if __name__ == "__main__":
    args = sys.argv[1:]
    fc = []
    if "--forbidden-commit" in args:
        i = args.index("--forbidden-commit")
        fc = [args[i + 1]]
        args = args[:i] + args[i + 2:]
    res = scan(args[0] if args else "HEAD", fc)
    print(res["commits"], "commits,", res["blobs_scanned"], "blobs;", "clean" if not res["problems"] else res["problems"][:10])
    sys.exit(1 if res["problems"] else 0)
