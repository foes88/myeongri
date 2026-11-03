/* v10.1 대시보드형 결과 화면. 기존 API 응답(answer.verdict)을 ViewModel 로 한 번 재구성해 모든 영역이 같은 데이터·같은 선택 상태({year, domain})를 참조한다.
   새 점수·확률을 만들지 않는다(엔진이 준 상태와 문장만 배치). 내부 근거 ID·전문 용어는 다루지 않는다. */
(function(){
'use strict';
const TV={opportunity:['▲','기회','t-opp'],cautious:['▽','주의','t-cau'],mixed:['◆','맞섬','t-mix'],thin:['?','근거 부족','t-thin'],quiet:['–','변화 없음','t-quiet'],steady:['●','안정','t-steady'],balance:['○','균형','t-steady']};
const tv=t=>TV[t]||['·','','t-quiet'];
const first=t=>{const m=String(t||'').match(/^.*?[.!?](\s|$)/);return m?m[0].trim():String(t||'')};
const rest=t=>String(t||'').slice(first(t).length).trim();
const E=(t,txt,cls)=>{const e=document.createElement(t);if(txt!==undefined&&txt!==null)e.textContent=txt;if(cls)e.className=cls;return e};
const A=(e,o)=>{Object.entries(o).forEach(([k,v])=>e.setAttribute(k,v));return e};

/* ---------- ViewModel ---------- */
function buildVM(a){
  const v=a.verdict,multi=v.mode==='multi',ys=(a.years||[]).slice();
  const blocksOf=y=>multi?((v.detail&&v.detail[String(y)]||{}).blocks||[]):(v.blocks||[]);
  const b0=blocksOf(ys[0]);
  const domains=b0.map(b=>({domain:b.domain,name:b.name}));
  const rows=multi?((v.period&&v.period.years)||[]):ys.map(y=>{const o=blocksOf(y).find(b=>b.domain==='overall')||blocksOf(y)[0]||{};return {year:y,tone:o.tone,line:null,change:null,caution:null,standout:false,why:''}});
  const ss=(v.profile&&v.profile.sipsung)||null;
  return {a,v,multi,years:ys,domains,rows,blocksOf,profile:v.profile||null,ss,
    row:y=>rows.find(r=>r.year===y)||{year:y},
    block:(y,d)=>blocksOf(y).find(b=>b.domain===d)||null,
    theme:y=>((ss&&ss.years)||[]).find(z=>z.year===y)||null,
    seg:y=>((v.segments||{})[String(y)])||[]};
}

/* ---------- 선택 상태 ---------- */
function makeState(vm){const ov=vm.domains.find(d=>d.domain==='overall');return {year:vm.years[0]!==undefined?vm.years[0]:null,domain:(ov||vm.domains[0]||{}).domain||'overall'}}

/* ---------- A 컨트롤 바 ---------- */
function controlBar(vm){
  const n=vm.years.length,bar=E('div',null,'dash-bar');
  const span=n?(n>1?vm.years[0]+'–'+vm.years[n-1]+'년':vm.years[0]+'년'):'타고난 사주';
  const seg=E('div',null,'dash-seg');A(seg,{role:'group','aria-label':'분석 기간'});
  [['1년',1,'to1'],['5년',5,'to5'],['10년',10,'to10']].forEach(([lab,k,id])=>{const b=E('button',lab,'segbtn');b.type='button';b.id='dash-'+id;A(b,{'aria-pressed':String(n===k),'data-act':id});
    b.onclick=()=>{const t=document.getElementById(id);if(t)t.click()};seg.append(b)});
  const nav=E('div',null,'dash-nav');A(nav,{role:'group','aria-label':'분석 연도 이동'});
  const pv=E('button','◀ 이전 해','navbtn');pv.type='button';pv.id='dash-prev';pv.onclick=()=>{const t=document.getElementById('yprev');if(t)t.click()};
  const cur=E('span',span,'navcur');cur.id='dash-span';A(cur,{'aria-live':'polite'});
  const nx=E('button','다음 해 ▶','navbtn');nx.type='button';nx.id='dash-next';nx.onclick=()=>{const t=document.getElementById('ynext');if(t)t.click()};
  nav.append(pv,cur,nx);
  const ed=E('button','입력 수정','navbtn ghost');ed.type='button';ed.id='dash-edit';ed.onclick=()=>{const t=document.getElementById('formedit');if(t)t.click()};
  bar.append(seg,nav,ed);return bar}

/* ---------- B 핵심 결론 ---------- */
function conclusion(vm){
  const p=vm.profile,s=E('section',null,'dash-conclusion');s.setAttribute('aria-labelledby','h-concl');
  const h=E('h2','이 사주에서 중요하게 읽히는 것');h.id='h-concl';s.append(h);
  if(!p){s.append(E('p','이 결과에는 종합 결론이 없습니다.','concl-text'));return s}
  const stamp=E('span',null,'stamp');A(stamp,{'aria-hidden':'true'});stamp.append(E('i','명'),E('i','리'));s.append(stamp);
  const ct=E('p',null,'concl-text');String(p.conclusion).split(/(‘[^’]+’)/).forEach(t=>{if(!t)return;if(t[0]==='‘')ct.append(E('mark',t,'hl'));else ct.append(document.createTextNode(t))});s.append(ct);
  const brush=E('span',null,'brush');A(brush,{'aria-hidden':'true'});s.append(brush);
  const re=p.reality||[];
  const timeLine=re.find(t=>t.indexOf('선택한 시기에 달라지는 조건')===0);
  const change=vm.multi&&vm.v.period&&vm.v.period.summary&&vm.v.period.summary.length>1?vm.v.period.summary[1]:(timeLine?timeLine.replace(/^선택한 시기에 달라지는 조건\s*[—-]\s*/,''):(vm.multi&&vm.v.period&&vm.v.period.summary?vm.v.period.summary[0]:null));
  const viewRaw=re.find(t=>/방향이 읽힙니다|판단을 유보|맞서/.test(t))||re.find(t=>t!==timeLine)||null;const view=viewRaw?first(viewRaw):null;
  const tend=vm.ss&&vm.ss.sections&&vm.ss.sections[0]?first(vm.ss.sections[0].text):null;const feat=tend||(vm.ss&&vm.ss.summary?vm.ss.summary.replace(/^한 줄로 말하면,\s*/,''):null);
  const trio=E('div',null,'concl-trio');
  [['이 사주의 특징',feat],['선택한 시기의 변화',change],['참고할 관점',view]].forEach(([lab,txt])=>{const d=E('div',null,'trio-item');d.append(E('h3',lab));d.append(E('p',txt||'이 항목은 근거가 부족해 말하지 않습니다.',txt?'':'muted'));trio.append(d)});
  s.append(trio);
  const d1=E('details',null,'fold');d1.append(E('summary','왜 그렇게 읽나요?'));const u1=E('ul');(p.why||[]).forEach(t=>u1.append(E('li',t)));d1.append(u1);
  const d2=E('details',null,'fold');d2.append(E('summary','판단이 달라질 수 있는 조건'));const u2=E('ul');(p.conditions||[]).forEach(t=>u2.append(E('li',t)));d2.append(u2);
  const folds=E('div',null,'folds');folds.append(d1,d2);s.append(folds);return s}

/* 다섯 기운의 상생 순환도(장식·보조): 나무→불→흙→쇠→물→나무. 원 크기는 글자 수. 값은 아래 막대·aria-label 이 그대로 전한다 */
function wheel(shape,cl){
  const NS='http://www.w3.org/2000/svg',mk=(t,a)=>{const e=document.createElementNS(NS,t);Object.entries(a||{}).forEach(([k,v])=>e.setAttribute(k,v));return e};
  const names=['나무','불','흙','쇠','물'],C=130,R=82,svg=mk('svg',{viewBox:'0 0 260 260',class:'wheel','aria-hidden':'true',focusable:'false'});
  const pos=names.map((n,i)=>{const a=(-90+72*i)*Math.PI/180;return {n,x:C+R*Math.cos(a),y:C+R*Math.sin(a),r:13+Math.min(shape[n]||0,5)*3.2,c:shape[n]||0}});
  const defs=mk('defs'),mkr=mk('marker',{id:'wa',viewBox:'0 0 8 8',refX:'6',refY:'4',markerWidth:'6',markerHeight:'6',orient:'auto'});mkr.append(mk('path',{d:'M0 0L8 4L0 8z',fill:'#a89a8a'}));defs.append(mkr);svg.append(defs);
  pos.forEach((p,i)=>{const q=pos[(i+1)%5],dx=q.x-p.x,dy=q.y-p.y,d=Math.hypot(dx,dy),ux=dx/d,uy=dy/d;
    svg.append(mk('line',{class:'wline',x1:p.x+ux*(p.r+3),y1:p.y+uy*(p.r+3),x2:q.x-ux*(q.r+6),y2:q.y-uy*(q.r+6),pathLength:'1','marker-end':'url(#wa)'}))});
  pos.forEach(p=>{const g=mk('g',{class:'wnode'}),ci=mk('circle',{cx:p.x,cy:p.y,r:p.r,class:cl[p.n]+' wc'+(p.c?'':' zero')});
    const t1=mk('text',{x:p.x,y:p.y+1,class:'wnum','text-anchor':'middle','dominant-baseline':'middle'});t1.textContent=String(p.c);
    const lx=C+(R+p.r+15)*(p.x-C)/R*1,ly=C+(R+p.r+15)*(p.y-C)/R;
    const t2=mk('text',{x:C+(p.x-C)*1.0,y:p.y+p.r+13,class:'wname','text-anchor':'middle'});t2.textContent=p.n;g.append(ci,t1,t2);svg.append(g)});
  const w=E('div',null,'wheel-wrap');w.append(svg);return w}

/* ---------- C-좌 내 사주의 모습 ---------- */
function me(vm){
  const aside=E('aside',null,'dash-me');aside.setAttribute('aria-labelledby','h-me');
  const h=E('h2','내 사주의 모습');h.id='h-me';aside.append(h);
  const st=vm.profile&&vm.profile.story;
  if(st){
    const im=E('div',null,'me-image');im.append(E('p','자연에 빗대면','kicker'),E('h3',st.image,'storytitle'),E('p','전통에서 쓰는 설명용 비유입니다. 결론이나 운의 좋고 나쁨을 정하는 근거가 아닙니다.','small muted'));aside.append(im);
    const el=E('div',null,'me-elements');el.append(E('h4','타고난 기운의 분포'));
    const cl={나무:'e-wood',불:'e-fire',흙:'e-earth',쇠:'e-metal',물:'e-water'},mx=Math.max(...Object.values(st.shape),1);
    const bars=E('div',null,'ebars');A(bars,{role:'group','aria-label':'다섯 가지 기운의 글자 수'});
    Object.entries(st.shape).forEach(([nm,c])=>{const col=E('div',null,'ecol');A(col,{role:'img','aria-label':nm+' 기운 '+c+'개'});col.append(E('span',String(c),'enum'));const bar=E('span',null,'ebar');const f=E('span',null,'efill '+cl[nm]);f.style.height=Math.max(c?12:0,c/mx*100)+'%';bar.append(f);col.append(bar,E('span',nm,'ename'));bars.append(col)});
    el.append(wheel(st.shape,cl),bars,E('p','네 기둥 글자를 다섯 가지 기운으로 센 것입니다. 많고 적음이 곧 좋고 나쁨은 아닙니다.','small muted'));aside.append(el);
    const seasonBeat=(st.beats||[]).find(t=>/필요하다고 보는데/.test(t));
    if(seasonBeat){const sb=E('div',null,'me-season');sb.append(E('h4','계절 균형'),E('p',seasonBeat));aside.append(sb)}
  }
  const ss=vm.ss;
  if(ss){const tr=E('div',null,'me-traits');
    ss.sections.filter(x=>x.key!=='tendency').forEach(x=>{const row=E('div',null,'trait');row.append(E('h4',x.title));const p=E('p',first(x.text));row.append(p);
      const r=rest(x.text);if(r){const more=E('span',' '+r,'more');more.hidden=true;p.append(more);const b=E('button','더 보기','morebtn');b.type='button';A(b,{'aria-expanded':'false'});b.onclick=()=>{more.hidden=!more.hidden;b.textContent=more.hidden?'더 보기':'접기';b.setAttribute('aria-expanded',String(!more.hidden))};row.append(b)}
      tr.append(row)});aside.append(tr)}
  const dt=E('details',null,'fold');dt.append(E('summary','큰 흐름 표와 근거 자리 보기'));
  if(st&&st.timeline&&st.timeline.length){const w=E('div',null,'needline');w.append(E('p','필요한 ‘'+st.need.join('·')+'’의 기운이 들어오는 때(좋은 운이라는 뜻이 아니라 계절 균형의 참고 표시)','small b'));
    const row=E('div',null,'needrow');st.timeline.forEach(r=>{const c=E('div',null,'needcell'+((r.luck_hit||r.year_hit)?' on':''));c.append(E('b',String(r.year)),E('span',(r.luck_hit?'●':'○')+' 큰 흐름','nl'),E('span',(r.year_hit?'●':'○')+' 그해','nl'));
      A(c,{'aria-label':r.year+'년: 10년 큰 흐름 '+(r.luck_hit?'들어옴':'없음')+', 그해의 기운 '+(r.year_hit?'들어옴':'없음')});row.append(c)});w.append(row);dt.append(w)}
  if(ss){const ul=E('ul');ss.palaces.forEach(p=>ul.append(E('li',p.text)));dt.append(E('h4','어느 자리의 어떤 기운인가'),ul,E('p',ss.label,'small muted'))}
  if(st)dt.append(E('p',st.note,'small muted'));
  if(dt.childElementCount>1)aside.append(dt);
  return aside}

/* ---------- C-우 시기별 흐름 ---------- */
function flow(vm,S,sel){
  const sec=E('section',null,'dash-flow');sec.setAttribute('aria-labelledby','h-flow');
  const n=vm.years.length,span=n?(n>1?vm.years[0]+'–'+vm.years[n-1]+'년':vm.years[0]+'년'):'타고난 사주';
  const h=E('h2',span+' 시기별 흐름');h.id='h-flow';sec.append(h);
  if(vm.multi&&vm.v.period&&vm.v.period.summary&&vm.v.period.summary[0])sec.append(E('p',vm.v.period.summary[0],'flow-lead'));
  // 타임라인
  const tl=E('div',null,'timeline'+(n>6?' compact':''));A(tl,{role:'group','aria-label':'연도별 흐름(연도를 눌러 선택)'});
  let lastLine=null;
  vm.years.forEach(y=>{const r=vm.row(y),m=tv(r.tone);const b=E('button',null,'tl-node '+m[2]);b.type='button';b.dataset.year=y;A(b,{'aria-pressed':String(y===S.year),'aria-label':y+'년 '+m[1]+(r.standout?', 가장 달라지는 해':'')});
    const hd=E('span',null,'tl-head');hd.append(E('b',String(y),'tl-year'),E('span',r.standout?'★':'','tl-star'));b.append(hd);
    const sy=E('span',null,'tl-sym');sy.append(E('span',m[0],'sym'),E('span',m[1],'lab'));b.append(sy);
    const ln=r.change||r.line,cur=ln?first(ln):'';if(cur&&cur!==(m[1]||'')){if(cur===lastLine)b.append(E('span','앞 해와 같은 흐름','tl-line same'));else{const sp=E('span',cur,'tl-line');sp.title=ln;b.append(sp)}lastLine=cur}
    const sg=vm.seg(y);if(sg.length){const bar=E('span',null,'tl-seg');A(bar,{'aria-hidden':'true'});sg.forEach((s,i)=>{const p=E('span',null,'segpart '+(i%2?'sb':'sa'));p.style.flexGrow=String(Math.max(s.share,0.04));p.title=s.label+(s.note?' · '+s.note:'');bar.append(p)});b.append(bar);
      if(sg.length>1)b.append(E('span',sg.length+'개 구간','tl-segn'))}
    b.onclick=()=>sel({year:y});tl.append(b)});
  sec.append(tl);
  // 분야 × 연도 표
  const gw=E('div',null,'dgrid-wrap');gw.append(E('h3','분야 × 연도 한눈에 보기'));
  const sc=E('div',null,'dgrid-scroll');const t=E('table',null,'dgrid');A(t,{'aria-label':'분야별·연도별 흐름 표(칸을 눌러 선택)'});
  const hr=E('tr');const th0=E('th','분야');th0.scope='col';hr.append(th0);vm.years.forEach(y=>{const th=E('th',String(y));th.scope='col';th.dataset.year=y;hr.append(th)});const thead=E('thead');thead.append(hr);t.append(thead);
  const tb=E('tbody');vm.domains.forEach(d=>{const r=E('tr');const nm=E('th',d.name);nm.scope='row';r.append(nm);
    vm.years.forEach(y=>{const b=vm.block(y,d.domain),td=E('td');td.dataset.year=y;td.dataset.domain=d.domain;if(b){const m=tv(b.tone);td.className=m[2];const bt=E('button',null,'cell');bt.type='button';A(bt,{'aria-label':y+'년 '+d.name+' '+m[1],'data-year':y,'data-domain':d.domain});bt.append(E('span',m[0],'sym'),E('span',m[1],'lab'));bt.onclick=()=>sel({year:y,domain:d.domain});td.append(bt)}r.append(td)});tb.append(r)});
  t.append(tb);sc.append(t);gw.append(sc);
  const lg=E('p',null,'dlegend');['opportunity','cautious','mixed','thin','quiet','steady'].forEach(k=>{const m=TV[k];const sp=E('span',null,m[2]);sp.textContent=m[0]+' '+m[1];lg.append(sp)});gw.append(lg);
  gw.append(E('p','기회·주의는 그해의 구조 변화가 한쪽으로 뚜렷할 때만 표시합니다. 좋은 일·나쁜 일이 일어난다는 뜻이 아니며 확률이나 점수도 아닙니다. 근거가 부족하면 ‘근거 부족’으로 두고 억지로 방향을 정하지 않습니다.','small muted'));
  sec.append(gw);
  // 선택한 해 패널
  const yp=E('div',null,'year-panel');yp.id='dash-year-panel';A(yp,{'aria-live':'polite'});sec.append(yp);
  return sec}

function fillYearPanel(vm,S,root){
  const yp=root.querySelector('#dash-year-panel');if(!yp)return;yp.textContent='';
  const y=S.year;if(y===null||y===undefined){return}
  const r=vm.row(y),m=tv(r.tone);
  const hd=E('div',null,'yp-head');hd.append(E('h3',y+'년'),E('span',m[0]+' '+m[1],'chip '+m[2]));if(r.standout)hd.append(E('span','★ 가장 달라지는 해','chip star'));yp.append(hd);
  if(r.change)yp.append(E('p',r.change,'yp-change'));
  if(r.caution)yp.append(E('p','주의: '+r.caution,'yp-caution'));
  if(r.why)yp.append(E('p','왜 두드러지나요? '+r.why,'yp-why'));
  const sg=vm.seg(y);
  if(sg.length>1){const w=E('div',null,'yp-seg');w.append(E('h4','이 해의 구간'));const ul=E('ul');sg.forEach(s=>{const li=E('li');li.append(E('b',s.label),document.createTextNode(' ('+s.days+'일)'+(s.note?' · '+s.note:'')));ul.append(li)});w.append(ul);
    w.append(E('p','구간이 나뉘면 짧은 구간의 변화를 한 해 전체의 특징으로 읽지 않습니다.','small muted'));yp.append(w)}
  const th=vm.theme(y);
  if(th){const w=E('div',null,'yp-theme');w.append(E('h4','이 해의 주제'),E('p',th.theme+' '+th.link),E('p','준비해 볼 일: '+th.prep,'yprep'));yp.append(w)}
}

/* ---------- D 분야별 해석 ---------- */
function domains(vm,S,sel){
  const sec=E('section',null,'dash-domains');sec.setAttribute('aria-labelledby','h-dom');
  const h=E('h2','분야별 해석');h.id='h-dom';sec.append(h);
  const sub=E('p',null,'dom-sub');sub.id='dash-dom-sub';sec.append(sub);
  const tabs=E('div',null,'dtabs');A(tabs,{role:'tablist','aria-label':'분야 선택'});
  vm.domains.forEach(d=>{const b=E('button',null,'dtab');b.type='button';b.id='dtab-'+d.domain;b.dataset.domain=d.domain;A(b,{role:'tab','aria-controls':'dash-dom-panel'});b.append(E('span',d.name,'dn'),E('span','','dsym'));b.onclick=()=>sel({domain:d.domain});
    b.onkeydown=ev=>{const k=ev.key,all=[...tabs.querySelectorAll('.dtab')],i=all.indexOf(b);let j=null;if(k==='ArrowRight')j=(i+1)%all.length;else if(k==='ArrowLeft')j=(i-1+all.length)%all.length;else if(k==='Home')j=0;else if(k==='End')j=all.length-1;if(j!==null){ev.preventDefault();all[j].focus();sel({domain:all[j].dataset.domain})}};tabs.append(b)});
  sec.append(tabs);
  const pn=E('div',null,'dpanel');pn.id='dash-dom-panel';A(pn,{role:'tabpanel','aria-live':'polite'});sec.append(pn);return sec}

function fillDomain(vm,S,root){
  const pn=root.querySelector('#dash-dom-panel');if(!pn)return;pn.textContent='';
  const sub=root.querySelector('#dash-dom-sub');if(sub)sub.textContent=(S.year!==null&&S.year!==undefined?S.year+'년 기준 · ':'')+'위의 표에서 연도와 분야를 바꿔 보세요.';
  root.querySelectorAll('.dtab').forEach(b=>{const on=b.dataset.domain===S.domain;b.setAttribute('aria-selected',String(on));b.tabIndex=on?0:-1;const blk=vm.block(S.year,b.dataset.domain),m=blk?tv(blk.tone):null;b.querySelector('.dsym').textContent=m?m[0]:''});
  const b=vm.block(S.year,S.domain);if(!b){pn.append(E('p','이 분야·연도의 해석이 없습니다.','muted'));return}
  const m=tv(b.tone);
  pn.setAttribute('aria-labelledby','dtab-'+S.domain);
  const hd=E('div',null,'dp-head');hd.append(E('h3',b.name),E('span',m[0]+' '+m[1],'chip '+m[2]));pn.append(hd);
  pn.append(E('p',b.headline,'dp-headline'));
  const cols=E('div',null,'dp-cols');const L=E('div',null,'dp-main'),R=E('div',null,'dp-side');
  (b.story||[]).forEach(t=>L.append(E('p',t,'dp-story')));
  [].concat(b.counter||[]).filter(Boolean).slice(0,2).forEach(t=>L.append(E('p','다만 '+String(t).replace(/^다만\s*/,''),'dp-counter')));
  const storyText=(b.story||[]).join(' ');
  const per=((b.why&&b.why.period)||[]).filter(t=>t&&storyText.indexOf(t.slice(0,18))<0);
  if(per.length){R.append(E('h4','이 해의 변화'));const ul=E('ul');per.slice(0,2).forEach(t=>ul.append(E('li',t)));R.append(ul)}
  if((b.think||[]).length){R.append(E('h4','현실에서 생각해 볼 점'));const ul=E('ul');b.think.forEach(t=>ul.append(E('li',t)));R.append(ul)}
  cols.append(L,R);pn.append(cols);
  const w=b.why||{},d=E('details',null,'fold');d.append(E('summary','왜 그렇게 해석하나요?'));
  [['타고난 사주에서',w.natal],['이 시기에는',w.period],['반대로 보는 이유',w.against]].forEach(([lab,arr])=>{if(arr&&arr.length){d.append(E('h4',lab));const ul=E('ul');arr.forEach(t=>ul.append(E('li',t)));d.append(ul)}});
  if(w.nature)d.append(E('p',w.nature,'small muted'));
  pn.append(d)}

/* ---------- 조립 ---------- */
function build(a){
  const vm=buildVM(a),S=makeState(vm),root=E('div',null,'dash');root.id='dash';
  let started=false,prevYear=null,prevDomain=null;
  function sel(p){
    if(p.year!==undefined&&p.year!==null)S.year=p.year;if(p.domain)S.domain=p.domain;
    const prevNode=root.querySelector('.tl-node[aria-pressed="true"]');
    root.querySelectorAll('.tl-node').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.year)===S.year)));
    const nextNode=root.querySelector('.tl-node[aria-pressed="true"]');
    if(started&&window.MingliMotion&&prevNode&&nextNode&&prevNode!==nextNode)window.MingliMotion.slide(root.querySelector('.timeline'),prevNode,nextNode);
    root.querySelectorAll('.dgrid th[data-year]').forEach(th=>th.classList.toggle('selcol',Number(th.dataset.year)===S.year));
    root.querySelectorAll('.dgrid td').forEach(td=>{const on=Number(td.dataset.year)===S.year;td.classList.toggle('selcol',on);td.classList.toggle('selcell',on&&td.dataset.domain===S.domain)});
    root.querySelectorAll('.dgrid .cell').forEach(c=>c.setAttribute('aria-pressed',String(Number(c.dataset.year)===S.year&&c.dataset.domain===S.domain)));
    fillYearPanel(vm,S,root);fillDomain(vm,S,root);
    if(started&&window.MingliMotion){if(S.year!==prevYear)window.MingliMotion.ink(root.querySelector('#dash-year-panel'),nextNode);if(S.year!==prevYear||S.domain!==prevDomain)window.MingliMotion.panel(root.querySelector('#dash-dom-panel'))}
    prevYear=S.year;prevDomain=S.domain;started=true;
    const nm=(vm.domains.find(d=>d.domain===S.domain)||{}).name||'';
    window.MingliSel={year:S.year,domain:S.domain,domainName:nm};
    const cx=document.getElementById('ctxline');if(cx)cx.textContent='지금 보고 있는 것: '+(S.year?S.year+'년 · ':'')+nm;
    if(typeof window.MingliChips==='function')window.MingliChips(a,window.MingliSel);
  }
  root.append(controlBar(vm),conclusion(vm));
  const grid=E('div',null,'dash-grid');grid.append(me(vm),flow(vm,S,sel));root.append(grid,domains(vm,S,sel));
  sel({});
  return root}

window.MingliDash={build,buildVM,tv:tv};
})();
