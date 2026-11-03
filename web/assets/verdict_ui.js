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

/* 명식 전체 종합: 핵심 결론 → 왜 → 현실 참고 → 판단이 달라질 수 있는 조건 */
/* 이 사주의 모습: 성향·일하는 방식·돈·관계를 이어 읽는 글. 근거(어느 자리에 어떤 기운)는 접어 둔다. 한 해만 볼 때는 그 해의 주제를 덧붙인다. */
function sipEl(ss,single){const s=el('section',null,'vsip');s.dataset.sip='1';
  s.append(el('h2','이 사주의 모습'));s.append(el('p',ss.summary,'sipsummary'));
  ss.sections.forEach(x=>{const d=el('div',null,'sipitem');d.append(el('h3',x.title));d.append(el('p',x.text));s.append(d)});
  if(single&&ss.years&&ss.years.length){const y=ss.years[0];const d=el('div',null,'sipitem sipyear');d.append(el('h3',y.year+'년의 주제'));d.append(el('p',y.theme+' '+y.link));d.append(el('p','준비해 볼 일: '+y.prep,'yprep'));s.append(d)}
  const w=el('details',null,'whybox');w.append(el('summary','어느 자리의 어떤 기운에서 그렇게 읽었나요?'));
  const ul=el('ul');ss.palaces.forEach(p=>ul.append(el('li',p.text)));w.append(ul);
  const ev=[].concat(...ss.sections.map(x=>x.evidence||[]));if(ev.length){const u2=el('ul');ev.forEach(t=>u2.append(el('li',t)));w.append(u2)}
  s.append(w);s.append(el('p',ss.label,'small muted'));return s}
/* 첫 장면: 자연물 비유 + 타고난 기운 막대 + 필요한 기운이 들어오는 때(시간 순) */
function storyEl(st){const s=el('section',null,'vstorycard');s.dataset.story='1';
  /* 읽는 순서: 핵심 결론 → 시기·분야 요약 → (이 카드) 자연물 비유. 비유는 설명용이며 판정에 쓰이지 않는다. 막대·계절 균형·큰 흐름 표는 기본 접힘. */
  s.append(el('p','이 사주를 자연에 빗대면','kicker'));s.append(el('h2',st.image,'storytitle'));
  s.append(el('p','전통 명리는 태어난 날의 글자를 자연물에 빗대어 읽습니다. 구조를 쉽게 떠올리기 위한 비유일 뿐, 결론이나 운의 좋고 나쁨을 정하는 근거가 아닙니다.','small muted'));
  const d=el('details',null,'whybox storydetails');d.append(el('summary','기운 분포·계절 균형·큰 흐름 표 보기'));
  const ol=el('ol',null,'beats');st.beats.slice(1).forEach(t=>ol.append(el('li',t)));
  const shape=el('div',null,'storyshape');shape.append(shapeEl(st.shape));
  const body=el('div',null,'storybody');body.append(ol);body.append(shape);d.append(body);
  if(st.timeline&&st.timeline.length){const w=el('div',null,'needline');w.append(el('p','필요한 ‘'+st.need.join('·')+'’의 기운이 들어오는 때(좋은 운이라는 뜻이 아니라 계절 균형의 참고 표시)','small b'));
    const row=el('div',null,'needrow');st.timeline.forEach(r=>{const c=el('div',null,'needcell'+((r.luck_hit||r.year_hit)?' on':''));
      c.append(el('b',String(r.year)));c.append(el('span',(r.luck_hit?'●':'○')+' 큰 흐름','nl'));c.append(el('span',(r.year_hit?'●':'○')+' 그해','nl'));
      c.setAttribute('aria-label',r.year+'년: 10년 큰 흐름 '+(r.luck_hit?'들어옴':'없음')+', 그해의 기운 '+(r.year_hit?'들어옴':'없음'));row.append(c)});w.append(row);d.append(w)}
  d.append(el('p',st.note,'small muted'));s.append(d);return s}
function shapeEl(shape){const w=el('div',null,'elwrap');w.append(el('h3','타고난 기운의 분포'));const cl={나무:'e-wood',불:'e-fire',흙:'e-earth',쇠:'e-metal',물:'e-water'};
  const mx=Math.max(...Object.values(shape),1);let n=0;
  Object.entries(shape).forEach(([nm,c])=>{n+=c;const row=el('div',null,'elrow');row.append(el('span',nm,'elname'));const bar=el('span',null,'elbar');const f=el('span',null,'elfill '+cl[nm]);f.style.width=(c/mx*100)+'%';bar.append(f);row.append(bar);row.append(el('span',c+'개','elnum'));row.setAttribute('role','img');row.setAttribute('aria-label',nm+' 기운 '+c+'개');w.append(row)});
  w.append(el('p','글자 '+n+'개를 다섯 가지 기운으로 센 것입니다. 많고 적음이 곧 좋고 나쁨은 아니며, 속에 숨은 기운은 세지 않았습니다.','small muted'));return w}
/* (예전 단독 막대는 첫 장면으로 합쳐졌다) 여덟 글자를 다섯 가지 기운으로 세는 보조 */
const EL_OF={'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水','子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火','午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'};
const EL_VIS=[['木','나무','e-wood'],['火','불','e-fire'],['土','흙','e-earth'],['金','쇠','e-metal'],['水','물','e-water']];
function elementEl(pil){if(!pil)return null;const cnt={木:0,火:0,土:0,金:0,水:0};let n=0;
  Object.values(pil).forEach(v=>{if(v)[...v].forEach(ch=>{if(EL_OF[ch]){cnt[EL_OF[ch]]++;n++}})});
  if(!n)return null;const w=el('div',null,'elwrap');w.append(el('h3','타고난 기운의 분포'));
  const mx=Math.max(...Object.values(cnt),1);
  EL_VIS.forEach(([k,nm,cl])=>{const row=el('div',null,'elrow');row.append(el('span',nm,'elname'));const bar=el('span',null,'elbar');const fill=el('span',null,'elfill '+cl);fill.style.width=(cnt[k]/mx*100)+'%';
    if(!cnt[k])fill.style.width='0';bar.append(fill);row.append(bar);row.append(el('span',cnt[k]+'개','elnum'));row.setAttribute('role','img');row.setAttribute('aria-label',nm+' 기운 '+cnt[k]+'개');w.append(row)});
  w.append(el('p','글자 '+n+'개를 다섯 가지 기운으로 센 것입니다. 많고 적음이 곧 좋고 나쁨은 아니며, 속에 숨은 기운(지장간)은 세지 않았습니다.','small muted'));
  return w}
function profileEl(p){const s=el('section',null,'vprofile');s.dataset.profile=p.withheld?'withheld':'ok';
  const hd=el('div',null,'vhead');hd.append(el('h2','이 사주에서 중요하게 읽히는 것'));s.append(hd);
  s.append(el('p',p.conclusion,'verdict-a'));
  if(p.reality&&p.reality.length){const h=el('h3','현실에서 참고할 부분');s.append(h);const ul=el('ul');p.reality.forEach(t=>ul.append(el('li',t)));s.append(ul)}
  const d=el('details',null,'whybox');d.append(el('summary','왜 그렇게 읽나요?'));const u1=el('ul');p.why.forEach(t=>u1.append(el('li',t)));d.append(u1);s.append(d);
  if(p.conditions&&p.conditions.length){const c=el('details',null,'whybox');c.append(el('summary','판단이 달라질 수 있는 조건'));const u2=el('ul');p.conditions.forEach(t=>u2.append(el('li',t)));c.append(u2);s.append(c)}
  return s}
function blockEl(v,b,lead){const s=el('section',null,'vblock'+(lead?' lead':''));s.dataset.domain=b.domain;s.dataset.tone=b.tone;
  const h=el('h2',b.name);const hd=el('div',null,'vhead');hd.append(h,chip(b.tone));s.append(hd);
  s.append(el('p',b.headline,'verdict-a'));
  s.append(el('p',b.story.join(' '),'vstory'));
  if(b.think&&b.think.length){s.append(el('h3','현실에서 생각해 볼 점'),ul(b.think))}
  const box=reasonsBox(v,b);const btn=el('button','왜 그렇게 읽나요?','sec why');btn.type='button';btn.setAttribute('aria-expanded','false');
  btn.onclick=()=>{box.hidden=!box.hidden;btn.setAttribute('aria-expanded',String(!box.hidden));btn.textContent=box.hidden?'왜 그렇게 읽나요?':'이유 접기'};
  s.append(btn,box);return s}

function limitsEl(v){const s=el('section',null,'vlimits');s.append(el('h3','해석의 한계'));s.append(ul(v.limits));return s}

/* 한눈표: 분야(행) × 연도(열)의 판정. 색에만 의존하지 않도록 기호와 글자를 함께 쓴다. 판정이 '확률'이나 '좋고 나쁨의 점수'가 아님을 범례에 밝힌다. */
const TONE_VIS={opportunity:['▲','기회','t-opp'],cautious:['▽','주의','t-cau'],mixed:['◆','양면','t-mix'],thin:['?','근거 부족','t-thin'],quiet:['–','변화 없음','t-quiet'],steady:['●','안정','t-steady'],balance:['○','균형','t-steady']};
function heatEl(v){const p=v.period;const ys=p.years.map(r=>r.year);const doms=[];const cell={};
  ys.forEach(y=>{((v.detail[String(y)]||{}).blocks||[]).forEach(b=>{if(!doms.find(d=>d.domain===b.domain))doms.push({domain:b.domain,name:b.name});cell[b.domain+'|'+y]=b})});
  if(!doms.length)return null;
  const w=el('div',null,'heatwrap');w.append(el('h3','한눈에 보기'));
  const sc=el('div',null,'heatscroll');const t=el('table',null,'heat');t.setAttribute('aria-label','분야별·연도별 흐름 한눈표');
  const hr=el('tr');hr.append(el('th','분야'));ys.forEach(y=>hr.append(el('th',String(y))));const th=el('thead');th.append(hr);t.append(th);
  const tb=el('tbody');doms.forEach(d=>{const r=el('tr');const nm=el('th',d.name);nm.scope='row';r.append(nm);
    ys.forEach(y=>{const b=cell[d.domain+'|'+y];const td=el('td');if(b){const m=TONE_VIS[b.tone]||['·',b.tone_label,'t-quiet'];td.className=m[2];td.title=y+'년 '+d.name+': '+m[1];
      td.append(el('span',m[0],'sym'));td.append(el('span',m[1],'lab'));td.setAttribute('aria-label',y+'년 '+d.name+' '+m[1])}else td.textContent='';r.append(td)});tb.append(r)});
  t.append(tb);sc.append(t);w.append(sc);
  const lg=el('p',null,'heatlegend small muted');['opportunity','cautious','mixed','thin','quiet','steady'].forEach(k=>{const m=TONE_VIS[k];const sp=el('span',null,m[2]);sp.append(document.createTextNode(m[0]+' '+m[1]));lg.append(sp)});w.append(lg);
  w.append(el('p','기회·주의는 각 해의 구조 변화가 한쪽으로 뚜렷할 때만 표시합니다. 좋은 일·나쁜 일이 일어난다는 뜻이 아니며 확률도 아닙니다. 근거가 부족하면 ‘근거 부족’으로 두고 억지로 방향을 정하지 않습니다.','small muted'));
  return w}
function periodEl(v){const p=v.period;const s=el('section',null,'vperiod');
  s.append(el('h2',p.span+' 핵심 흐름'));
  p.summary.forEach(t=>s.append(el('p',t,'vstory')));
  const hm=heatEl(v);if(hm)s.append(hm);
  s.append(el('h3','연도별 한 줄'));
  const ol=el('ol',null,'yearlines');
  p.years.forEach(r=>{const li=el('li',null,r.standout?'standout':'');li.dataset.year=r.year;
    const head=el('div',null,'yhead');head.append(el('b',r.year+'년'+(r.standout?' ★':'')),chip(r.tone));li.append(head);
    li.append(el('p',r.change,'ychange'));if(r.caution)li.append(el('p','주의: '+r.caution,'ycaution'));
    if(r.why)li.append(el('p','왜 두드러지나요? '+r.why,'ywhy'));
    const th=((v.profile&&v.profile.sipsung&&v.profile.sipsung.years)||[]).find(z=>z.year===r.year);
    if(th){const t=el('div',null,'ytheme');t.append(el('p',th.theme+' '+th.link));t.append(el('p','준비해 볼 일: '+th.prep,'yprep'));li.append(t)}
    const det=el('div',null,'ydetail');det.hidden=true;
    const btn=el('button',r.year+'년 자세히 보기','sec');btn.type='button';btn.setAttribute('aria-expanded','false');
    btn.onclick=()=>{if(!det.childElementCount){((v.detail[String(r.year)]||{}).blocks||[]).forEach((b,i)=>det.append(blockEl(v,b,false)))}
      det.hidden=!det.hidden;btn.setAttribute('aria-expanded',String(!det.hidden));btn.textContent=det.hidden?r.year+'년 자세히 보기':r.year+'년 접기'};
    li.append(btn,det);ol.append(li)});
  s.append(ol);
  s.append(el('p','연도별 한 줄은 ‘'+(p.primary_domain==='overall'?'종합운':(DOM_KO[p.primary_domain]||p.primary_domain))+'’ 기준입니다. 두드러지는 해는 확률이 아니라 구조 변화의 크기로 고른 것입니다.','small muted'));
  return s}

function chipsFor(a,sel){const v=a.verdict;const box=$('chips');if(!box){return}box.textContent='';
  const ys=a.years||[];const d0=(a.domains||[]).find(d=>d!=='overall'&&d!=='luck');
  const selName=sel&&sel.domain&&sel.domain!=='overall'?sel.domainName:'';
  const dn=selName||(d0?(DOM_KO[d0]||d0):'올해 흐름');
  const q=[];
  const y=(sel&&sel.year)||ys[0]||'';
  q.push((y?y+'년 ':'')+dn+'은 그래서 어떻게 하는 게 좋다는 거야?');
  if(ys.length>=2){const o=ys.find(z=>z!==y);q.push(Math.min(y||ys[0],o)+'년과 '+Math.max(y||ys[0],o)+'년은 어떤 차이가 있어?')}
  if(sel&&sel.month){q.push('이 달에는 무엇이 달라지나요?');q.push('이 달과 지난달은 무엇이 다른가요?')}
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
  /* v10.1: 대시보드형 결과 — 컨트롤 바 → 핵심 결론 → 내 사주의 모습 | 시기별 흐름 → 분야별 해석 → 한계 (dashboard.js). 대시보드가 없으면(구버전 데모) 예전 구성으로 */
  document.body.classList.toggle('has-dash',!!(window.MingliDash&&v.profile));document.body.classList.toggle('is-static',!!STATIC);
  if(window.MingliDash&&v.profile){root.append(window.MingliDash.build(a))}
  else{
    if(v.profile){root.append(profileEl(v.profile))}
    if(v.mode==='multi'){root.append(periodEl(v))}else{v.blocks.forEach((b,i)=>root.append(blockEl(v,b,i===0)))}
  }
  root.append(limitsEl(v));out.append(root);
  if(window.MingliMotion&&document.getElementById('dash')){window.MingliMotion.results(document.getElementById('dash'));window.MingliMotion.sticky(document.querySelector('#dash .dash-bar'))}
  /* 내 사주(네 기둥): 결론 아래에 접어 둔다 */
  const st=$('status');st.textContent='';st.hidden=false;st.className='chapter pillars-card';
  if(pre.calc){const cn=el('div',null,'calc calc-'+pre.calc.level);cn.append(el('b',pre.calc.title));const ul=el('ul');pre.calc.items.forEach(t=>ul.append(el('li',t)));cn.append(ul);cn.setAttribute('data-calc',pre.calc.level);st.append(cn)}
  const d=el('details');d.append(el('summary','내 사주(네 기둥) 보기'));d.append(pillarTable(pre.pillars));
  d.append(el('p','태어난 해·달·날·시각을 각각 한자 두 글자(위=하늘 기운, 아래=땅 기운)로 적은 것입니다. ‘나의 중심’은 태어난 날의 위 글자로, 풀이에서 나를 대표하는 글자로 삼습니다. 아래 풀이의 바탕이 되는 계산 결과입니다.','small muted'));st.append(d);
  out.after(st);
  window.MingliChips=function(aa,sel){chipsFor(aa,sel)};
  if(!window.MingliSel)chipsFor(a);
  const old=$('keypoints');if(old)old.remove();
};
renderRecord=function(a,question){
  if(!a||a.refused||!a.qa)return origRecord(a,question);
  recordNo+=1;const s=el('section',null,'record qa');s.setAttribute('aria-label','후속 상담 '+recordNo);
  s.append(el('p',question||'(질문 없음)','q'));
  const qa=a.qa;s.append(el('p',qa.text||'','verdict-a small'));
  if(qa.points&&qa.points.length){const u=el('ul',null,'qpoints');qa.points.forEach(t=>u.append(el('li',t)));s.append(u)}
  $('out').append(s);if(window.MingliMotion)window.MingliMotion.appear(s,{y:8,duration:0.35});s.scrollIntoView({block:'nearest'})};
/* 결과가 나오면 머리글(배너·제목·단계 표시)을 접어 첫 결론이 첫 화면에 보이게 하고, '입력 수정'을 누르면 되돌린다 */
const HEAD_SEL=['#staticbanner','main > p.kicker','main > h1','main > p.lead','main > ol.steps'];
const setHead=h=>HEAD_SEL.forEach(q=>{const e=document.querySelector(q);if(e)e.hidden=h});
const origCollapse=collapseForm;
collapseForm=function(j){origCollapse(j);setHead(true)};
$('formedit').addEventListener('click',()=>setHead(false));
const origClear=window.clearScreen;
/* 정적 미리보기 데모도 같은 화면으로(데이터는 결론형만) */
})();
