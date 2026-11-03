/* 회원 기능(일회성 모드 화면에서만 동작): 가입·로그인, 분석 저장, 내 리포트 목록·재열람·후속 상담·내보내기·삭제, 계정 삭제.
   로그인하지 않으면 아무 것도 바꾸지 않는다(일회성 분석은 그대로, 브라우저 저장소·쿠키 사용 없음). 토큰은 로그인 후에만 sessionStorage 에 둔다(탭을 닫으면 삭제). */
(function(){
if(typeof ONESHOT==='undefined'||!ONESHOT)return;
const box=$('acct');if(!box)return;
(async()=>{const h=await fetch('/api/v1/health').then(r=>r.json()).catch(()=>null);if(h&&h.accounts){box.hidden=false;REG=h.registration||'open';if(REG==='closed'){const g=$('acct-reg');if(g)g.hidden=true}else if(REG==='invite'){const pw=$('acct-pw'),inp=document.createElement('input');inp.id='acct-inv';inp.type='password';inp.placeholder='초대 코드(가입할 때만)';inp.maxLength=100;inp.autocomplete='off';pw.parentNode.parentNode.after(inp)}}})();
let REG='open';
let AUTH=null,reportId=null,curPre=null,curYears=[];
try{const t=sessionStorage.getItem('mingli_token');if(t)AUTH={token:t,email:sessionStorage.getItem('mingli_email')||''}}catch(e){}
const msg=(t,bad)=>{const m=$('acct-msg');m.textContent=t||'';m.className='small '+(bad?'bad':'muted')};
const H=()=>({'Content-Type':'application/json','Authorization':'Bearer '+AUTH.token});
const kor=r=>{const d=r.j&&r.j.detail;return d&&d.message?d.message:(typeof d==='string'?d:'요청을 처리하지 못했습니다.')};

/* call 래핑: 로그인 상태에서만 일회성 API 호출을 저장형 API 로 바꾼다 */
const origCall=call;
call=async function(path,opt){
  if(!AUTH)return origCall(path,opt);
  const body=opt&&opt.body?JSON.parse(opt.body):null;
  if(path==='/api/v1/oneshot/analyze'){return origCall('/api/v1/reports',{method:'POST',headers:H(),body:JSON.stringify({title:'',request:body})})}
  if(path==='/api/v1/oneshot/ask'&&reportId){return origCall('/api/v1/reports/'+reportId+'/ask',{method:'POST',headers:H(),body:JSON.stringify({question:body.question,years:body.years&&body.years.length?body.years:null,domains:null,focus_year:body.focus_year||null,focus_domain:body.focus_domain||null,focus_month:body.focus_month||null})}).then(r=>{if(r.ok)r.j=r.j.answer;return r})}
  if(path==='/api/v1/oneshot/reality'&&reportId){return origCall('/api/v1/reports/'+reportId+'/reality',{method:'POST',headers:H(),body:JSON.stringify(body.event)})}
  return origCall(path,opt)};
const origBegin=begin;
begin=function(j){origBegin(j);if(AUTH)setTimeout(fbBar,0);curPre=j.precommit||curPre;curYears=(j.answer&&j.answer.years)||curYears;if(AUTH&&j.id){reportId=j.id;const n=$('cover').querySelector('p.small.muted:last-child');if(n)n.textContent='이 분석은 암호화되어 내 리포트에 저장되었습니다. 출생 정보 원문은 저장하지 않았습니다. 나중에 로그인하면 다시 열어 후속 질문을 이어갈 수 있습니다.';refresh()}};

function show(){const on=!!AUTH;$('acct-out').hidden=on;$('acct-in').hidden=!on;if(on){$('acct-email').textContent=AUTH.email}}
async function refresh(){if(!AUTH)return;const r=await origCall('/api/v1/reports',{headers:H()});if(r.status===401){logoutLocal('세션이 만료되었습니다. 다시 로그인하세요.');return}
  if(!r.ok)return;const L=r.j.reports;$('acct-n').textContent=L.length;const u=$('mylist');u.textContent='';
  if(!L.length)u.append(el('li','저장한 리포트가 없습니다. 로그인한 상태로 분석하면 자동으로 저장됩니다.','muted'));
  L.forEach(x=>{const li=el('li');const when=new Date(x.created_at*1000).toLocaleString('ko-KR',{dateStyle:'medium',timeStyle:'short'});
    li.append(el('b',x.title),document.createTextNode(' · '+when+' · '+(x.verification_status||'')+' '));
    const bo=el('button','열기','sec');bo.type='button';bo.onclick=()=>openReport(x.id);
    const be=el('button','내보내기(.md)','sec');be.type='button';be.onclick=()=>exportReport(x.id);
    const bd=el('button','삭제','sec');bd.type='button';bd.onclick=()=>delReport(x.id);
    li.append(bo,document.createTextNode(' '),be,document.createTextNode(' '),bd);u.append(li)})}
async function openReport(id){const r=await origCall('/api/v1/reports/'+id,{headers:H()});if(!r.ok){msg(kor(r),true);return}
  const views=r.j.turns.filter(t=>t.kind==='answer'&&t.body.view);const lastView=views.length?views[views.length-1].body.answer:null;
  origBegin({answer:lastView||r.j.answer,precommit:r.j.precommit});reportId=id;if(AUTH)fbBar();curPre=r.j.precommit;curYears=(lastView||r.j.answer).years||[];
  const n=$('cover').querySelector('p.small.muted:last-child');if(n)n.textContent='저장된 리포트를 다시 열었습니다('+r.j.title+'). 아래에서 후속 질문을 이어갈 수 있습니다.';
  r.j.turns.forEach(t=>{if(t.kind==='feedback'||(t.kind==='answer'&&t.body.view))return;if(t.kind==='answer')renderRecord(t.body.answer,t.body.question);else{localRecords.push({kind:'reality',text:(t.body.event.type||'')+' '+(t.body.event.year||'')+'년 → '+t.body.result.outcome})}});}
async function exportReport(id){const r=await fetch('/api/v1/reports/'+id+'/export',{headers:{'Authorization':'Bearer '+AUTH.token}});if(!r.ok){msg('내보내기에 실패했습니다.',true);return}
  const b=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='명리_리포트_'+id.slice(0,8)+'.md';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
async function delReport(id){const r=await origCall('/api/v1/reports/'+id,{method:'DELETE',headers:H()});if(r.ok||r.status===204){if(reportId===id){reportId=null;curPre=null;curYears=[];clearScreen()}msg('리포트를 삭제했습니다.');refresh()}else msg(kor(r),true)}
function clearScreen(){window.MingliSel=null;document.body.classList.remove('has-dash');const cx=$('ctxline');if(cx)cx.textContent='';/* 이전 사용자의 목록·리포트·기록이 화면에 남지 않게 한다(공용 기기 보호) */
  $('mylist').textContent='';$('acct-n').textContent='0';
  ['out','cover','status','histout','evr'].forEach(i=>{const e=$(i);if(e)e.textContent=''});
  const k=$('keypoints');if(k)k.remove();$('report').hidden=true;$('session').hidden=true;$('status').hidden=true;
  localRecords.length=0;lastBody=null;
  ['#staticbanner','main > p.kicker','main > h1','main > p.lead','main > ol.steps'].forEach(q=>{const e=document.querySelector(q);if(e)e.hidden=false});
  $('f').after($('acct'));  $('f').hidden=false;$('formbar').hidden=true;const n=$('intronote');if(n)n.hidden=false;
  document.querySelector('.steps li:nth-child(2)').removeAttribute('aria-current');document.querySelector('.steps li:nth-child(1)').setAttribute('aria-current','step')}
function logoutLocal(m){AUTH=null;reportId=null;try{sessionStorage.removeItem('mingli_token');sessionStorage.removeItem('mingli_email')}catch(e){}clearScreen();show();msg(m||'')}
async function auth(kind){const email=$('acct-mail').value.trim(),pw=$('acct-pw').value;
  const r=await origCall('/api/v1/auth/'+kind,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,password:pw,invite:($('acct-inv')&&$('acct-inv').value)||null})});
  if(!r.ok){msg(kor(r),true);return}
  AUTH={token:r.j.token,email:r.j.user.email};try{sessionStorage.setItem('mingli_token',AUTH.token);sessionStorage.setItem('mingli_email',AUTH.email)}catch(e){}
  $('acct-pw').value='';msg('');show();refresh()}
$('acct-login').onclick=()=>auth('login');$('acct-reg').onclick=()=>auth('register');
$('acct-logout').onclick=async()=>{await origCall('/api/v1/auth/logout',{method:'POST',headers:H()});logoutLocal('로그아웃했습니다.')};
$('delacct').onclick=async()=>{const r=await origCall('/api/v1/me',{method:'DELETE',headers:H(),body:JSON.stringify({password:$('delpw').value})});
  if(r.ok||r.status===204){$('delpw').value='';logoutLocal('계정과 저장된 모든 리포트를 삭제했습니다.')}else msg(kor(r),true)};
/* 내 평가(1~5점): 해석 내용이 아니라 점수와 짧은 메모만 저장. 상담 품질 ‘검증’이 아니라 개인 사용 기록 */
function fbBar(){
  let f=$('fbk');if(f){const m0=$('fbm');if(m0)m0.textContent='';return f}const anchor=$('chips');if(!anchor||!anchor.parentNode)return null;
  f=document.createElement('div');f.id='fbk';f.className='small';f.setAttribute('role','group');f.setAttribute('aria-label','이 풀이에 대한 내 평가');
  f.append(el('span','이 풀이가 도움이 되었나요? '));
  for(let i=1;i<=5;i++){const bt=el('button',String(i),'sec');bt.type='button';bt.setAttribute('aria-label',i+'점');bt.onclick=async()=>{
    if(!AUTH||!reportId)return;const note=($('fbn')&&$('fbn').value)||'';
    const r=await origCall('/api/v1/reports/'+reportId+'/feedback',{method:'POST',headers:H(),body:JSON.stringify({rating:i,target:'reading',note:note})});
    $('fbm').textContent=r.ok?'평가를 저장했습니다. 고맙습니다.':kor(r)};f.append(bt,document.createTextNode(' '))}
  const n=document.createElement('input');n.id='fbn';n.maxLength=300;n.placeholder='한 줄 메모(선택)';n.setAttribute('aria-label','메모');f.append(n);
  const m=el('span','','muted');m.id='fbm';m.setAttribute('role','status');f.append(document.createTextNode(' '),m);anchor.parentNode.insertBefore(f,anchor);return f}
/* 저장된 명식으로 연도·기간만 바꿔 다시 풀이(출생 정보 재입력 없음) */
async function reYears(years){
  if(years.some(y=>y<1901||y>2049)){msg('분석 연도는 1901~2049년 사이입니다.',true);return}
  const b=$('busy');if(b){b.textContent='저장된 명식으로 다시 풀이하는 중…';b.hidden=false}
  const r=await origCall('/api/v1/reports/'+reportId+'/analyze',{method:'POST',headers:H(),body:JSON.stringify({years})});
  if(b)b.hidden=true;
  if(!r.ok){msg(kor(r),true);return}
  origBegin({answer:r.j.answer,precommit:curPre});curYears=r.j.answer.years||years;
  const n=$('cover').querySelector('p.small.muted:last-child');if(n)n.textContent='저장된 명식으로 '+curYears[0]+(curYears.length>1?'~'+curYears[curYears.length-1]:'')+'년을 다시 풀었습니다. 출생 정보는 다시 입력하지 않아도 됩니다.'}
const yn=(id,fn)=>{const e=$(id);if(e)e.addEventListener('click',ev=>{if(!AUTH||!reportId||!curYears.length)return;ev.stopImmediatePropagation();ev.preventDefault();fn()},true)};
yn('yprev',()=>reYears(curYears.map(y=>y-1)));yn('ynext',()=>reYears(curYears.map(y=>y+1)));
yn('to1',()=>reYears([curYears[0]]));yn('to5',()=>reYears(Array.from({length:5},(_,i)=>curYears[0]+i)));yn('to10',()=>reYears(Array.from({length:10},(_,i)=>curYears[0]+i)));
show();refresh();
})();
