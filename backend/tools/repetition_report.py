"""상담문 반복 분석(합성 명식 20개 × 연도 5개 × 분야 7개 = 단일 연도 결과). 같은 도구를 서로 다른 버전의 코드에 돌려 전후를 비교한다.
측정: 문장 다양성, 상위 반복 문장, 지목된 표현('큰 변화 없음'·'기회와 점검'·'한쪽으로만 읽지' 등)의 빈도, 같은 답변 안에서 분야 간 문장 겹침, 풀이 첫 문장 다양성.
실행: python -m tools.repetition_report   (출력: 마크다운)"""
import re
import sys
from collections import Counter

from app.consult import agent
from app.evaluation import dataset as DS
from tools.eval_synthesis import charts

sys.stdout.reconfigure(encoding="utf-8")
DOMS = ("wealth", "career", "business", "job_change", "docs_realestate", "love_marriage", "family")
YEARS = (2027, 2028, 2029, 2030, 2031)
PATTERNS = {"큰 변화 없음·크게 달라지지 않": r"크게 달라지지 않|큰 변화 없|눈에 띄게 달라지는 점이 없|눈에 띄는 변화가 없", "기회와 점검(결론 문구)": r"기회와 점검할 점",
            "한쪽으로만 읽지": r"한쪽으로만 읽지", "좋은 면만 보고 판단": r"좋은 면만 보고", "'다만 타고난 사주에도'": r"다만 타고난 사주에도", "타고난 사주에는 …(풀이 첫머리)": r"^타고난 사주에는"}


def sents(t: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.다요])\s+", t) if len(x.strip()) > 6]


def main():
    headlines, story_sents, openers, blocks = [], [], [], 0
    pat = Counter()
    overlap = []
    cross_dup = 0
    for name, p in charts():
        for y in YEARS:
            spec = DS.Spec(p, domains=("overall",) + DOMS, years=(y,), cycles_first_year=2000)
            pre = DS.pre_of(spec)
            a = agent.answer(pre, "x", domains_=["overall", *DOMS], years=[y], depth="detailed")
            bl = a["verdict"]["blocks"]
            per_block = []
            for b in bl:
                blocks += 1
                headlines.append(b["headline"])
                ss = sents(" ".join(b["story"]))
                story_sents += ss
                openers.append(b["story"][0][:8] if b["story"] else "")
                per_block.append(set(ss))
                text = b["headline"] + " " + " ".join(b["story"])
                for k, rx in PATTERNS.items():
                    pat[k] += len(re.findall(rx, text, flags=re.M))
                if re.match(PATTERNS["타고난 사주에는 …(풀이 첫머리)"], b["story"][0]):
                    pat["타고난 사주에는 …(풀이 첫머리)"] += 0
            allsent = [s for ps in per_block for s in ps]
            cross_dup += len(allsent) - len(set(allsent))
            for i in range(len(per_block)):
                for j in range(i + 1, len(per_block)):
                    u = per_block[i] | per_block[j]
                    overlap.append(len(per_block[i] & per_block[j]) / max(1, len(u)))
    c = Counter(story_sents)
    top = c.most_common(8)
    print("# 상담문 반복 분석\n")
    print(f"- 블록 수 {blocks} (명식 20 × 연도 {len(YEARS)} × 종합+분야 {len(DOMS) + 1})")
    print(f"- 서로 다른 결론 문장(headline) {len(set(headlines))}/{blocks} = {len(set(headlines)) / blocks:.2f}")
    print(f"- 풀이 문장 {len(story_sents)}개 중 서로 다른 문장 {len(c)}개 = {len(c) / len(story_sents):.2f}, 상위 8개 문장이 차지하는 비율 {sum(n for _, n in top) / len(story_sents):.2f}")
    print(f"- 같은 답변 안에서 분야끼리 겹치는 풀이 문장: 답변당 평균 {cross_dup / (20 * len(YEARS)):.2f}개, 분야 쌍 평균 겹침(Jaccard) {sum(overlap) / max(1, len(overlap)):.3f}")
    print(f"- 풀이 첫 문장 앞 8글자 종류 {len(set(openers))}/{blocks}")
    print("\n지목 표현의 100블록당 빈도\n")
    for k, v in pat.items():
        print(f"- {k}: {v * 100 / blocks:.1f}")
    print("\n상위 반복 문장\n")
    for s, n in top:
        print(f"- ({n}회) {s[:90]}")


if __name__ == "__main__":
    main()
