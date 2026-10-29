"""고전 규칙 원문 위치 검증 도구(네트워크 필요). 실행: python -m tools.verify_classical [--refresh]

- 공개 전사본 페이지를 내려받아(저장소에는 저장하지 않음, 캐시는 임시 폴더) 규칙별 핵심어가 실제로 나타나는지 확인하고
  짧은 발췌(최대 40자)만 golden/classical_verification.json 에 기록한다.
- 자동 키워드 일치는 'location_confirmed' 까지만 부여한다. 'text_confirmed' 는 사람이 발췌를 읽고 판단한 항목을
  tools/verify_classical.py 의 HUMAN 에 근거 발췌와 함께 명시했을 때만 부여한다.
- 접속 실패 출처는 failed_sources 에 기록하고 해당 규칙은 pending 으로 둔다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "golden" / "classical_verification.json"
ACCESSED = "2026-10-29"
CACHE = Path(tempfile.gettempdir()) / "myeongri_classical_cache"

SOURCES = {
    "dt": ("滴天髓", "https://zh.wikisource.org/zh-hant/滴天髓"),
    "ren": ("滴天髓闡微(任鐵樵 注)", "https://zh.wikisource.org/zh-hant/滴天髓闡微"),
    "zp": ("子平真詮 卷一·八 論用神", "https://donglishuzhai.net/chapter/3721.html"),
    "zpc": ("子平真詮 卷一·九 成敗救應", "https://m.donglishuzhai.net/chapter/3722.html"),
    "zpv": ("子平真詮評註(徐樂吾 평주 포함)", "https://libokang.com/zh-hant/classics/bazi/子平真詮評註/"),
    "qt": ("窮通寶鑑", "https://zh.wikisource.org/zh-hant/窮通寶鑑"),
    "yh": ("淵海子平", "https://zh.wikisource.org/zh-hant/淵海子平"),
    "sm": ("三命通會 卷三", "https://zh.wikisource.org/zh-hant/三命通會/卷三"),
}

# ---- 규칙별 확인 명세 ------------------------------------------------------------------------------
# loc: 위치 확인(자동) = (출처코드 목록, 핵심어(여러 글자), 절 이름)
# human: 사람이 읽고 확인한 구절 = (출처코드, 원문 그대로의 발췌(<=40자), is_commentary, 범위·한계 메모)
#   발췌가 실제 페이지 텍스트에 그대로 있지 않으면 text_confirmed 로 인정하지 않는다(자동 강등).
CONV = {"MG-L1-SUPPORT-ORDINAL", "MG-L3-CHAIN", "MG-L4-YONGSHIN-CONFLICT", "MG-L5-STRUCTURE-DELTA", "MG-L5-SEGMENT", "MG-L5-COMPARE"}
LOC = {
    "MG-L1-DEUKRYEONG-BONGI": (["dt"], ["氣象得令者吉"], "月令論(令星得令)"),
    "MG-L2-PA": (["sm"], ["皆相破"], "三命通會 卷三 破煞"),
    "MG-L2-HAE": (["ren"], ["六害由六合而來"], "滴天髓闡微(任氏曰) 刑沖害論"),
    "MG-L2-HYUNG": (["zpv"], ["三刑也"], "論刑沖會合解法"),
}
HUMAN = {
    "MG-L1-WOLRYEONG": ("dt", "月令提綱，譬之宅也，人元用事之神，宅之向也", False, "月令=提綱 개념 확인. 이 구현의 '월령 사실 기록' 범위와 일치."),
    "MG-L1-HIDDEN-ROLE": ("dt", "立春後七日前，皆值戊土用事，八日後十四日前，丙火用事，十五日後，甲木用事", False,
                          "寅月 한 예(戊→丙→甲, 즉 여기→중기→본기 순)만 확인. 12지 전체 표와 사령 일수는 이 구현이 사용하지 않으며 확인하지 않음."),
    "MG-L1-TONGGEUN": ("ren", "干無壬癸，地支有寅卯以通根", True, "任氏曰(주석). 천간 木에 지지 寅卯=통근. 지장간 동일글자 엄격/관대 구분, 강·중·약 등급은 구현 규약. 沈孝瞻 원문은 長生·祿·旺·庫를 有根으로 봄(十二運 기준, 미구현)."),
    "MG-L1-TUGAN": ("zpv", "不透甲而透丙，則如知府不臨郡，而同知得以作主", False, "투출 여부가 작용하는 글자를 바꾼다는 내용 확인. 연·월·시간만 보고 일간 제외하는 세부 규칙은 구현 규약."),
    "MG-L2-STEM-HAP": ("zpv", "乙庚化金次之；金生水，故丙辛化水又次之；水生木，故丁壬化木又次之", False, "甲己土·乙庚金·丙辛水·丁壬木·戊癸火 5쌍 확인(同節 前문 甲己 포함)."),
    "MG-L2-BRANCH-YUKHAP": ("zpv", "合者，六合也，子與丑合之類是也", False, "六合 개념과 대표쌍(子丑)만 확인. 6쌍 전체 나열은 이 구절에 없음."),
    "MG-L2-SAMHAP": ("zpv", "會者，三會也，申子辰之類是也", False, "원문은 申子辰을 '三會'로 부름(평주는 三合會局으로 풀이). 용어 차이 있음. 반합·공합의 인정 범위는 확인하지 않음."),
    "MG-L2-CHUNG": ("zpv", "沖者，六沖也，子午卯酉之類是也", False, "六沖 개념과 대표쌍(子午·卯酉)만 확인."),
    "MG-L2-GOGO": ("zpv", "財官入庫不沖不發——此說雖俗書盛稱之，然子平先生造命，無是說也", False, "원문은 '庫는 반드시 沖해야 연다'는 속설을 부정하고 沖이 오히려 印을 해칠 수 있다고 함 → 개고 성립이 학파 논쟁이라는 본 규칙의 처리와 부합. 辰=水庫 등 庫 대응표 자체는 별도 구절."),
    "MG-L2-COMPETITION": ("zpv", "刑沖俱非美事，而三合六合，可以解之", False, "원문은 합이 충·형을 푼다는 입장(합 우선설). 본 규칙의 '합 우선/충 우선/인접·월령 우선' 중 합 우선설만 직접 뒷받침. 나머지 학설은 확인하지 않음."),
    "MG-L3-SIKSANG-SAENGJAE": ("zpv", "食神生財，或食帶煞而無財，棄食就煞而透印，食格成也", False, "食神生財→食格成. 傷官生財→傷官格成도 같은 절에 있음."),
    "MG-L3-JAE-SAENGGWAN": ("zpv", "如財旺生官，美格也，身弱透官，即為破格", False, "財旺生官=美格이나 身弱이면 破格(반례)이라는 점까지 확인."),
    "MG-L3-GWAN-INSAENG": ("zpv", "印輕逢煞，或官印雙全，或身印兩旺而用食傷洩氣", False, "官印雙全이 印格成의 한 형태로 나옴. '관인상생'이라는 용어 자체는 任氏曰(滴天髓闡微)에 있음."),
    "MG-L3-SAL-INSAENG": ("ren", "甲申戊寅，真為殺印相生", False, "滴天髓 원문 구절(原註 앞). 殺印相生 용어와 사례. 殺強身弱에 印綬化殺은 任氏曰."),
    "MG-L3-SANGGWAN-GYEONGWAN": ("zpv", "傷官見官，為格之忌，透財而地位配置合宜，則傷官生財來生官，反可以解", False, "상관견관=格忌이며 財가 통관하면 해소된다는 구응까지 확인(본 규칙의 반대 근거 처리와 부합)."),
    "MG-L3-GUNGEOP-JAENGJAE": ("zpv", "財輕比重，財透七煞，財格敗也", False, "財輕比重=財格敗 확인. '群劫爭財' 용어는 任氏曰 사례 구절(commentary_excerpt)에 있음. 구응(食傷으로 化)은 救應 절 '財逢劫而透食以化之'."),
    "MG-L4-GYEOKGUK-CAND": ("zpv", "不透甲而透丙，則如知府不臨郡，而同知得以作主", False, "본기 미투출 시 중기 투출이 용신이 되는 '用神變化' 확인. 투출 우선 순서의 모든 세부 규칙은 구현 단순화."),
    "MG-L4-SEONGPA": ("zpv", "何謂成？如官逢財印，又無刑沖破害，官格成也", False, "沈孝瞻 成敗救應 절이 격별 成/敗/救應 조건표를 직접 제시. 구현 조건표는 이를 단순화(예: 刑沖破害·合煞 등 세부 생략)한 것으로 원문과 동일하지 않음."),
    "MG-L4-GEUKGUK-YONGSHIN": ("zpv", "用神專尋月令，以四柱配之，必有成敗", False, "격국용신=월령에서 구함 확인. 억부·조후용신과 분리한다는 점은 후대 구분."),
    "MG-L4-EOKBU-YONGSHIN": ("zpv", "日元強者抑之，日元弱者扶之，此以扶抑為用神也", True, "徐樂吾 평주의 용신 5분류 중 (一)扶抑. 沈孝瞻 원문이 아니라 20세기 평주. 강/약 후보 판정 규칙은 구현 규약."),
    "MG-L4-JOHU-DIRECTION": ("dt", "金水為寒，木火為暖，得氣之寒，遇暖而發", False, "寒暖論 원문. 한난 방향 개념 확인. 窮通寶鑑 일간×월지 개별 표는 확인·구현하지 않음. 평주(徐樂吾)의 調候 분류도 존재."),
    "MG-L5-LUCK-STEM": ("zpv", "取運則又以運之干，配八字之喜忌", False, "운의 간을 원국 喜忌에 맞춰 본다는 내용 확인. 주의: 현재 엔진은 이 rule_id 를 쓰는 claim 노드를 만들지 않음(규칙만 등록)."),
    "MG-L5-LUCK-BRANCH": ("zpv", "運中每運行一字，即必以此一字，配命中干支而統觀之", False, "운 글자를 원국 간지와 함께 본다는 일반 원칙 확인. 합충 세부 분류는 Layer 2 규칙 참조."),
}
# 학파별 적용 조건(요약)
SCHOOL = {
    "MG-L1-WOLRYEONG": "공통. 월지 확정(절입 모호성 없음)이 전제.",
    "MG-L1-DEUKRYEONG-BONGI": "본기 비겁/인성이면 득령. 중기·여기만 돕는 경우는 학파별 '부분득령' 논쟁.",
    "MG-L1-DEUKRYEONG-SEASON": "계절 오행 기준. 토월 처리는 학파 차이.",
    "MG-L1-HIDDEN-ROLE": "지장간 표 판본 이견(knowledge/15 I07). 사령 일수 적용 여부는 학파 차이(이 구현은 미적용).",
    "MG-L1-TONGGEUN": "엄격(같은 간)/관대(같은 오행)/십이운성 기준이 갈림(이 구현은 앞 둘만).",
    "MG-L1-TUGAN": "월지 지장간이 연·월·시간에 나타나면 투출. 일간 처리·암장 가중은 학파 차이.",
    "MG-L1-SUPPORT-ORDINAL": "억부론 관점의 구현 규칙. 기세론·종격 관점에서는 달리 판정 가능.",
    "MG-L2-STEM-HAP": "공통(5쌍). 인접 여부와 작용은 학파 차이.",
    "MG-L2-HAP-HWA": "인접·월령·화신 뿌리·경합·극신 조건 중 어떤 것을 필수로 보는지 학파 차이. 일간 합화 허용 여부 논쟁.",
    "MG-L2-BRANCH-YUKHAP": "午未 합의 화신(火/土) 논쟁.",
    "MG-L2-SAMHAP": "완전 삼합/반합/공합 인정 범위 학파 차이.",
    "MG-L2-BANGHAP": "2글자 방합 인정 여부 논쟁.",
    "MG-L2-CHUNG": "충이 지장간 손상·개고를 뜻하는지 학파 차이. 이 구현은 존재만 기록.",
    "MG-L2-HYUNG": "삼형 완성 여부, 2글자 형 인정, 자형 인정이 학파 차이. 원문 저자도 三刑에 대해 闕疑(존치)라 함.",
    "MG-L2-PA": "三命通會는 寅亥·巳申을 三合/六合이라 破로 취하지 않음 → 본 구현 표(6쌍)와 불일치. 학파 차이.",
    "MG-L2-HAE": "任氏曰은 害(穿)에 회의적. 寅亥/寅巳 분류가 자료마다 다름.",
    "MG-L2-GOGO": "충=개고설/충=손상설/형·합으로도 연다는 설. 원문(沈孝瞻)은 必沖 속설 부정.",
    "MG-L2-COMPETITION": "합이 충을 푼다(원문) / 충이 합을 깬다 / 인접·월령 우선 — 학파 차이.",
    "MG-L3-SIKSANG-SAENGJAE": "편인도식 시 해소 여부, 군겁 시 성립 여부는 학파 차이.",
    "MG-L3-JAE-SAENGGWAN": "身弱이면 破格(원문), 비겁 탈재 시 성립 여부.",
    "MG-L3-GWAN-INSAENG": "財破印, 傷官克官 시 성립 여부는 학파 차이.",
    "MG-L3-SAL-INSAENG": "食神制殺 경로와 병존 시 우선순위 논쟁. 財滋弱殺 여부.",
    "MG-L3-SANGGWAN-GYEONGWAN": "印으로 제어(傷官佩印) / 財로 통관(傷官生財) 구응이 모두 있음. 金水傷官은 예외로 보는 설(원문 敗 절).",
    "MG-L3-GUNGEOP-JAENGJAE": "官殺로 제겁 / 食傷으로 化劫生財 / 신약이면 비겁이 용신이라는 억부론.",
    "MG-L3-CHAIN": "구현 규약.",
    "MG-L4-GYEOKGUK-CAND": "투출 우선(沈孝瞻 用神變化) vs 본기 중심 vs 인원사령(일수) — 학파 차이. 건록·양인은 외격 별도.",
    "MG-L4-GYEOKGUK-BONGI": "본기 중심 설(구현상 병렬 대안).",
    "MG-L4-SEONGPA": "격별 成敗救應 조건. 구현은 단순화 표.",
    "MG-L4-GEUKGUK-YONGSHIN": "월령 중심 격국용신.",
    "MG-L4-EOKBU-YONGSHIN": "억부론(扶抑). 강약 후보 규칙은 구현 규약.",
    "MG-L4-JOHU-DIRECTION": "조후론. 일간×월지 개별 표(窮通寶鑑)는 미구현.",
    "MG-L4-YONGSHIN-CONFLICT": "구현 규약(합치지 않는다는 원칙).",
    "MG-L5-LUCK-STEM": "운 천간 해석 — 규칙만 등록, 노드 미생성.",
    "MG-L5-LUCK-BRANCH": "운 지지와 원국의 합충 — 인접 개념 적용 여부는 학파 차이.",
    "MG-L5-STRUCTURE-DELTA": "구현 규약.", "MG-L5-SEGMENT": "구현 규약(대운 교체일·입춘 분리).", "MG-L5-COMPARE": "구현 규약(점수 없는 비교).",
}
CASES = json.loads(r'''
{
 "MG-L1-DEUKRYEONG-BONGI": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L1-DEUKRYEONG-SEASON": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L1-TONGGEUN": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L1-TUGAN": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L1-WOLRYEONG": {
  "pos": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  }
 },
 "MG-L2-BANGHAP": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L2-BRANCH-YUKHAP": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L2-CHUNG": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "戊寅",
   "month": "辛酉",
   "day": "壬寅",
   "hour": "癸卯"
  }
 },
 "MG-L2-COMPETITION": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "己亥",
   "month": "丁巳",
   "day": "庚戌",
   "hour": "癸丑"
  }
 },
 "MG-L2-GOGO": {
  "neg": {
   "year": "戊寅",
   "month": "辛酉",
   "day": "壬寅",
   "hour": "癸卯"
  },
  "pos": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  }
 },
 "MG-L2-HAE": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "癸丑",
   "month": "乙未",
   "day": "壬子",
   "hour": "癸丑"
  }
 },
 "MG-L2-HAP-HWA": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "丙辰",
   "month": "辛酉",
   "day": "丁未",
   "hour": "乙未"
  }
 },
 "MG-L2-HYUNG": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L2-PA": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L2-SAMHAP": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "己巳",
   "month": "己丑",
   "day": "辛酉",
   "hour": "辛丑"
  }
 },
 "MG-L2-STEM-HAP": {
  "neg": {
   "year": "己亥",
   "month": "丁巳",
   "day": "庚戌",
   "hour": "癸丑"
  },
  "pos": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  }
 },
 "MG-L3-GUNGEOP-JAENGJAE": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "己卯",
   "month": "辛丑",
   "day": "戊戌",
   "hour": "壬申"
  }
 },
 "MG-L3-GWAN-INSAENG": {
  "neg": {
   "year": "辛丑",
   "month": "壬辰",
   "day": "己卯",
   "hour": "甲子"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L3-JAE-SAENGGWAN": {
  "neg": {
   "year": "己巳",
   "month": "己丑",
   "day": "辛酉",
   "hour": "辛丑"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L3-SAL-INSAENG": {
  "neg": {
   "year": "癸丑",
   "month": "乙未",
   "day": "壬子",
   "hour": "癸丑"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L3-SANGGWAN-GYEONGWAN": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "己亥",
   "month": "丁巳",
   "day": "庚戌",
   "hour": "癸丑"
  }
 },
 "MG-L3-SIKSANG-SAENGJAE": {
  "neg": {
   "year": "壬午",
   "month": "癸巳",
   "day": "癸酉",
   "hour": "庚申"
  },
  "pos": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  }
 },
 "MG-L4-EOKBU-YONGSHIN": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L4-GEUKGUK-YONGSHIN": {
  "neg": {
   "year": "己亥",
   "month": "庚寅",
   "day": "甲寅",
   "hour": "庚子"
  },
  "pos": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  }
 },
 "MG-L4-GYEOKGUK-BONGI": {
  "pos": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  }
 },
 "MG-L4-GYEOKGUK-CAND": {
  "neg": {
   "year": "己亥",
   "month": "庚寅",
   "day": "甲寅",
   "hour": "庚子"
  },
  "pos": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  }
 },
 "MG-L4-JOHU-DIRECTION": {
  "neg": {
   "year": "辛未",
   "month": "甲申",
   "day": "丙申",
   "hour": "丙申"
  },
  "pos": {
   "year": "乙巳",
   "month": "己未",
   "day": "庚午",
   "hour": "庚申"
  }
 },
 "MG-L4-SEONGPA": {
  "neg": {
   "year": "癸丑",
   "month": "乙未",
   "day": "壬子",
   "hour": "癸丑"
  },
  "pos": {
   "year": "戊寅",
   "month": "辛酉",
   "day": "壬寅",
   "hour": "癸卯"
  }
 }
}
''')


def fetch(code: str, refresh: bool = False) -> tuple[str | None, str]:
    name, url = SOURCES[code]
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"{code}.txt"
    if f.exists() and not refresh:
        return f.read_text(encoding="utf-8"), ""
    try:
        q = urllib.parse.quote(url, safe=":/?=&%")
        r = urllib.request.urlopen(urllib.request.Request(q, headers={"User-Agent": "Mozilla/5.0"}), timeout=30)
        html = r.read().decode("utf-8", errors="replace")
        html = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))
        f.write_text(txt, encoding="utf-8")
        return txt, ""
    except Exception as e:  # noqa: BLE001
        return None, repr(e)[:120]


def excerpt(txt: str, kw: str, width: int = 40) -> str:
    i = txt.find(kw)
    return txt[max(0, i - width // 2): i + width // 2][:width] if i >= 0 else ""


def _norm(t: str) -> str:
    return re.sub(r"\s+", "", t)


EXTRA_COMMENTARY = {"MG-L3-GUNGEOP-JAENGJAE": ("ren", "原局無食傷之化，群劫爭財"),
                    "MG-L3-SAL-INSAENG": ("ren", "殺強身弱，則以印綬化殺"),
                    "MG-L3-GWAN-INSAENG": ("ren", "官印相生，日主休囚，喜印緩而不喜比劫")}

# ---- v6.6 심화 조사(2026-10-29): 위치만 확인되던 8개 중 4개를 '범위 한정 text_confirmed' 로 승격. 나머지 4개(BONGI/HYUNG/PA/HAE)는
#      원문이 규칙을 부정·보류·다른 기준으로 서술하므로 location_confirmed 유지(content_gap 기록).
HUMAN.update({
    "MG-L2-BANGHAP": ("dt", "方是方兮局是局，方要得方莫混局", False,
                      "滴天髓 方局論 원문 구절: 方(방합)과 局(삼합)을 구분하고 섞지 말라. 方의 구성(寅卯辰 등 4조)은 任氏曰(commentary_excerpt)이 나열. 2글자 방합(부분)은 원문에 없음(엔진은 contested 로만 기록).",
                      "滴天髓 方局論"),
    "MG-L2-HAP-HWA": ("zpv", "譬如甲與己合，而甲己中間，以庚間隔之", False,
                      "沈孝瞻 論十干合而不合: 사이에 합 상대를 극하는 글자가 끼면 합이 안 됨(間隔), 멀리 떨어지면 半合. 論外格用舍(從化): 化는 得時乘令·四支局全이 요건(additional_excerpts). 쟁합·극신 천간 조건은 원문 확인 못함(구현자 보강).",
                      "論十干合而不合"),
    "MG-L1-DEUKRYEONG-SEASON": ("zpv", "春木夏火秋金冬水為得時，比劫印綬通根扶助為黨眾", True,
                                "徐樂吾 평주(논십간득시불왕실시불약): 春木夏火秋金冬水=得時(월령 오행이 일간과 같음). 단 得時=旺일 뿐 強은 아님. 엔진이 추가로 '월령이 일간을 생해도 득령 근거'로 보는 부분은 확인 못함.",
                      "論十干得時不旺失時不弱(평주)"),
    "MG-L4-GYEOKGUK-BONGI": ("zpv", "即以寅論，甲為本主，如郡之有府", False,
                             "沈孝瞻 論用神變化: 본기(甲)=本主. 단 본기 불투출·중기 투출이면 중기가 作主(additional_excerpts). 엔진의 '항상 본기로 격 이름' 대안은 원문이 아니라 병렬 대안이며 원문 규칙은 MG-L4-GYEOKGUK-CAND(투출 우선)와 일치.",
                      "論用神變化"),
})
EXTRA_COMMENTARY.update({  # 주석부 보강(원문 구절은 HUMAN)
    "MG-L2-BANGHAP": ("ren", "支得寅卯辰、巳午未、申酉戌、亥子丑之方是也"),
})
# 부가 발췌(확인 근거 추적용). (코드, 발췌, 구분[original|commentary], 메모) — 페이지 텍스트에 그대로 있어야 verified=True
MORE = {
    "MG-L1-DEUKRYEONG-BONGI": [("dt", "令星，乃命之至要，宜氣象得令者吉，喜神得令者吉", "annotation", "得令=氣象·喜神(用神)이 令星(月令 人元用事)을 얻음. 일간 신강약·본기 비겁/인성 기준이 아님"),
                               ("zpv", "雖秉令而不強也", "commentary", "徐樂吾: 秉令(得令)해도 強하다고는 못함 — 得令과 強弱 분리")],
    "MG-L1-DEUKRYEONG-SEASON": [("zpv", "雖秉令而不強也", "commentary", "得時=旺, 強弱과 별개")],
    "MG-L2-HAP-HWA": [("zpv", "有從化取格者，要化出之物，得時乘令，四支局全", "original", "化格 요건: 化神이 得時乘令 + 地支 局全(寅卯辰/亥卯未)"),
                      ("zpv", "甲在年干，己在時上", "original", "원격=半合(길흉 영향 10분의 2~3)")],
    "MG-L2-HYUNG": [("zpv", "至於三刑取廡，姑且闕疑", "original", "저자가 三刑의 취의를 闕疑(보류)"),
                    ("ren", "子卯一刑也，寅巳申二刑也，丑戌未三刑也", "commentary", "통용 三刑 분류. 任氏曰은 刑 자체를 取義 없음(俗謬)으로 비판"),
                    ("ren", "又有自刑，此皆俗謬，姑置之", "commentary", "자형은 任氏曰이 俗謬로 배척")],
    "MG-L2-PA": [("sm", "惟寅申巳亥原破，卻三合，故不取", "original", "寅亥·巳申 破는 취하지 않음(엔진 modern_6 와 충돌, sanmyeongtonghoe_4 와 일치)"),
                 ("ren", "至於破之義，非害即刑也，尤屬不經，削之可也", "commentary", "任氏曰: 破 자체를 삭제 가능(不經)")],
    "MG-L2-HAE": [("ren", "穿，即害也，六害由六合而來，沖我合神，故為之害", "commentary", "害의 정의·산출 규칙(엔진 6쌍과 동일하게 도출됨 — 회귀 테스트)"),
                  ("ren", "害之義，尤為穿鑿", "commentary", "그러나 任氏曰은 害의 取義를 穿鑿이라 비판, '生克으로 논함이 옳다'")],
    "MG-L4-GYEOKGUK-BONGI": [("zpv", "不透甲而透丙，則如知府不臨郡，而同知得以作主", "original", "본기 불투출·중기 투출이면 중기가 作主 → 투출 우선")],
}
# 규칙별 보강 메타: coverage(scoped|partial), unconfirmed_parts, content_gap(location_confirmed 로 남은 이유)
META = {
    "MG-L2-BANGHAP": {"coverage": "partial", "unconfirmed_parts": ["2글자 부분 방합의 인정 여부(원문 없음 — 엔진은 contested 로만 기록)"]},
    "MG-L2-HAP-HWA": {"coverage": "partial", "unconfirmed_parts": ["쟁합·투합 경쟁 없음 조건", "화신을 극하는 천간 없음 조건", "일간 합화 허용 여부(학파 논쟁)"],
                      "confirmed_parts": ["間隔(극하는 글자가 사이에 있음) → 합 불성립", "원격 → 半合", "化는 得時乘令·地支 局全 요건"]},
    "MG-L1-DEUKRYEONG-SEASON": {"coverage": "partial", "unconfirmed_parts": ["월령 오행이 일간을 '생'하는 경우도 득령 근거로 보는 확장"],
                                "confirmed_parts": ["月令 오행 == 일간 오행 = 得時"]},
    "MG-L4-GYEOKGUK-BONGI": {"coverage": "partial", "unconfirmed_parts": ["투출과 무관하게 항상 본기로 격 이름을 짓는 병렬 대안"],
                             "confirmed_parts": ["본기=本主", "본기 불투출·중기 투출이면 중기가 作主(=투출 우선)"]},
    "MG-L1-DEUKRYEONG-BONGI": {"content_gap": "원문의 得令은 月令에서 用事하는 人元(令星, 사령 일수 기준)을 氣象·喜神(用神)이 얻는가의 문제이며, '월지 본기가 일간의 비겁/인성이면 득령'이라는 신강약식 정의는 후대 개념이다. 評註도 得令(秉令)과 強弱을 분리한다. 엔진 정의는 원문에 직접 대응하지 않음."},
    "MG-L2-HYUNG": {"content_gap": "원문(沈孝瞻)은 刑을 三刑('子卯巳申之類')으로 정의하되 取義는 闕疑(보류)로 둔다. 任氏曰은 刑·自刑을 俗謬로 배척한다. 엔진은 子卯·寅巳申·丑戌未·자형을 '존재 후보'로 기록하므로 원문이 규칙 내용을 긍정적으로 뒷받침한다고 볼 수 없다."},
    "MG-L2-PA": {"content_gap": "三命通會는 子酉·丑辰·卯午·未戌 4쌍을 破로 들고 寅申巳亥(寅亥·巳申)는 原破이나 三合/合이므로 취하지 않는다고 한다. 엔진 기본 프로필(modern_6)은 寅亥·巳申을 포함해 원문과 충돌하고 sanmyeongtonghoe_4 프로필만 일치한다. 任氏曰은 破 자체를 삭제 가능(不經)이라 한다. 破는 원문에서 神煞(破煞) 맥락이다.",
                 "confirmed_parts": ["子酉·丑辰·卯午·未戌 4쌍"], "unconfirmed_parts": ["寅亥·巳申 포함(원문은 취하지 않음)"]},
    "MG-L2-HAE": {"content_gap": "任氏曰(주석)이 害(穿)를 '六合의 상대를 沖하는 글자'로 정의한다(엔진 6쌍과 같은 결과가 도출됨). 그러나 같은 주석이 害의 取義를 穿鑿이라 비판하고 生克으로 논하라고 하며, 예시에 寅亥를 적어 도출 규칙(寅巳)과 어긋난다. 원문(滴天髓 본문)에는 害 규정이 없음."},
}


def main() -> None:
    from app.mingli.rules import RULES
    refresh = "--refresh" in sys.argv
    pages: dict[str, str | None] = {}
    failed: dict[str, str] = {}
    for code in SOURCES:
        txt, err = fetch(code, refresh)
        pages[code] = _norm(txt) if txt else None
        if err:
            failed[code] = err
    result = {}
    for rid in RULES:
        base = {"accessed": ACCESSED, "school_conditions": SCHOOL.get(rid, ""),
                "positive_case": CASES.get(rid, {}).get("pos"), "negative_case": CASES.get(rid, {}).get("neg")}
        if rid in CONV:
            result[rid] = {**base, "classification": "convention", "status": "implementation_convention", "work": None, "section": None,
                           "url": None, "original_excerpt": None, "commentary_excerpt": None, "keywords_found": [], "scope_note": "구현자 규약. 고전이 이렇게 말한다고 주장하지 않는다.",
                           "notes": ""}
            continue
        entry = {**base, "classification": "classical", "status": "pending", "work": None, "section": None, "url": None,
                 "original_excerpt": None, "commentary_excerpt": None, "keywords_found": [], "scope_note": "", "notes": ""}
        if rid in HUMAN:
            code, ex, is_comm, why, *sec = HUMAN[rid]
            name, url = SOURCES[code]
            if pages.get(code) and _norm(ex) in pages[code]:
                entry.update(status="text_confirmed", work=name, url=url, section=(sec[0] if sec else why.split(".")[0][:30]), scope_note=why,
                             keywords_found=[ex[:8]], notes="사람이 구절을 읽고 규칙 내용(scope_note 범위)에 대응함을 확인. 발췌는 페이지 텍스트에 그대로 존재함을 스크립트가 재검증.")
                entry["commentary_excerpt" if is_comm else "original_excerpt"] = ex
            else:
                entry.update(notes=f"HUMAN 발췌가 페이지에 없거나 출처({code}) 접속 실패 → text_confirmed 강등. 접속 오류: {failed.get(code)}")
        elif rid in LOC:
            codes, kws, section = LOC[rid]
            for code in codes:
                if pages.get(code) and all(k in pages[code] for k in kws):
                    name, url = SOURCES[code]
                    ex = excerpt(pages[code], kws[0])
                    entry.update(status="location_confirmed", work=name, url=url, section=section, keywords_found=kws,
                                 commentary_excerpt=ex if code in ("ren",) else None, original_excerpt=None if code in ("ren",) else ex,
                                 scope_note="핵심어가 해당 출처 페이지에 존재함(위치 확인). 구절이 규칙 내용을 직접 뒷받침하는지는 판단하지 않음.", notes=SCHOOL.get(rid, ""))
                    break
            else:
                entry["notes"] = f"핵심어 {kws} 를 {codes} 에서 찾지 못했거나 접속 실패"
        if rid in EXTRA_COMMENTARY:
            code, ex = EXTRA_COMMENTARY[rid]
            if pages.get(code) and _norm(ex) in pages[code]:
                entry["commentary_excerpt"] = ex
        entry["coverage"] = META.get(rid, {}).get("coverage", "scoped" if entry["status"] == "text_confirmed" else None)
        for key in ("unconfirmed_parts", "confirmed_parts", "content_gap"):
            if key in META.get(rid, {}):
                entry[key] = META[rid][key]
        adds = []
        for code, text, kind, note in MORE.get(rid, []):
            ok = bool(pages.get(code)) and _norm(text) in pages[code]
            assert len(text) <= 40, (rid, text)
            adds.append({"work": SOURCES[code][0], "url": SOURCES[code][1], "kind": kind, "text": text, "note": note, "verified_in_page": ok})
        if adds:
            entry["additional_excerpts"] = adds
        result[rid] = entry
    # 일관성: 단일 한자 핵심어 일치만으로 위치를 인정하지 않는다(LOC 는 모두 2글자 이상)
    assert all(len(k) >= 2 for _, ks, _ in LOC.values() for k in ks)
    OUT.write_text(json.dumps({"accessed": ACCESSED, "failed_sources": failed,
                               "method": "자동 위치 확인 + 사람이 읽고 확인한 발췌의 재검증. 외부 전사본은 판본 교감 전이며 짧은 발췌만 저장.",
                               "rules": result}, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(dict(Counter(e["status"] for e in result.values())), "failed:", list(failed))


if __name__ == "__main__":
    main()
