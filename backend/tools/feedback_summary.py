"""개인용 앱에 남긴 본인 평가(1~5점·메모)의 요약. 해석 내용·출생 정보는 읽지 않고 점수와 개수만 센다(암호화된 평가 기록만 복호화).
사용: python -m tools.feedback_summary   (서버와 같은 DATABASE_URL / APP_DB / APP_DATA_KEY 환경변수). 이 요약은 개인 사용 기록이며 상담 품질 검증이 아니다."""
from __future__ import annotations

import json
import sys
from collections import Counter

from app.accounts import api as A


def summarize(repo=None) -> dict:
    repo = repo or A.repo()
    users = getattr(repo, "all_user_ids", None)
    ids = users() if users else []
    ratings, by_target, notes = [], Counter(), 0
    for uid in ids:
        for r in repo.list_reports(uid):
            for t in repo.get_turns(uid, r["id"]):
                if t["kind"] != "feedback":
                    continue
                b = t["body"]
                ratings.append(b.get("rating"))
                by_target[b.get("target", "reading")] += 1
                notes += bool(b.get("note"))
    n = len(ratings)
    dist = Counter(ratings)
    return {"feedback_count": n, "mean_rating": round(sum(ratings) / n, 2) if n else None, "distribution": {k: dist.get(k, 0) for k in range(1, 6)}, "by_target": dict(by_target), "with_note": notes,
            "status": "기록 없음(미평가)" if not n else "개인 사용 기록 — 상담 품질 검증이 아님"}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(summarize(), ensure_ascii=False, indent=1))
