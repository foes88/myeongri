"""슬라이딩 윈도우 rate limit(프로세스 메모리). 서버리스·다중 인스턴스에서는 공유 저장소(예: Redis) 구현이 필요하다 — 같은 인터페이스로 교체한다."""
from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, clock=time.time):
        self.clock, self.hits, self.lock = clock, {}, threading.Lock()

    def check(self, key: str, limit: int, window: float) -> tuple[bool, int]:
        """(허용 여부, 재시도까지 남은 초). 허용되면 호출을 기록한다."""
        now = self.clock()
        with self.lock:
            q = [t for t in self.hits.get(key, []) if now - t < window]
            if len(q) >= limit:
                self.hits[key] = q
                return False, max(1, int(window - (now - q[0])))
            q.append(now)
            self.hits[key] = q
            return True, 0

    def reset(self, key: str) -> None:
        with self.lock:
            self.hits.pop(key, None)
