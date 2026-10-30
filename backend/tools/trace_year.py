"""연도 판단의 근거 추적(개발자용): 결론이 규칙 그래프의 어느 노드·증거에서 나왔는지, v8.1 방식과 무엇이 다른지 보여 준다.
실행: python -m tools.trace_year [연도 ...]   (가상 입력 1984-06-15 10:00 수원, 분야 종합·재물·직업, 범위 2027~2031)"""
import sys

from app import main as M
from app.consult import agent
from app.consult import synthesis as S

sys.stdout.reconfigure(encoding="utf-8")
YEARS = [int(x) for x in sys.argv[1:]] or [2028, 2030]
RANGE = (2027, 2028, 2029, 2030, 2031)
DOMS = ("overall", "wealth", "career")


def main():
    b = M.OneshotBody(calendar="solar", birth_date="1984-06-15", birth_time="10:00", gender="male", birth_place="경기도 수원시", years=list(RANGE), domains=list(DOMS))  # 가상 입력
    pre = M._oneshot_pre(b)
    ans = agent.answer(pre, "x", domains_=list(DOMS), years=list(RANGE), depth="detailed")
    v = ans["verdict"]
    tr, dev = v["internal"]["trace"], v["internal"]["period_dev"]
    rel = S._relevant(["wealth", "career"])
    nm = {s["name"]: s for s in pre["natal_structure"]["layer3"]["structures"]}
    print(f"# 연도 판단 근거 추적 (범위 {RANGE[0]}~{RANGE[-1]}, 분야 종합·재물·직업)\n")
    print("규칙 버전", pre["ruleset_version"], "· 검증 상태", pre["verification"]["status"], "· 타고난 구조 등급", {n: nm[n]["rank"] for n in rel if n in nm}, "\n")
    print("연도별 가중 점수(두드러짐 판정 dev):", dev, "→ 두드러지는 해:", v["period"]["standout"], "\n")
    for y in YEARS:
        t = tr[str(y)]
        old = S.year_reading(next(p for p in ans["periods"] if p["year"] == y), rel, nm)
        old_dev_ups = len(old["ups"])
        print(f"## {y}년 (총 {t['total_days']}일)\n")
        for s in t["segments"]:
            print(f"- {s['from']}~{s['to']} ({s['days']}일) 대운 {s['luck']} · 세운 {s['sewun']}")
            print(f"  - 세운↔원국 관계: {', '.join(s['year_relations']) or '없음'} / 대운↔원국 관계: {', '.join(s['luck_relations']) or '없음'}")
            for d in s["deltas"]:
                print(f"  - 구조 변화 {d['structure']} {d['change']} ('{d['before']}' → '{d['after']}') · 노드 {d['claim_id']} · 규칙 {d['rule_id']}")
                print(f"    · 변화를 만든 운 글자: {', '.join(d['added_by']) or '(없음)'}")
            if not s["deltas"]:
                print("  - 구조 변화 없음")
        w = t["weighted"]
        print(f"\n가중 결과: 해 전체의 변화로 셈 {w['ups_major(해 전체의 변화로 셈)'] or '없음'} · 일부 기간만 {w['ups_partial(일부 기간만)'] or '없음'} · 대운 교체 {w['luck_split']} · 규칙 상태 {t['rule_status']}")
        print(f"v8.1 방식(구간 길이 무시)이었다면 변화로 센 구조 수: {old_dev_ups} → {'해 전체의 변화로 오인' if old_dev_ups and not w['ups_major(해 전체의 변화로 셈)'] else '동일'}")
        for blk in v["detail"][str(y)]["blocks"]:
            print(f"- 사용자 결론({blk['name']}): [{blk['tone_label']}] {blk['headline']}")
        row = next(r for r in v["period"]["years"] if r["year"] == y)
        print(f"- 기간 표 행: 두드러짐={row['standout']} · 변화=\"{row['change']}\" · 이유=\"{row['why']}\"\n")


if __name__ == "__main__":
    main()
