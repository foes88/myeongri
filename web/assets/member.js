/* 회원 기능(일회성 모드 화면에서만 동작): 가입·로그인, 분석 저장, 내 리포트 목록·재열람·후속 상담·내보내기·삭제, 계정 삭제.
   로그인하지 않으면 아무 것도 바꾸지 않는다(일회성 분석은 그대로, 브라우저 저장소·쿠키 사용 없음). 토큰은 로그인 후에만 sessionStorage 에 둔다(탭을 닫으면 삭제). */
(function(){
if(typeof ONESHOT==='undefined'||!ONESHOT)return;
const box=$('acct');if(!box)return;
(async()=>{const h=await fetch('/api/v1/health').then(r=>r.json()).catch(()=>null);if(h&&h.accounts)box.hidden=false})();
let AUTH=null,reportId=null;
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
  if(path==='/api/v1/oneshot/ask'&&reportId){return origCall('/api/v1/reports/'+reportId+'/ask',{method:'POST',headers:H(),body:JSON.stringify({question:body.question,years:body.years&&body.years.length?body.years:null,domains:null})}).then(r=>{if(r.ok)r.j=r.j.answer;return r})}
  if(path==='/api/v1/oneshot/reality'&&reportId){return origCall('/api/v1/reports/'+reportId+'/reality',{method:'POST',headers:H(),body:JSON.stringify(body.event)})}
  return origCall(path,opt)};
const origBegin=begin;
begin=function(j){origBegin(j);if(AUTH&&j.id){reportId=j.id;const n=$('cover').querySelector('p.small.muted:last-child');if(n)n.textContent='이 분석은 암호화되어 내 리포트에 저장되었습니다. 출생 정보 원문은 저장하지 않았습니다. 나중에 로그인하면 다시 열어 후속 질문을 이어갈 수 있습니다.';refresh()}};

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
  origBegin({answer:r.j.answer,precommit:r.j.precommit});reportId=id;
  const n=$('cover').querySelector('p.small.muted:last-child');if(n)n.textContent='저장된 리포트를 다시 열었습니다('+r.j.title+'). 아래에서 후속 질문을 이어갈 수 있습니다.';
  r.j.turns.forEach(t=>{if(t.kind==='answer')renderRecord(t.body.answer,t.body.question);else{localRecords.push({kind:'reality',text:(t.body.event.type||'')+' '+(t.body.event.year||'')+'년 → '+t.body.result.outcome})}});}
async function exportReport(id){const r=await fetch('/api/v1/reports/'+id+'/export',{headers:{'Authorization':'Bearer '+AUTH.token}});if(!r.ok){msg('내보내기에 실패했습니다.',true);return}
  const b=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='명리_리포트_'+id.slice(0,8)+'.md';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
async function delReport(id){const r=await origCall('/api/v1/reports/'+id,{method:'DELETE',headers:H()});if(r.ok||r.status===204){if(reportId===id)reportId=null;msg('리포트를 삭제했습니다.');refresh()}else msg(kor(r),true)}
function logoutLocal(m){AUTH=null;reportId=null;try{sessionStorage.removeItem('mingli_token');sessionStorage.removeItem('mingli_email')}catch(e){}show();msg(m||'')}
async function auth(kind){const email=$('acct-mail').value.trim(),pw=$('acct-pw').value;
  const r=await origCall('/api/v1/auth/'+kind,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,password:pw})});
  if(!r.ok){msg(kor(r),true);return}
  AUTH={token:r.j.token,email:r.j.user.email};try{sessionStorage.setItem('mingli_token',AUTH.token);sessionStorage.setItem('mingli_email',AUTH.email)}catch(e){}
  $('acct-pw').value='';msg('');show();refresh()}
$('acct-login').onclick=()=>auth('login');$('acct-reg').onclick=()=>auth('register');
$('acct-logout').onclick=async()=>{await origCall('/api/v1/auth/logout',{method:'POST',headers:H()});logoutLocal('로그아웃했습니다.')};
$('delacct').onclick=async()=>{const r=await origCall('/api/v1/me',{method:'DELETE',headers:H(),body:JSON.stringify({password:$('delpw').value})});
  if(r.ok||r.status===204){$('delpw').value='';logoutLocal('계정과 저장된 모든 리포트를 삭제했습니다.')}else msg(kor(r),true)};
show();refresh();
})();
