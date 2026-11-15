import {useCallback, useEffect, useMemo, useState} from 'react';
import {CheckCircle2, ClipboardCheck, RefreshCw, ShieldCheck, AlertTriangle, ArrowRight} from 'lucide-react';
import {API_BASE, authFetch} from './authClient';
import './workspace-review-station.css';

type Role = 'admin' | 'editor' | 'creator' | 'reviewer';
type Workspace = {id:string; name:string; role:Role};
type Draft = {id:string; title:string; channel:string; author_id:string; version:number};
type Version = {id:string; number:number; content:string; created_at:string};
type Detail = Draft & {current:Version; versions:Version[]};
type Review = {id:string;version_id:string;actor_id:string;decision:'approved'|'changes_requested';comment:string;created_at:string};
type Activity = {id:string;type:string;version_id?:string;created_at:string};
type Finding = {id:string;rule_code:string;title:string;matched_text:string};
type Run = {id:string;version_id:string;checked_rules:number;rule_snapshot:string;findings:Finding[];created_at:string};
type Rule = {id:string;code:string;version:number;pattern:string;active:number};
type Member = {user_id:string;display_name:string;role:Role};
type User = {id:string;display_name:string};
const esc = encodeURIComponent;

async function api<T>(path:string, init:RequestInit={}):Promise<T> {
  const response = await authFetch(`${API_BASE}${path}`,{
    ...init,
    headers:{'Content-Type':'application/json',...init.headers},
  });
  if (!response.ok) {
    const body = await response.json().catch(()=>null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
function date(value:string) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}
function policyMatches(run:Run|null, rules:Rule[]):boolean {
  if (!run || run.checked_rules < 1) return false;
  try {
    const snapshot:unknown = JSON.parse(run.rule_snapshot);
    if (!Array.isArray(snapshot)) return false;
    const current = rules.filter(r=>Boolean(r.active));
    if (current.length === 0 || snapshot.length !== current.length || run.checked_rules !== current.length) return false;
    return current.every(rule=>snapshot.some((item:unknown)=>{
      if (!item || typeof item !== 'object') return false;
      const record = item as Record<string,unknown>;
      return record.id===rule.id && record.code===rule.code &&
        record.version===rule.version && record.pattern===rule.pattern;
    }));
  } catch {return false;}
}

export default function WorkspaceReviewStation({onOpenDraft}:{onOpenDraft?:(workspaceId:string,draftId:string)=>void}) {
  const [workspaces,setWorkspaces] = useState<Workspace[]>([]);
  const [active,setActive] = useState('');
  const [drafts,setDrafts] = useState<Draft[]>([]);
  const [selected,setSelected] = useState('');
  const [detail,setDetail] = useState<Detail|null>(null);
  const [reviews,setReviews] = useState<Review[]>([]);
  const [members,setMembers] = useState<Member[]>([]);
  const [rules,setRules] = useState<Rule[]>([]);
  const [lastRun,setLastRun] = useState<Run|null>(null);
  const [currentUser,setCurrentUser] = useState<User|null>(null);
  const [comment,setComment] = useState('');
  const [busy,setBusy] = useState(false);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [refresh,setRefresh] = useState(0);
  const workspace=workspaces.find(w=>w.id===active);
  const base=`/workspaces/${esc(active)}`;

  const reload = useCallback(()=>setRefresh(n=>n+1),[]);
  useEffect(()=>{
    let cancelled=false;
    Promise.all([api<Workspace[]>('/workspaces'),api<User>('/auth/me')])
      .then(([all,user])=>{if(cancelled)return;setWorkspaces(all);setCurrentUser(user);setActive(previous=>all.some(w=>w.id===previous)?previous:(all[0]?.id||''));})
      .catch(e=>{if(!cancelled)setError(String(e));})
      .finally(()=>{if(!cancelled)setLoading(false);});
    return ()=>{cancelled=true;};
  },[]);
  useEffect(()=>{
    if(!active) return;
    let cancelled=false;
    setError('');setDetail(null);setLastRun(null);setReviews([]);
    Promise.all([api<Draft[]>(`${base}/drafts`),api<Member[]>(`${base}/members`),api<Rule[]>(`${base}/rules`)])
      .then(([draftList,memberList,ruleList])=>{if(cancelled)return;setDrafts(draftList);setMembers(memberList);setRules(ruleList);setSelected(old=>old && draftList.some(d=>d.id===old)?old:(draftList[0]?.id||''));})
      .catch(e=>{if(!cancelled)setError(String(e));});
    return ()=>{cancelled=true;};
  },[active,refresh]);
  useEffect(()=>{
    if(!active||!selected)return;
    let cancelled=false;
    setError('');setLastRun(null);
    const draftBase=`${base}/drafts/${esc(selected)}`;
    Promise.all([api<Detail>(draftBase),api<Review[]>(`${draftBase}/reviews`),api<Activity[]>(`${draftBase}/activity`)])
      .then(async([draft,history,activity])=>{
        const latest = activity.filter(a=>a.type==='policy_test' && a.version_id===draft.current.id)
          .sort((a,b)=>b.created_at.localeCompare(a.created_at)||b.id.localeCompare(a.id))[0];
        const run=latest ? await api<Run>(`${base}/runs/${esc(latest.id.replace(/^test:/,''))}`) : null;
        if(cancelled)return;
        setDetail(draft);setReviews(history);setLastRun(run);
      })
      .catch(e=>{if(!cancelled)setError(String(e));});
    return ()=>{cancelled=true;};
  },[active,selected,refresh]);

  const checked = lastRun !== null && lastRun.version_id===detail?.current.id;
  const matchesPolicy = policyMatches(lastRun,rules);
  const clean = checked && lastRun!.findings.length===0;
  const hasApproval=Boolean(detail && reviews.some(r=>r.version_id===detail.current.id&&r.decision==='approved'));
  const independent=Boolean(currentUser && detail && currentUser.id!==detail.author_id);
  const canReview=workspace?.role==='reviewer'||workspace?.role==='admin';
  const canApprove=Boolean(canReview && independent && checked && clean && matchesPolicy && !hasApproval && !busy);
  const maker=useMemo(()=>members.find(m=>m.user_id===detail?.author_id)?.display_name||'Former or unknown member',[members,detail]);
  async function decide(decision:'approved'|'changes_requested') {
    if(!detail || busy || !canReview) return;
    if(decision==='approved' && !canApprove)return;
    setBusy(true);setError('');setNotice('');
    try {
      // Re-read latest records immediately before submitting. The server remains authoritative.
      const [fresh,history,activity,policies] = await Promise.all([
        api<Detail>(`${base}/drafts/${esc(selected)}`),
        api<Review[]>(`${base}/drafts/${esc(selected)}/reviews`),
        api<Activity[]>(`${base}/drafts/${esc(selected)}/activity`),
        api<Rule[]>(`${base}/rules`),
      ]);
      if(fresh.current.id!==detail.current.id)throw new Error('A newer version exists. Refresh before reviewing.');
      if(decision==='approved') {
        if(history.some(r=>r.version_id===fresh.current.id && r.decision==='approved'))throw new Error('This version already has an approval.');
        const latest=activity.filter(a=>a.type==='policy_test' && a.version_id===fresh.current.id)
          .sort((a,b)=>b.created_at.localeCompare(a.created_at)||b.id.localeCompare(a.id))[0];
        const run=latest ? await api<Run>(`${base}/runs/${esc(latest.id.replace(/^test:/,''))}`) : null;
        if(!run || run.findings.length>0 || !policyMatches(run,policies))throw new Error('Latest version needs a clean evaluation against the current policy before approval.');
      }
      await api(`${base}/drafts/${esc(selected)}/reviews`,{method:'POST',body:JSON.stringify({decision,comment})});
      setComment('');setNotice(decision==='approved'?'Approval recorded against the latest saved version.':'Changes requested and recorded.');
      reload();
    }catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  }
  return <section className="wrs-root" aria-label="Workspace Review Station">
    <header className="wrs-header"><div><span className="kicker">AUTHENTICATED DECISIONS / HUMAN GATE</span><h2>Review Station</h2><p>Review saved versions with real workspace permissions and traceable decisions.</p></div>
      <button className="ghost" type="button" onClick={reload} disabled={busy||!active}><RefreshCw size={16}/> Refresh</button></header>
    <div className="wrs-banner"><ShieldCheck size={18}/><span>Decisions are attached to saved draft versions. Reviewers cannot silently change draft content; the backend verifies each decision.</span></div>
    {error && <p className="wrs-error" role="alert"><AlertTriangle size={17}/>{error}</p>}
    {notice && <p className="wrs-success" role="status"><CheckCircle2 size={17}/>{notice}</p>}
    <div className="wrs-selectors"><label>Workspace<select value={active} onChange={e=>setActive(e.target.value)} aria-label="Review workspace">
      {workspaces.map(w=><option key={w.id} value={w.id}>{w.name} · {w.role}</option>)}</select></label>
      <label>Draft<select value={selected} onChange={e=>setSelected(e.target.value)} aria-label="Draft to review">
        {drafts.map(d=><option key={d.id} value={d.id}>{d.title} · v{d.version}</option>)}</select></label></div>
    {loading?<p className="wrs-empty">Loading authorized workspaces…</p>:!workspace?<p className="wrs-empty">No authorized workspace available.</p>:drafts.length===0?<p className="wrs-empty">No saved drafts in this workspace yet.</p>:!detail?<p className="wrs-empty">Loading the selected draft and its reviews…</p>:<div className="wrs-grid">
      <article className="wrs-card"><span className="kicker">01 / SAVED CONTENT</span><h3>{detail.title}</h3>
        <p className="wrs-muted">{detail.channel} · Version {detail.current.number} · Author: {maker}</p>
        <div className="wrs-copy">{detail.current.content}</div>
        <h4>Current-version policy check</h4>
        {!checked?<p className="wrs-state wrs-caution">Not tested — send this version to Content Lab.</p>
        :lastRun!.findings.length>0?<p className="wrs-state wrs-fail">{lastRun!.findings.length} unresolved finding(s)</p>
        :!matchesPolicy?<p className="wrs-state wrs-caution">Policy changed or test evidence is incomplete. Retest against current rules.</p>
        :<p className="wrs-state wrs-pass">No findings in {lastRun!.checked_rules} configured rule(s) · current rule snapshot matches</p>}
        {hasApproval && <p className="wrs-muted">A historical/current-version approval exists. Its policy validity is not established solely by the recorded decision.</p>}
        {onOpenDraft && <button type="button" className="wrs-link" onClick={()=>onOpenDraft(active,selected)}>Open in Workspace Control <ArrowRight size={15}/></button>}
      </article>
      <article className="wrs-card"><span className="kicker">02 / INDEPENDENT HUMAN REVIEW</span><h3>Decision desk</h3>
        <p className="wrs-muted">Signed-in role: <strong>{workspace.role}</strong>. Draft author: <strong>{maker}</strong>.</p>
        {!canReview?<div className="wrs-info">Only a workspace Reviewer or Admin can submit review decisions. You can inspect the current status.</div>
          :<><label htmlFor="wrs-comment">Review note</label><textarea id="wrs-comment" rows={4} maxLength={1000} placeholder="Describe the required changes or why this is ready…" value={comment} onChange={e=>setComment(e.target.value)}/>
            <div className="wrs-buttons"><button className="ghost" type="button" disabled={busy} onClick={()=>void decide('changes_requested')}>Request changes</button><button className="primary" type="button" disabled={!canApprove} onClick={()=>void decide('approved')}><ClipboardCheck size={16}/> Approve version</button></div>
            {!independent&&<p className="wrs-muted">Authors cannot approve their own draft.</p>}
            {!matchesPolicy&&<p className="wrs-muted">Approval requires a clean current-version run whose rule snapshot matches the active workspace policies.</p>}
            {hasApproval&&<p className="wrs-muted">An approval is already recorded for this version; repeated approval is disabled here.</p>}
          </>}
        <h4>Recorded review history</h4>
        {reviews.length===0?<p className="wrs-muted">No decisions recorded.</p>:<div className="wrs-history">{reviews.map(r=><div key={r.id}>
          <strong>{r.decision==='approved'?'Approved':'Changes requested'}</strong> · Version {detail.versions.find(v=>v.id===r.version_id)?.number??'?'}
          <small>{members.find(m=>m.user_id===r.actor_id)?.display_name||'Former or unknown member'} · {date(r.created_at)}</small>
          {r.comment && <p>{r.comment}</p>}
        </div>)}</div>}
        <p className="wrs-disclaimer">A passing deterministic policy check does not verify factual claims. Policy freshness and duplicate approval prevention must also be enforced server-side before public deployment.</p>
      </article>
    </div>}
  </section>;
}
