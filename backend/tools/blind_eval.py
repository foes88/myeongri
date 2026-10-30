"""블라인드 평가 운영 도구(로컬 전용, 합성 명식만).
  python -m tools.blind_eval build [--n 20]      → data_private/blind/{packet.json,key.json,rater_form.html}  (key.json 은 평가자에게 주지 않는다)
  python -m tools.blind_eval score FILE [FILE..] → 평가 파일 집계와 완료 게이트 판정
평가자는 rater_form.html 을 브라우저로 열어 점수를 매기고 JSON 을 내려받아 운영자에게 보낸다(네트워크 전송 없음).
"""
import argparse
import json
import sys
from pathlib import Path

from app import blind_eval as BE
from app.consult import agent
from tools.eval_synthesis import charts

OUT = Path(__file__).resolve().parents[1] / "data_private" / "blind"
QUESTIONS = [(("overall", "wealth", "career"), (2030,), "2030년 재물과 직업·승진 흐름이 궁금합니다"), (("love_marriage", "family"), (2028,), "2028년 관계와 가족 흐름이 궁금합니다"),
             (("overall", "career"), tuple(range(2027, 2032)), "앞으로 5년 직업 흐름이 궁금합니다")]


def items(n):
    from app.evaluation import dataset as DS
    out = []
    for name, p in charts(n):
        doms, years, q = QUESTIONS[len(out) % len(QUESTIONS)]
        pre = DS.pre_of(DS.Spec(p, domains=doms, years=years, cycles_first_year=2000))
        a = agent.answer(pre, q, domains_=list(doms), years=list(years), depth="detailed")
        S = a["synthesis"]
        syn = "\n".join([x["text"] for k in ("headline", "favorable", "cautions") for x in S[k]] + [f"[{r['name']}] " + " ".join([r["meaning"], r["why"], r["reality"], " ".join(r["counter"]), r["scope"]]) for r in S["readings"]])
        out.append({"item_id": name, "question": q, "years": list(years), "domains": list(doms), "variants": {"legacy": a["narrative"], "synthesis": syn}})
    return out


FORM = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>상담문 블라인드 평가</title>
<style>body{font:16px/1.7 serif;max-width:900px;margin:0 auto;padding:16px;background:#F7F4EE;color:#1F1A17}.t{background:#FCFBF8;border:1px solid #D9D0C4;padding:12px;margin:10px 0;white-space:pre-wrap}
td,th{padding:3px 8px;border-bottom:1px solid #D9D0C4}button{padding:6px 14px}.q{color:#5C5148}</style>
<h1>상담문 블라인드 평가</h1><p>합성 명식으로 만든 문장입니다. 출처는 알려 주지 않습니다. 항목마다 문장 X/Y를 각각 1~5점으로 평가하고, 더 나은 쪽을 고르세요. 네트워크로 전송되지 않습니다.</p>
<p>평가자 ID <input id=rid> 역할 <select id=role><option value=lay>일반</option><option value=expert>명리 전문가</option></select></p><div id=app></div>
<p><button onclick=exp()>평가 결과 JSON 내려받기</button></p><script>
const P=__PACKET__;const R={};
const app=document.getElementById('app');
P.items.forEach((it,ix)=>{const d=document.createElement('section');d.innerHTML='<h2>항목 '+(ix+1)+'</h2><p class=q>질문: '+it.question+'</p>';
 const slots=Object.keys(it.texts);slots.forEach(s=>{d.innerHTML+='<h3>문장 '+s+'</h3><div class=t></div>';});
 d.querySelectorAll('.t').forEach((e,i)=>e.textContent=it.texts[slots[i]]);
 const tb=document.createElement('table');tb.innerHTML='<tr><th>항목</th>'+slots.map(s=>'<th>'+s+'</th>').join('')+'</tr>'+P.criteria.map(c=>'<tr><td>'+c.label+'</td>'+slots.map(s=>'<td><select data-id="'+it.id+'" data-s="'+s+'" data-k="'+c.key+'"><option value="">-</option>'+[1,2,3,4,5].map(n=>'<option>'+n+'</option>').join('')+'</select></td>').join('')+'</tr>').join('');
 d.append(tb);const pf=document.createElement('p');pf.innerHTML='더 나은 문장: <select data-pref="'+it.id+'"><option value="">-</option>'+slots.map(s=>'<option>'+s+'</option>').join('')+'</select>';d.append(pf);app.append(d)});
function exp(){const ratings=P.items.map(it=>{const scores={};document.querySelectorAll('select[data-id="'+it.id+'"]').forEach(e=>{if(e.value){(scores[e.dataset.s]=scores[e.dataset.s]||{})[e.dataset.k]=parseInt(e.value)}});
 const pr=document.querySelector('select[data-pref="'+it.id+'"]').value;return {id:it.id,scores:scores,preferred:pr||null}}).filter(r=>Object.keys(r.scores).length||r.preferred);
 const o={schema:'blind-eval-rating/1',rater_id:document.getElementById('rid').value.trim(),role:document.getElementById('role').value,ratings:ratings};
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(o,null,1)],{type:'application/json'}));a.download='rating_'+(o.rater_id||'anon')+'.json';a.click()}
</script>"""


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--n", type=int, default=20)
    s = sub.add_parser("score")
    s.add_argument("files", nargs="+")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.cmd == "build":
        packet, key = BE.build_packet(items(a.n))
        (OUT / "packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / "rater_form.html").write_text(FORM.replace("__PACKET__", json.dumps(packet, ensure_ascii=False)), encoding="utf-8")
        print("wrote", OUT, "— key.json 은 평가자에게 배포하지 마세요")
    else:
        packet = json.loads((OUT / "packet.json").read_text(encoding="utf-8"))
        key = json.loads((OUT / "key.json").read_text(encoding="utf-8"))
        agg = BE.aggregate(packet, key, [json.loads(Path(f).read_text(encoding="utf-8")) for f in a.files])
        print(json.dumps({"aggregate": agg, "gate": BE.gate(agg)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
