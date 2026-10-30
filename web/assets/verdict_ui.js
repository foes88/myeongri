/* 결론형 결과 화면(일회성·정적 미리보기). 응답의 answer.verdict 만 사용한다 — 규칙 번호·근거 번호·구조 이름·원시 근거는 응답에 없고 화면에도 없다.
   live(개발) 모드는 기존 화면을 그대로 쓴다. */
(function(){
if(typeof ONESHOT==='undefined')return;
const NEWUI=ONESHOT||STATIC;
if(!NEWUI)return;
const origRender=renderReport,origRecord=renderRecord;
const TONE_CHIP={opportunity:'▲ 기회',mixed:'◆ 기회와 점검',cautious:'▽ 신중',quiet:'─ 잔잔',thin:'? 근거 부족',steady:'○ 안정',balance:'◇ 균형'};
const chip=t=>{const s=el('span',TONE_CHIP[t]||'','tone t-'+t);return s};

/* 개발용 도구(현실 사건 기록·기록 목록 등)는 사용자 화면에서 만들지 않는다 */
function trimSession(){const s=$('session');s.querySelectorAll('h3').forEach(h=>{h.remove()});
  ['evt','evy','evb','evr','hist','histout','reb','rer','pap','rt','rk','reopen'].forEach(i=>{const e=$(i);if(!e)return;const p=e.closest('.grid')||e.closest('p')||e;e.hidden=true;if(p!==e)p.hidden=true});
  s.querySelectorAll('p.small.muted').forEach(p=>{if(!p.closest('#chips'))p.hidden=true});
  const hd=s.querySelector('h2');if(hd)hd.textContent='더 물어보기';const k=s.querySelector('.kicker');if(k)k.textContent='후속 상담';
  const lab=s.querySelector('label[for=q2]');if(lab)lab.textContent='궁금한 점을 그대로 적어 보세요';
  $('askb').textContent='물어보기';
  const dp=$('depth');if(dp){const g=dp.closest('div');if(g)g.hidden=true}}
trimSession();

function reasonsBox(v,b){const w=b.why;const box=el('div',null,'whybox');box.hidden=true;
  if(!w){box.append(el('p','이 결론의 이유를 정리한 항목이 없습니다.','small muted'));return box}
  const sec=(t,arr)=>{if(arr&&arr.length){box.append(el('h4',t),ul(arr))}};
  sec('타고난 사주에서 이렇게 봅니다',w.natal);sec('이 시기에 이렇게 봅니다',w.period);sec('반대로 보는 이유',w.against);
  if(w.nature)box.append(el('p',w.nature,'small muted'));return box}

function blockEl(v,b,lead){const s=el('section',null,'vblock'+(lead?' lead':''));s.dataset.domain=b.domain;s.dataset.tone=b.tone;
  const h=el('h2',b.name);const hd=el('div',null,'vhead');hd.append(h,chip(b.tone));s.append(hd);
  s.append(el('p',b.headline,'verdict-a'));
  s.append(el('p',b.story.join(' '),'vstory'));
  if(b.think&&b.think.length){s.append(el('h3','현실에서 생각해 볼 점'),ul(b.think))}
  const box=reasonsBox(v,b);const btn=el('button','왜 그렇게 읽나요?','sec why');btn.type='button';btn.setAttribute('aria-expanded','false');
  btn.onclick=()=>{box.hidden=!box.hidden;btn.setAttribute('aria-expanded',String(!box.hidden));btn.textContent=box.hidden?'왜 그렇게 읽나요?':'이유 접기'};
  s.append(btn,box);return s}

function limitsEl(v){const s=el('section',null,'vlimits');s.append(el('h3','해석의 한계'));s.append(ul(v.limits));return s}

function periodEl(v){const p=v.period;const s=el('section',null,'vperiod');
  s.append(el('h2',p.span+' 핵심 흐름'));
  p.summary.forEach(t=>s.append(el('p',t,'vstory')));
  s.append(el('h3','연도별 한 줄'));
  const ol=el('ol',null,'yearlines');
  p.years.forEach(r=>{const li=el('li',null,r.standout?'standout':'');li.dataset.year=r.year;
    const head=el('div',null,'yhead');head.append(el('b',r.year+'년'+(r.standout?' ★':'')),chip(r.tone));li.append(head);
    li.append(el('p',r.change,'ychange'));if(r.caution)li.append(el('p','주의: '+r.caution,'ycaution'));
    if(r.why)li.append(el('p','왜 두드러지나요? '+r.why,'ywhy'));
    const det=el('div',null,'ydetail');det.hidden=true;
    const btn=el('button',r.year+'년 자세히 보기','sec');btn.type='button';btn.setAttribute('aria-expanded','false');
    btn.onclick=()=>{if(!det.childElementCount){((v.detail[String(r.year)]||{}).blocks||[]).forEach((b,i)=>det.append(blockEl(v,b,false)))}
      det.hidden=!det.hidden;btn.setAttribute('aria-expanded',String(!det.hidden));btn.textContent=det.hidden?r.year+'년 자세히 보기':r.year+'년 접기'};
    li.append(btn,det);ol.append(li)});
  s.append(ol);
  s.append(el('p','연도별 한 줄은 ‘'+(p.primary_domain==='overall'?'종합운':(DOM_KO[p.primary_domain]||p.primary_domain))+'’ 기준입니다. 두드러지는 해는 확률이 아니라 구조 변화의 크기로 고른 것입니다.','small muted'));
  return s}

function chipsFor(a){const v=a.verdict;const box=$('chips');if(!box){return}box.textContent='';
  const ys=a.years||[];const d0=(a.domains||[]).find(d=>d!=='overall'&&d!=='luck');const dn=d0?(DOM_KO[d0]||d0):'올해 흐름';
  const q=[];
  const y=ys[0]||'';
  q.push((y?y+'년 ':'')+dn+'은 그래서 어떻게 하는 게 좋다는 거야?');
  if(ys.length>=2)q.push(ys[0]+'년과 '+ys[ys.length>1?1:0]+'년 중 어느 쪽이 더 나아?');
  q.push('결과에 나온 ‘점검할 점’은 무슨 뜻이야?');q.push('왜 그렇게 읽어?');
  q.forEach(t=>{const b=el('button',t,'chipq');b.type='button';b.onclick=()=>{$('q2').value=t;$('askb').click()};box.append(b)})}

renderReport=function(a,pre,reopened){
  if(!a.verdict)return origRender(a,pre,reopened);
  $('report').hidden=false;
  const c=$('cover');c.textContent='';
  c.append(el('p',STATIC?'합성 데모 — 실제 분석 결과가 아닙니다':'내 사주 풀이','kicker'),el('h1','결론부터 말씀드리면'));
  const m=el('p',null,'meta');const add=(k,t)=>{const s=el('span');s.append(el('b',k+' '));s.append(document.createTextNode(t));m.append(s)};
  add('분석 시기',(a.years&&a.years.length)?(a.years.length>1?a.years[0]+'~'+a.years[a.years.length-1]+'년':a.years[0]+'년'):'타고난 사주');
  add('살펴본 분야',(a.domains||[]).map(d=>DOM_KO[d]||d).join(', '));c.append(m);
  const out=$('out');out.textContent='';const v=a.verdict;const root=el('div');root.id='verdict';
  if(v.mode==='multi'){root.append(periodEl(v))}
  else{v.blocks.forEach((b,i)=>root.append(blockEl(v,b,i===0)))}
  root.append(limitsEl(v));out.append(root);
  /* 내 사주(네 기둥): 결론 아래에 접어 둔다 */
  const st=$('status');st.textContent='';st.hidden=false;st.className='chapter pillars-card';
  if(pre.calc){const cn=el('div',null,'calc calc-'+pre.calc.level);cn.append(el('b',pre.calc.title));const ul=el('ul');pre.calc.items.forEach(t=>ul.append(el('li',t)));cn.append(ul);cn.setAttribute('data-calc',pre.calc.level);st.append(cn)}
  const d=el('details');d.append(el('summary','내 사주(네 기둥) 보기'));d.append(pillarTable(pre.pillars));
  d.append(el('p','위쪽 글자(천간)와 아래쪽 글자(지지)로 이루어진 네 기둥입니다. 풀이의 바탕이 되는 계산 결과입니다.','small muted'));st.append(d);
  out.after(st);
  chipsFor(a);
  const old=$('keypoints');if(old)old.remove();
};
renderRecord=function(a,question){
  if(!a||a.refused||!a.qa)return origRecord(a,question);
  recordNo+=1;const s=el('section',null,'record qa');s.setAttribute('aria-label','후속 상담 '+recordNo);
  s.append(el('p',question||'(질문 없음)','q'));
  const qa=a.qa;s.append(el('p',qa.text||'','verdict-a small'));
  if(qa.points&&qa.points.length){const u=el('ul',null,'qpoints');qa.points.forEach(t=>u.append(el('li',t)));s.append(u)}
  $('out').append(s);s.scrollIntoView({block:'nearest'})};
/* 결과가 나오면 머리글(배너·제목·단계 표시)을 접어 첫 결론이 첫 화면에 보이게 하고, '입력 수정'을 누르면 되돌린다 */
const HEAD_SEL=['#staticbanner','main > p.kicker','main > h1','main > p.lead','main > ol.steps'];
const setHead=h=>HEAD_SEL.forEach(q=>{const e=document.querySelector(q);if(e)e.hidden=h});
const origCollapse=collapseForm;
collapseForm=function(j){origCollapse(j);setHead(true)};
$('formedit').addEventListener('click',()=>setHead(false));
const origClear=window.clearScreen;
/* 정적 미리보기 데모도 같은 화면으로(데이터는 결론형만) */
})();
