"""내부 Narrator(외부 호출·비용 없음). 근거 판단(key_judgments)을 상담 글의 흐름(큰 그림 → 시기 → 분야별 → 조건 → 유의점)으로 재구성한다.

- 판단 문장 자체는 바꾸지 않고(검증기가 문장 단위로 근거를 확인), 순서·단락·연결어·번호 매김을 바꿔 읽기 흐름을 만든다.
- 연결어는 문장 내용의 해시로 고르므로 결정론적이다(같은 입력=같은 출력). 새 사실·용어·연도·간지를 만들지 않는다.
- 질문 문장은 분야 단어(재물·직업 등) 일치로만 반영한다.
- narrator.Provider 인터페이스를 따르므로 같은 Claim Validator 와 fallback 을 거친다. 로컬 모델 제공자도 이 자리에 같은 방식으로 끼운다.
"""
from __future__ import annotations

import hashlib
import json
import re

from .narrator import NarratorResult, Usage, est_tokens

ORDINAL = ["첫째", "둘째", "셋째", "넷째", "다섯째"]
OPEN_FAV = ["먼저", "또", "아울러"]
OPEN_CAU = ["다만", "한편", "그렇지만"]
DOMAIN_WORDS = [(r"재물|돈|수입|월급", "재물"), (r"직업|직장|승진|커리어|이직", "직업"), (r"사업|창업", "사업"), (r"연애|결혼|배우자", "관계"), (r"가족|부모|자녀", "가족"), (r"집|부동산|계약|문서", "거처·문서")]
SKIP_OPEN = ("다만", "한편", "또한", "먼저", "끝으로", "원국에는", "아울러", "그렇지만")


def _pick(options: list[str], text: str) -> str:
    return options[int(hashlib.sha256(text.encode()).hexdigest(), 16) % len(options)]


def _strip(t: str) -> str:
    for o in SKIP_OPEN:
        if t.startswith(o + " "):
            return t[len(o) + 1:]
    return t


class InternalNarrator:
    name, model = "internal-composer", "composer-1"

    def generate(self, prompt: dict) -> NarratorResult:
        js = json.loads(re.search(r"<judgments>(.*)</judgments>", prompt["user"], re.S).group(1))
        q = re.search(r"<user_question>(.*?)</user_question>", prompt["user"], re.S)
        topics = [w for pat, w in DOMAIN_WORDS if q and re.search(pat, q.group(1))]
        by = lambda sec: [j for j in js if j["section"] == sec]
        out: list[dict] = []

        def add(text, claims):
            out.append({"text": text, "claim_ids": list(claims)})

        head = by("headline")
        if topics:
            add(f"질문하신 {'·'.join(dict.fromkeys(topics))} 흐름을 중심으로 정리합니다.", [])
        for i, j in enumerate(head):
            add(j["text"] if i == 0 else f"{_pick(OPEN_FAV, j['text'])} {_strip(j['text'])}", j["claim_ids"])
        fav = by("favorable")
        for i, j in enumerate(fav[:4]):
            add(f"{ORDINAL[i]}, {_strip(j['text'])}", j["claim_ids"])
        # 분야별(5단 해석): 의미 → 근거 → 현실 연결 → 반대 근거 → 범위
        names = list(dict.fromkeys(j["reading"] for j in js if j["section"].startswith("reading_")))
        for nm in names:
            brief = bool(topics) and len(names) > 3 and not any(w in nm for w in topics + ["종합"])  # 질문과 먼 분야는 의미·반대 근거만 남긴다(반대 근거는 지우지 않는다)
            part = {s: [j for j in js if j["section"] == s and j.get("reading") == nm] for s in ("reading_meaning", "reading_why", "reading_reality", "reading_counter", "reading_scope")}
            for j in part["reading_meaning"][:1]:
                add(f"[{nm}] {j['text']}", j["claim_ids"])
            for j in ([] if brief else part["reading_why"][:1]):
                add(j["text"], j["claim_ids"])
            for j in ([] if brief else part["reading_reality"][:1]):
                add(j["text"], j["claim_ids"])
            for j in part["reading_counter"]:
                add(f"{_pick(OPEN_CAU, j['text'])} {j['text']}.", j["claim_ids"])
            for j in ([] if brief else part["reading_scope"][:1]):
                add(j["text"], j["claim_ids"])
        for j in by("cautions"):
            add(f"{_pick(OPEN_CAU, j['text'])} {_strip(j['text'])}", j["claim_ids"])
        unc = by("uncertainty")
        for i, j in enumerate(unc):
            add(("끝으로, " if i == 0 else "") + j["text"], j["claim_ids"])
        txt = json.dumps(out, ensure_ascii=False)
        return NarratorResult(out, Usage(self.name, self.model, prompt["version"], est_tokens(prompt["system"] + prompt["user"]), est_tokens(txt)))
