"""블라인드 상담 평가 파일럿 운영 도구(로컬 전용, 합성 명식만).
  python -m tools.blind_eval build [--n 20] [--v81-json F] [--v82-json F]  → data_private/blind/{packet.json, key.json, rater_form.html}
        (key.json 은 평가자에게 배포하지 않는다. rater_form.html 은 독립 HTML 한 개 — 이메일·메신저로 전달해 브라우저로 열면 된다)
  python -m tools.blind_eval score FILE.csv|FILE.json ...                  → 집계(summary.md/summary.csv) 및 파일럿 상태
  python -m tools.blind_eval status                                       → 응답 없이 현재 상태(미평가) 확인
응답이 없으면 '미평가'를 유지한다. 파일럿이 끝나도 '상담 품질 검증 완료'로 표시하지 않는다(전문가 3·일반 3 기준은 별도)."""
import argparse
import csv
import json
import sys
from pathlib import Path

from app import blind_eval as BE
from app.consult import agent
from tools.eval_synthesis import charts

OUT = Path(__file__).resolve().parents[1] / "data_private" / "blind"
QUESTIONS = [(("overall", "wealth", "career"), (2030,), "2030년 재물과 직업·승진 흐름이 궁금합니다"), (("love_marriage", "family"), (2028,), "2028년 관계와 가족 흐름이 궁금합니다"),
             (("overall", "career"), tuple(range(2027, 2032)), "앞으로 5년 직업 흐름이 궁금합니다")]


def items(n, v81_json: str | None = None, v82_json: str | None = None):
    """평가 항목: 같은 합성 명식·질문에 대해 v7.0(종합 템플릿), v8.1(결론형), v8.2(개선)의 문장을 출처 없이 비교한다.
    v8.1·v8.2 문장은 해당 커밋의 코드에서 tools.dump_verdict_text 로 덤프한 JSON 을 쓴다(없으면 v8.2 는 현재 코드로 생성)."""
    from app.evaluation import dataset as DS
    from tools.dump_verdict_text import verdict_text
    load = lambda f: json.loads(Path(f).read_text(encoding="utf-8")) if f and Path(f).exists() else {}
    v81, v82 = load(v81_json), load(v82_json)
    out = []
    for name, p in charts(n):
        doms, years, q = QUESTIONS[len(out) % len(QUESTIONS)]
        pre = DS.pre_of(DS.Spec(p, domains=doms, years=years, cycles_first_year=2000))
        a = agent.answer(pre, q, domains_=list(doms), years=list(years), depth="detailed")
        S = a["synthesis"]
        v70 = "\n".join([x["text"] for k in ("headline", "favorable", "cautions") for x in S[k]] + [f"[{r['name']}] " + " ".join([r["meaning"], r["why"], r["reality"], " ".join(r["counter"]), r["scope"]]) for r in S["readings"]])
        variants = {"v70": v70}
        if name in v81:
            variants["v81"] = v81[name]
        variants["v82"] = v82.get(name) or verdict_text(a["verdict"])
        out.append({"item_id": name, "question": q, "years": list(years), "domains": list(doms), "variants": variants})
    return out


FORM = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>상담 문장 읽어 보고 평가하기</title>
<style>:root{--paper:#F7F4EE;--doc:#FCFBF8;--ink:#1F1A17;--ink2:#5C5148;--rule:#D9D0C4;--seal:#A6462A}
body{font:16.5px/1.8 "Noto Serif KR","Nanum Myeongjo",Batang,serif;max-width:960px;margin:0 auto;padding:18px;background:var(--paper);color:var(--ink)}
h1{font-size:1.5rem}h2{font-size:1.15rem;margin:0 0 .4rem}.box{background:var(--doc);border:1px solid var(--rule);padding:14px 16px;margin:14px 0}
.note{border-left:3px solid var(--seal);padding:.5rem .9rem;background:#F3E6DF}.q{color:var(--ink2)}.t{white-space:pre-wrap;background:#fff;border:1px solid var(--rule);padding:10px 12px;font-size:.98rem}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px}table{border-collapse:collapse;width:100%;font:.92rem/1.5 sans-serif}td,th{padding:3px 6px;border-bottom:1px solid var(--rule);text-align:left}
select,input,textarea,button{font:inherit;padding:4px 8px;max-width:100%}textarea{width:100%;box-sizing:border-box}button{cursor:pointer}.bar{position:sticky;top:0;background:var(--paper);padding:8px 10px;border-bottom:1px solid var(--rule);z-index:5;display:flex;flex-wrap:wrap;gap:.5rem .8rem;align-items:center}
.done{border-color:var(--seal)}.small{font:.88rem/1.6 sans-serif;color:var(--ink2)}</style></head><body>
<h1>상담 문장 읽어 보고 평가하기</h1>
<div class="note"><b>명리학을 몰라도 됩니다.</b> 아래 문장은 <b>가상의 사주</b>(실제 사람이 아님)로 컴퓨터가 만든 상담 문장입니다. 항목마다 서로 다른 방식으로 만든 문장 X·Y·Z(경우에 따라 둘)가 나옵니다.
어느 방식이 어떤 문장인지는 알려 드리지 않습니다. 정답은 없고, <b>읽고 느낀 대로</b> 평가해 주세요.</div>
<div class="box"><h2>이렇게 평가해 주세요</h2><ol>
<li>질문을 읽고, 문장 X·Y·Z를 차례로 읽습니다.</li>
<li>각 문장마다 5가지를 1점(전혀 아니다)~5점(매우 그렇다)으로 고릅니다: 이해도 · 구체성 · 유용성 · 자연스러움 · 신뢰도.</li>
<li>가장 마음에 드는 문장을 고르고, <b>왜 그렇게 골랐는지 한두 문장</b>으로 적어 주세요(선택이지만 큰 도움이 됩니다).</li>
<li>10개 이상 평가하면 충분합니다. 모두 못 해도 됩니다. 입력은 이 브라우저에 자동 저장되므로 중간에 닫아도 됩니다.</li>
<li>마지막에 <b>‘평가 결과 내려받기(CSV)’</b>를 눌러 파일을 운영자에게 보내 주세요. 서버로 전송되는 것은 없습니다.</li></ol>
<p class="small">개인정보: 실제 이름·생년월일·연락처는 적지 않습니다. 평가자 이름 칸에는 별명이나 번호(예: 평가자1)만 쓰세요. 이 평가는 문장 품질을 비교하는 것이며 점이나 예언의 정확도를 시험하는 것이 아닙니다.</p></div>
<div class="bar box"><label>평가자 별명/번호 <input id="rid" placeholder="예: 평가자1" size="14"></label>
 <label>나는 <select id="role"><option value="general">일반(명리학 모름)</option><option value="expert">명리 전문가</option></select></label>
 <span id="prog" class="small"></span> <button onclick="exportCsv()">평가 결과 내려받기(CSV)</button> <button onclick="exportJson()" class="small">백업(JSON)</button></div>
<div id="app"></div>
<script>
const P=__PACKET__;const KEY='blind-eval-'+P.items.length+'-'+P.items.map(i=>i.id).join('').slice(0,24);
const C=P.criteria;let S={};try{S=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
function save(){try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}prog()}
function get(id){return S[id]=S[id]||{sc:{},pref:'',reason:''}}
function complete(it){const g=get(it.id);return Object.keys(it.texts).every(s=>C.every(c=>g.sc[s]&&g.sc[s][c.key]))&&g.pref}
function prog(){const n=P.items.filter(complete).length;document.getElementById('prog').textContent=' 완료 '+n+' / '+P.items.length+' (10 이상이면 충분)';
 document.querySelectorAll('section.box').forEach((e,i)=>e.classList.toggle('done',complete(P.items[i])))}
const app=document.getElementById('app');
P.items.forEach((it,ix)=>{const g=get(it.id);const sec=document.createElement('section');sec.className='box';
 const h=document.createElement('h2');h.textContent='항목 '+(ix+1)+' / '+P.items.length;sec.append(h);
 const q=document.createElement('p');q.className='q';q.textContent='질문: '+it.question;sec.append(q);
 const cols=document.createElement('div');cols.className='cols';
 Object.keys(it.texts).forEach(s=>{const d=document.createElement('div');const t=document.createElement('div');t.className='t';t.textContent='문장 '+s+'\n\n'+it.texts[s];d.append(t);
  const tb=document.createElement('table');C.forEach(c=>{const tr=document.createElement('tr');const th=document.createElement('td');th.textContent=c.label.split(':')[0];th.title=c.label;
   const td=document.createElement('td');const sel=document.createElement('select');sel.setAttribute('aria-label','문장 '+s+' '+c.label);sel.innerHTML='<option value="">-</option>'+[1,2,3,4,5].map(n=>'<option>'+n+'</option>').join('');
   sel.value=(g.sc[s]&&g.sc[s][c.key])||'';sel.onchange=()=>{(g.sc[s]=g.sc[s]||{})[c.key]=sel.value;save()};td.append(sel);tr.append(th,td);tb.append(tr)});d.append(tb);cols.append(d)});
 sec.append(cols);
 const p=document.createElement('p');p.innerHTML='<b>가장 마음에 드는 문장</b> ';Object.keys(it.texts).forEach(s=>{const l=document.createElement('label');const r=document.createElement('input');r.type='radio';r.name='pref'+it.id;r.value=s;r.checked=g.pref===s;r.onchange=()=>{g.pref=s;save()};l.append(r,document.createTextNode(' '+s+'  '));p.append(l)});sec.append(p);
 const ta=document.createElement('textarea');ta.rows=2;ta.placeholder='왜 그 문장이 가장 좋았나요? (선택, 한두 문장)';ta.value=g.reason||'';ta.oninput=()=>{g.reason=ta.value;save()};sec.append(ta);app.append(sec)});
const legend=document.createElement('p');legend.className='small';legend.textContent='점수 기준: 1=전혀 아니다, 2=아니다, 3=보통, 4=그렇다, 5=매우 그렇다. 항목 이름에 마우스를 올리면 설명이 보입니다.';app.append(legend);
function q(v){v=String(v==null?'':v);return '"'+v.replace(/"/g,'""')+'"'}
function exportCsv(){const rid=document.getElementById('rid').value.trim();if(!rid){alert('평가자 별명/번호를 먼저 적어 주세요.');return}
 const role=document.getElementById('role').value;const rows=[['rater_id','role','item_id','slot','understand','specific','useful','natural','trust','preferred','reason']];
 P.items.forEach(it=>{const g=get(it.id);Object.keys(it.texts).forEach(s=>{const sc=g.sc[s]||{};if(!C.some(c=>sc[c.key])&&g.pref!==s)return;
  rows.push([rid,role,it.id,s,sc.understand||'',sc.specific||'',sc.useful||'',sc.natural||'',sc.trust||'',g.pref===s?1:'',g.pref===s?g.reason:''])})});
 const n=P.items.filter(complete).length;if(n<10&&!confirm('완료한 항목이 '+n+'개입니다(10개 이상 권장). 그래도 내려받을까요?'))return;
 const blob=new Blob(['﻿'+rows.map(r=>r.map(q).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='rating_'+rid+'.csv';a.click()}
function exportJson(){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({rater_id:document.getElementById('rid').value,role:document.getElementById('role').value,state:S},null,1)],{type:'application/json'}));a.download='backup.json';a.click()}
prog();
</script></body></html>"""


def build(a):
    OUT.mkdir(parents=True, exist_ok=True)
    packet, key = BE.build_packet(items(a.n, a.v81_json, a.v82_json))
    (OUT / "packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "rater_form.html").write_text(FORM.replace("__PACKET__", json.dumps(packet, ensure_ascii=False)), encoding="utf-8")
    print("wrote", OUT, "— key.json 은 평가자에게 배포하지 마세요. 배포 파일: rater_form.html 하나")


def load_ratings(files):
    out = []
    for f in files:
        text = Path(f).read_text(encoding="utf-8-sig")
        if str(f).lower().endswith(".csv"):
            out += BE.ratings_from_csv(text)
        else:
            d = json.loads(text)
            if "ratings" in d:
                out.append(d)
    return out


def report(files):
    packet = json.loads((OUT / "packet.json").read_text(encoding="utf-8"))
    key = json.loads((OUT / "key.json").read_text(encoding="utf-8"))
    ratings = load_ratings(files)
    agg = BE.aggregate(packet, key, ratings)
    pg = BE.pilot_gate(agg)
    lines = [f"# 블라인드 평가 파일럿 집계\n", f"- 상태: **{pg['status']}** (파일럿 완료={pg['pilot_complete']}, 상담 품질 검증 완료={pg['validation_complete']})",
             f"- 유효 평가자 {agg.get('n_valid_raters', 0)}명 {agg['raters']}, 제외된 응답 {len(agg['rejected'])}건"]
    if pg["reasons"]:
        lines.append("- 미충족: " + " / ".join(pg["reasons"]))
    if pg.get("note"):
        lines.append(f"- 주의: {pg['note']}")
    if agg["overall"]:
        lines += ["\n## 버전별 평균(1~5)\n", "| 버전 | 전체 | 이해도 | 구체성 | 유용성 | 자연스러움 | 신뢰도 | 선호 수 |", "|---|---|---|---|---|---|---|---|"]
        for r in BE.summary_rows(agg):
            lines.append(f"| {r['variant']} | {r['overall_mean']} | " + " | ".join(str(r.get(k)) for k in BE.CRITERIA_KEYS) + f" | {r['preferred_count']} |")
        lines.append(f"\n- 선호 응답 {agg['n_preferences']}건, 평가자 간 선호 일치도 {agg['agreement']}")
        for v, rs in agg["reasons"].items():
            lines += [f"\n### {v}를 고른 이유({len(rs)}건)"] + [f"- {x}" for x in rs[:8]]
    else:
        lines.append("\n응답이 없어 집계할 점수가 없습니다. **미평가 상태입니다.**")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(OUT / "summary.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["variant", "overall_mean", *BE.CRITERIA_KEYS, "preferred_count"])
        w.writeheader()
        w.writerows(BE.summary_rows(agg))
    print("\n".join(lines))
    return agg, pg


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--n", type=int, default=20)
    b.add_argument("--v81-json", default=None)
    b.add_argument("--v82-json", default=None)
    s = sub.add_parser("score")
    s.add_argument("files", nargs="+")
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a)
    elif a.cmd == "score":
        report(a.files)
    else:
        report([])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
