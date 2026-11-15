import {useCallback,useEffect,useRef,useState} from 'react';
import {Building2,CheckCircle2,ClipboardCheck,FilePlus2,Play,RefreshCw,ShieldCheck,Users,AlertTriangle} from 'lucide-react';
import {authFetch,API_BASE} from './authClient';
import './workspace-control.css';
import Tracebook from './Tracebook';

type Role='admin'|'editor'|'reviewer'|'creator';
type Workspace={id:string;name:string;role:Role;created_at:string};
type Member={user_id:string;display_name:string;email:string;role:Role;joined_at:string};
type Draft={id:string;title:string;channel:string;author_id:string;version:number;created_at:string};
type Version={id:string;number:number;content:string;created_at:string};
type Detail=Draft&{current:Version;versions:Version[]};
type Finding={id:string;rule_code:string;title:string;matched_text:string;start:number;end:number;suggestion:string};
type Run={run_id:string;version_number:number;checked_rules:number;findings:Finding[]};
type Review={id:string;decision:string;comment:string;actor_id:string;version_id:string;created_at:string};
const writable=(r:Role)=>r==='admin'||r==='editor'||r==='creator';
const reviewer=(r:Role)=>r==='admin'||r==='reviewer';
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const r=await authFetch(`${API_BASE}${path}`,{...init,headers:{'Content-Type':'application/json',...init.headers}});
  if(!r.ok){const d=await r.json().catch(()=>null);throw new Error(typeof d?.detail==='string'?d.detail:`Request failed (${r.status})`);}
  return r.json() as Promise<T>;
}
const json=(body:unknown):RequestInit=>({method:'POST',body:JSON.stringify(body)});

export default function WorkspaceControl({focusDraft}:{focusDraft?:{workspaceId:string;draftId:string}|null}){
 const focusedOnce=useRef('');
 const [workspaces,setWorkspaces]=useState<Workspace[]>([]);
 const [active,setActive]=useState('');
 const [members,setMembers]=useState<Member[]>([]);
 const [drafts,setDrafts]=useState<Draft[]>([]);
 const [selected,setSelected]=useState('');
 const [detail,setDetail]=useState<Detail|null>(null);
 const [run,setRun]=useState<Run|null>(null);
 const [reviews,setReviews]=useState<Review[]>([]);
 const [workspaceName,setWorkspaceName]=useState('');
 const [title,setTitle]=useState('');
 const [channel,setChannel]=useState('social');
 const [content,setContent]=useState('');
 const [editContent,setEditContent]=useState('');
 const [comment,setComment]=useState('');
 const [memberId,setMemberId]=useState('');
 const [memberRole,setMemberRole]=useState<Role>('creator');
 const [activityTick,setActivityTick]=useState(0);
 const [busy,setBusy]=useState(false);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState('');
 const [success,setSuccess]=useState('');
 const current=workspaces.find(w=>w.id===active);
 const root=(suffix='')=>`/workspaces/${encodeURIComponent(active)}${suffix}`;
 const execute=async(fn:()=>Promise<void>)=>{setBusy(true);setError('');setSuccess('');try{await fn()}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
 const refreshWorkspaces=useCallback(async()=>{
   const list=await api<Workspace[]>('/workspaces');setWorkspaces(list);
   setActive(old=>focusDraft&&list.some(w=>w.id===focusDraft.workspaceId)?focusDraft.workspaceId:(list.some(w=>w.id===old)?old:(list[0]?.id||'')));
 },[focusDraft?.workspaceId]);
 useEffect(()=>{refreshWorkspaces().catch(e=>setError(String(e))).finally(()=>setLoading(false))},[refreshWorkspaces]);
 const refreshWorkspace=useCallback(async(id:string)=>{
  const key=encodeURIComponent(id);
  const [m,d]=await Promise.all([api<Member[]>(`/workspaces/${key}/members`),api<Draft[]>(`/workspaces/${key}/drafts`)]);
  setMembers(m);setDrafts(d);
 },[]);
 useEffect(()=>{
  setSelected('');setDetail(null);setRun(null);setReviews([]);setMembers([]);setDrafts([]);
  if(active)refreshWorkspace(active).catch(e=>setError(e instanceof Error?e.message:String(e)));
 },[active,refreshWorkspace]);
 async function openDraft(id:string){
  const [d,h]=await Promise.all([api<Detail>(root(`/drafts/${encodeURIComponent(id)}`)),api<Review[]>(root(`/drafts/${encodeURIComponent(id)}/reviews`))]);
  setSelected(id);setDetail(d);setEditContent(d.current.content);setReviews(h);setRun(null);
 }
 // Deep-link from the PostgreSQL Draft Radar. The backend still enforces scope.
 useEffect(()=>{
  if(!focusDraft || active!==focusDraft.workspaceId || !drafts.some(d=>d.id===focusDraft.draftId))return;
  const key=`${focusDraft.workspaceId}:${focusDraft.draftId}`;
  if(focusedOnce.current===key)return;
  focusedOnce.current=key;
  void execute(()=>openDraft(focusDraft.draftId));
 },[focusDraft?.workspaceId,focusDraft?.draftId,active,drafts]);
 async function makeWorkspace(){await execute(async()=>{
  const w=await api<Workspace>('/workspaces',json({name:workspaceName.trim()}));
  setWorkspaceName('');await refreshWorkspaces();setActive(w.id);setSuccess(`Workspace “${w.name}” created. You are its administrator.`);
 });}
 async function makeDraft(){await execute(async()=>{
  const d=await api<{id:string}>(root('/drafts'),json({title:title.trim(),channel,content}));
  setTitle('');setContent('');await refreshWorkspace(active);await openDraft(d.id);setSuccess('Draft created in this workspace.');
 });}
 async function saveRevision(){if(!detail)return;await execute(async()=>{
  const result=await api<{number:number}>(root(`/drafts/${encodeURIComponent(detail.id)}/revisions`),json({content:editContent,expected_version:detail.current.number}));
  await openDraft(detail.id);setActivityTick(x=>x+1);setSuccess(`Saved version ${result.number}. Run checks again before approval.`);
 });}
 async function testDraft(){if(!detail)return;await execute(async()=>{
  const result=await api<Run>(root(`/drafts/${encodeURIComponent(detail.id)}/run`),{method:'POST'});
  setRun(result);setActivityTick(x=>x+1);setSuccess(`${result.findings.length} findings across ${result.checked_rules} configured rules.`);
 });}
 async function decide(decision:'approved'|'changes_requested'){if(!detail)return;await execute(async()=>{
  await api(root(`/drafts/${encodeURIComponent(detail.id)}/reviews`),json({decision,comment}));
  setReviews(await api<Review[]>(root(`/drafts/${encodeURIComponent(detail.id)}/reviews`)));
  setComment('');setActivityTick(x=>x+1);setSuccess(decision==='approved'?'Version approved by your authenticated identity.':'Change request recorded.');
 });}
 async function addMember(){await execute(async()=>{
  const res=await authFetch(`${API_BASE}${root('/members')}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:memberId.trim(),role:memberRole})});
  if(!res.ok){const e=await res.json().catch(()=>({detail:`Request failed (${res.status})`}));throw new Error(e.detail||'Membership update failed')}
  setMemberId('');await refreshWorkspace(active);setSuccess('Workspace membership updated.');
 });}
 return <section className="wc-root" aria-label="Workspace Control">
  <div className="wc-banner"><ShieldCheck size={20}/><div><strong>PUBLIC JUDGE SANDBOX · READ-ONLY</strong><p>Explore authenticated workspace information, member permissions, and policy-governance records. This public demonstration uses synthetic data and prevents changes to the workspace.</p></div></div>
  {error&&<div className="wc-message wc-error" role="alert"><AlertTriangle size={16}/>{error}<button onClick={()=>setError('')} aria-label="Dismiss error">×</button></div>}
  {success&&<div className="wc-message wc-success" role="status"><CheckCircle2 size={16}/>{success}<button onClick={()=>setSuccess('')} aria-label="Dismiss notice">×</button></div>}
  <div className="wc-toolbar"><div><span className="kicker">AUTHORIZED ORGANIZATIONS</span><h2>Workspace Control</h2><p>Switch only between organizations your signed-in account belongs to.</p></div><button type="button" className="ghost" disabled={busy} onClick={()=>void execute(async()=>{await refreshWorkspaces();if(active)await refreshWorkspace(active)})}><RefreshCw size={15}/> Refresh</button></div>
  <div className="wc-columns"><section className="wc-card"><h3><Building2 size={17}/> Your workspaces</h3>
   {loading?<p>Loading authorized workspaces…</p>:workspaces.length===0?<p className="wc-muted">No workspaces yet. Create one to become its administrator.</p>:<div className="wc-workspaces">{workspaces.map(w=><button type="button" key={w.id} className={w.id===active?'wc-selected':''} onClick={()=>setActive(w.id)}><strong>{w.name}</strong><span>{w.role.toUpperCase()}</span></button>)}</div>}
   <label htmlFor="wc-name">Create workspace</label><div className="wc-inline"><input id="wc-name" value={workspaceName} maxLength={100} placeholder="e.g. Nivara Studio" onChange={e=>setWorkspaceName(e.target.value)}/><button className="primary" disabled={busy||workspaceName.trim().length<2} onClick={()=>void makeWorkspace()}>Create</button></div>
  </section><section className="wc-card"><h3><Users size={17}/> Members & permissions</h3>
   {!current?<p className="wc-muted">Select a workspace to view its authorized members.</p>:<><p className="wc-muted">Your authenticated role: <b>{current.role}</b>. Role labels cannot be changed through the browser alone.</p><div className="wc-member-list">{members.map(m=><div key={m.user_id}><div><strong>{m.display_name}</strong><small>{m.email}</small></div><span>{m.role}</span></div>)}</div>
    {current.role==='admin'&&<><label htmlFor="wc-member-id">Add or update an existing account</label><p className="wc-muted">Enter an existing account's user ID (available from its /auth/me response). Membership changes are checked by the backend.</p><input id="wc-member-id" value={memberId} onChange={e=>setMemberId(e.target.value)} placeholder="Account user ID"/><div className="wc-inline"><select aria-label="Member role" value={memberRole} onChange={e=>setMemberRole(e.target.value as Role)}><option value="creator">Creator</option><option value="editor">Editor</option><option value="reviewer">Reviewer</option><option value="admin">Administrator</option></select><button className="primary" disabled={busy||!memberId.trim()} onClick={()=>void addMember()}>Assign role</button></div></>}
   </>}
  </section></div>
  {current&&<><div className="wc-toolbar wc-section-header"><div><span className="kicker">REAL WORKSPACE RECORDS</span><h2>Draft workbench</h2><p>Drafts and reviews below are scoped to <b>{current.name}</b>, not the legacy shared database.</p></div></div>
   <div className="wc-columns"><section className="wc-card"><h3><FilePlus2 size={17}/> Workspace drafts</h3>
    {drafts.length?<div className="wc-draft-list">{drafts.map(d=><button key={d.id} type="button" className={selected===d.id?'wc-selected':''} onClick={()=>void execute(()=>openDraft(d.id))}><strong>{d.title}</strong><span>{d.channel} · v{d.version}</span></button>)}</div>:<p className="wc-muted">No drafts in this workspace yet.</p>}
    {writable(current.role)&&<div className="wc-create"><h4>New workspace draft</h4><label htmlFor="wc-draft-title">Title</label><input id="wc-draft-title" value={title} maxLength={120} onChange={e=>setTitle(e.target.value)} placeholder="Campaign launch"/><label htmlFor="wc-channel">Channel</label><select id="wc-channel" value={channel} onChange={e=>setChannel(e.target.value)}><option value="social">Social</option><option value="email">Email</option><option value="website">Website</option><option value="general">General</option></select><label htmlFor="wc-content">Draft content</label><textarea id="wc-content" rows={5} value={content} maxLength={12000} onChange={e=>setContent(e.target.value)} placeholder="Write sample brand content…"/><button className="primary" disabled={busy||!title.trim()||!content.trim()} onClick={()=>void makeDraft()}><FilePlus2 size={15}/> Save draft</button></div>}
   </section><section className="wc-card"><h3><ClipboardCheck size={17}/> Version & review</h3>
    {!detail?<p className="wc-muted">Choose a workspace draft to inspect and test it.</p>:<><h4>{detail.title} <span className="wc-tag">v{detail.current.number}</span></h4><p className="wc-muted">{detail.channel} · {detail.versions.length} saved versions</p><label htmlFor="wc-editor">Content</label><textarea id="wc-editor" rows={7} value={editContent} readOnly={!writable(current.role)} onChange={e=>{setEditContent(e.target.value);setRun(null)}}/>
     <div className="wc-actions">{writable(current.role)&&<><button className="ghost" disabled={busy||!editContent.trim()||editContent===detail.current.content} onClick={()=>void saveRevision()}>Save new version</button><button className="primary" disabled={busy||editContent!==detail.current.content} onClick={()=>void testDraft()}><Play size={15}/> Run policy checks</button></>}</div>
     {run&&<div className="wc-test-result"><strong>{run.findings.length} finding(s) · {run.checked_rules} rules evaluated</strong>{run.findings.length===0?<p>No configured-rule findings. This does not certify factual correctness.</p>:run.findings.map(f=><p key={f.id}><b>{f.rule_code}</b> · {f.title}: “{f.matched_text}”</p>)}</div>}
     <h4>Review decisions</h4>{reviews.length?reviews.map(r=><div className="wc-review" key={r.id}><b>{r.decision.replace('_',' ')}</b><span>{r.created_at} · Actor ID: {r.actor_id}</span><p>{r.comment||'No comment'}</p></div>):<p className="wc-muted">No decisions recorded.</p>}
     {reviewer(current.role)&&<><label htmlFor="wc-comment">Review note</label><textarea id="wc-comment" rows={3} value={comment} maxLength={1000} onChange={e=>setComment(e.target.value)} placeholder="Explain your decision…"/><div className="wc-actions"><button className="ghost" disabled={busy} onClick={()=>void decide('changes_requested')}>Request changes</button><button className="primary" disabled={busy} onClick={()=>void decide('approved')}>Approve tested version</button></div><p className="wc-muted">The server refuses approval when the latest version has no passing test run or has findings.</p></>}
     </>}
   </section></div>
   {detail&&<Tracebook workspaceId={active} draftId={detail.id} versions={detail.versions} activityTick={activityTick}/>}
  </>}
 </section>;
}
