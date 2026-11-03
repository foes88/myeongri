/* 명리 明理 — 움직임 계층 (v10.2). Motion(고정 버전 배포본, assets/vendor/motion-14.9.0.js) 위에서 '읽는 순서를 안내하는' 움직임만 만든다.
   원칙
   - 장식이 아니라 상태 변화를 이해시키는 용도: 결과가 나타나는 순서(결론 → 특징 → 내 사주 → 시기 흐름), 연도·분야 선택 시 내용 교체, 오행 막대의 크기, 구간 막대의 비율.
   - 사용자가 '움직임 줄이기'를 켰거나 Motion 을 못 불러오면 아무 것도 하지 않는다(내용은 이미 최종 상태).
   - 내용·판정과 무관하다: 이 파일은 DOM 의 opacity/transform/height 만 건드리고 텍스트·데이터를 읽거나 바꾸지 않는다.
   - 끝나면 인라인 스타일을 모두 치워 최종 상태가 CSS 와 같도록 한다(접근성 도구·인쇄·테스트에 잔여 변형 없음). */
(function(){
'use strict';
const M=(typeof window.Motion==='object'&&window.Motion)||null;
const mq=window.matchMedia?window.matchMedia('(prefers-reduced-motion: reduce)'):null;
const on=()=>!!(M&&typeof M.animate==='function'&&!(mq&&mq.matches));
const EASE=[0.22,0.61,0.36,1];
const arr=x=>x?(x.length!==undefined&&typeof x!=='string'&&!(x instanceof Element)?Array.from(x):[x]):[];
/* Motion 은 끝날 때 마지막 값을 인라인 스타일로 확정한다 → 그 확정이 끝난 뒤(두 프레임 + 짧은 지연)에 치워야 흔적이 남지 않는다 */
const later=fn=>requestAnimationFrame(()=>requestAnimationFrame(()=>setTimeout(fn,30)));
const clean=els=>els.forEach(e=>{if(e&&e.style){e.style.opacity='';e.style.transform='';e.style.transformOrigin='';e.style.willChange=''}});

/* 나타남: 처음 상태를 즉시 적용한 뒤 목표로. 실패하면 바로 최종 상태로 둔다. */
function appear(target,o){
  const els=arr(target).filter(Boolean);if(!els.length||!on())return null;
  o=o||{};const y=o.y===undefined?10:o.y,dur=o.duration||0.45,delay=o.delay||0,gap=o.stagger||0;
  try{
    els.forEach(e=>{e.style.opacity='0';e.style.transform=y?'translateY('+y+'px)':'';e.style.willChange='opacity, transform'});
    const a=M.animate(els,{opacity:[0,1],transform:[y?'translateY('+y+'px)':'none','none']},{duration:dur,ease:EASE,delay:gap?M.stagger(gap,{startDelay:delay}):delay});
    const done=()=>later(()=>clean(els));
    if(a&&a.finished&&a.finished.then)a.finished.then(done,done);else setTimeout(done,(dur+delay+gap*els.length)*1000+60);
    return a}
  catch(e){clean(els);return null}}

/* 막대가 차오름(오행 글자 수의 크기를 눈으로 보이게) */
function grow(fills,o){
  if(!on())return;o=o||{};
  arr(fills).forEach((f,i)=>{try{const t=f.style.height||'0%';f.style.height='0%';
    const a=M.animate(f,{height:['0%',t]},{type:'spring',stiffness:170,damping:22,delay:(o.delay||0)+i*0.06});
    const fin=()=>{f.style.height=t};if(a&&a.finished&&a.finished.then)a.finished.then(fin,fin);else fin()}catch(e){}})}

/* 구간 막대: 해 안의 실제 구간 비율이 왼쪽에서부터 펼쳐짐 */
function sweep(els,o){
  if(!on())return;o=o||{};const list=arr(els);if(!list.length)return;
  try{list.forEach(e=>{e.style.transformOrigin='left center';e.style.transform='scaleX(0)'});
    const a=M.animate(list,{transform:['scaleX(0)','scaleX(1)']},{duration:0.5,ease:EASE,delay:M.stagger(0.04,{startDelay:o.delay||0})});
    const d=()=>later(()=>clean(list));if(a&&a.finished&&a.finished.then)a.finished.then(d,d);else setTimeout(d,800)}catch(e){clean(list)}}

/* 연도·분야를 바꿀 때 내용이 갈아 끼워졌음을 알려 주는 짧은 전환(내용은 이미 바뀐 뒤) */
function panel(el){if(!el)return;appear(el,{y:6,duration:0.28})}

/* 결과 화면이 나타나는 순서 = 읽는 순서 */
function results(root){
  if(!on()||!root)return;
  const q=s=>root.querySelectorAll(s),one=s=>root.querySelector(s);
  appear(one('.dash-bar'),{y:0,duration:0.3});
  appear(one('.dash-conclusion'),{y:12,duration:0.5,delay:0.05});
  appear(q('.trio-item'),{y:8,duration:0.4,delay:0.25,stagger:0.09});
  appear(q('.dash-me > *'),{y:8,duration:0.4,delay:0.4,stagger:0.07});
  grow(q('.me-elements .efill'),{delay:0.55});
  appear(q('.dash-flow > h2, .dash-flow > .flow-lead'),{y:8,duration:0.4,delay:0.45,stagger:0.07});
  appear(q('.timeline .tl-node'),{y:10,duration:0.4,delay:0.55,stagger:0.05});
  sweep(q('.timeline .segpart'),{delay:0.75});
  appear(q('.dgrid-wrap > h3, .dlegend'),{y:6,duration:0.35,delay:0.7,stagger:0.05});
  appear(q('.dgrid .cell'),{y:0,duration:0.3,delay:0.75,stagger:0.018});
  appear(one('.year-panel'),{y:8,duration:0.4,delay:0.9});
  const dom=one('.dash-domains');
  if(dom&&typeof M.inView==='function'){try{M.inView(dom,()=>{appear(dom.children,{y:10,duration:0.45,stagger:0.07});return undefined},{margin:'0px 0px -12% 0px'})}catch(e){}}
}

/* 입력 화면: 제목·안내 → 입력 구역이 위에서 아래로, 스크롤로 보일 때 나타남 */
function intro(){
  if(!on())return;
  appear(document.querySelectorAll('main > .kicker, main > h1, main > p.lead, main > ol.steps'),{y:10,duration:0.5,stagger:0.08});
  if(typeof M.inView==='function'){document.querySelectorAll('#f > fieldset, #f > .formrow, #f > p').forEach(fs=>{try{M.inView(fs,()=>{appear(fs,{y:12,duration:0.45});return undefined},{margin:'0px 0px -8% 0px'})}catch(e){}})}
}

/* 고정 컨트롤 바: 내용이 아래로 지나가면 경계선 그림자가 생겨 '떠 있음'을 알림(CSS 클래스만 바꾼다) */
let stickyOff=null;
function sticky(bar){
  if(stickyOff){try{stickyOff()}catch(e){}stickyOff=null}
  if(!bar)return;
  const upd=()=>bar.classList.toggle('stuck',bar.getBoundingClientRect().top<=1&&window.scrollY>40);
  window.addEventListener('scroll',upd,{passive:true});upd();
  stickyOff=()=>window.removeEventListener('scroll',upd);
}

if(document.getElementById('f'))intro();
window.MingliMotion={enabled:on,appear,grow,sweep,panel,results,intro,sticky,version:M?'motion@14.9.0':null};
})();
