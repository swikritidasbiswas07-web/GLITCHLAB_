import {useCallback,useEffect,useState} from 'react';
import {authFetch} from './authClient';
import './workspace-regression-workbench.css';

const API=import.meta.env.VITE_API_BASE_URL||'http://127.0.0.1:8001';
export type RegressionRule={id:string;code:string;title:string};
export type RegressionCaseResult={id:string;rule_code:string;expected_match:boolean;actual_match:boolean|null;passed:boolean;error?:string|null};
type SavedCase={id:string;rule_id:string;rule_code:string;rule_title:string;sample:string;channel:string;expected_match:boolean|number;note:string;rule_active:boolean|number};
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await authFetch(`${API}${path}`,{...init,headers:{'Content-Type':'application/json',...init.headers}});
  if(!response.ok){const body=await response.json().catch(()=>({detail:`HTTP ${response.status}`}));throw new Error(typeof body.detail==='string'?body.detail:`HTTP ${response.status}`)}
  return response.json();
}
export default function WorkspaceRegressionWorkbench({workspaceId,role,rules,results,onChanged}:{workspaceId:string;role:string;rules:RegressionRule[];results:RegressionCaseResult[];onChanged:()=>Promise<void>}){
  const [cases,setCases]=useState<SavedCase[]>([]);
  const [ruleId,setRuleId]=useState(''),[channel,setChannel]=useState('social'),[sample,setSample]=useState(''),[expected,setExpected]=useState('match'),[note,setNote]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const admin=role==='admin';
  const endpoint=`/workspaces/${encodeURIComponent(workspaceId)}/protocol/cases`;
  const load=useCallback(async()=>{if(!workspaceId)return;setCases(await api<SavedCase[]>(`/workspaces/${encodeURIComponent(workspaceId)}/protocol/cases`));},[workspaceId]);
  useEffect(()=>{setRuleId(rules[0]?.id||'');},[workspaceId,rules]);
  useEffect(()=>{setCases([]);setError('');load().catch(e=>setError(String(e)));},[load]);
  const resultsById=new Map(results.map(r=>[r.id,r]));
  async function create(){
    if(!admin||!ruleId||!sample.trim())return;
    setBusy(true);setError('');setNotice('');
    try{
      await api(endpoint,{method:'POST',body:JSON.stringify({rule_id:ruleId,channel,sample,expected_match:expected==='match',note})});
      setSample('');setNote('');setNotice('Regression example saved. Protocol Studio has re-run the active rules.');
      await Promise.all([load(),onChanged()]);
    }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}
  }
  async function remove(id:string){
    if(!admin||!window.confirm('Delete this saved regression example?'))return;
    setBusy(true);setError('');setNotice('');
    try{await api(`${endpoint}/${encodeURIComponent(id)}`,{method:'DELETE'});setNotice('Regression example removed.');await Promise.all([load(),onChanged()]);}
    catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}
  }
  return <section className="ps-card rw-root">
    <span className="ps-kicker">03 / REGRESSION WORKBENCH</span>
    <h3>Test the rules before they ship.</h3>
    <p className="ps-muted">Save real examples with an expected result. The backend runs each example against the active regex rule; a failure blocks the next policy publication.</p>
    {error&&<p className="ps-error" role="alert">{error}</p>}{notice&&<p className="ps-success" role="status">{notice}</p>}
    {admin&&<div className="rw-form">
      <label>Rule to test<select value={ruleId} onChange={e=>setRuleId(e.target.value)}>{rules.map(r=><option key={r.id} value={r.id}>{r.code} — {r.title}</option>)}</select></label>
      <label>Channel<select value={channel} onChange={e=>setChannel(e.target.value)}><option value="social">Social</option><option value="web">Website</option><option value="email">Email</option><option value="advertising">Advertising</option><option value="other">Other</option></select></label>
      <label className="rw-wide">Example content<textarea rows={3} maxLength={4000} value={sample} onChange={e=>setSample(e.target.value)} placeholder="Example: Guaranteed performance."/></label>
      <label>Expected rule behavior<select value={expected} onChange={e=>setExpected(e.target.value)}><option value="match">Should flag this text</option><option value="no-match">Should NOT flag this text</option></select></label>
      <label>Why this case matters (optional)<textarea rows={2} maxLength={500} value={note} onChange={e=>setNote(e.target.value)} placeholder="Prevent a false positive / false negative"/></label>
      <button className="ps-primary rw-wide" onClick={create} disabled={busy||!ruleId||!sample.trim()}>Save and run example</button>
    </div>}
    {!admin&&<p className="ps-muted">Only workspace admins can add or delete regression examples. All members can view the results.</p>}
    <div className="rw-count"><b>{results.filter(r=>r.passed).length}/{results.length}</b> passing · <b>{results.filter(r=>!r.passed).length}</b> failing</div>
    {cases.length===0?<p className="ps-warn">No cases saved yet. Add a matching and a non-matching example for each active rule to establish basic regression coverage.</p>:<div className="rw-list">{cases.map(c=>{
      const result=resultsById.get(c.id);return <article key={c.id} className="rw-case">
        <div className="rw-head"><b>{c.rule_code}</b><span className={'rw-status '+(result?(result.passed?'rw-pass':'rw-fail'):'rw-inactive')}>{result?(result.passed?'PASS':'FAIL'):'INACTIVE'}</span></div>
        <p className="rw-sample">“{c.sample}”</p>
        <p>Expected: <b>{Boolean(c.expected_match)?'Flag':'Do not flag'}</b> · Observed: <b>{result?.actual_match===null||!result?'Not evaluated':result.actual_match?'Flagged':'Not flagged'}</b> · {c.channel}</p>
        {c.note&&<p className="ps-muted">{c.note}</p>}{result?.error&&<p className="ps-error">Invalid regex: {result.error}</p>}
        {admin&&<button className="ps-quiet" disabled={busy} onClick={()=>remove(c.id)}>Delete example</button>}
      </article>})}</div>}
    <p className="ps-muted ps-fine">These tests verify deterministic pattern behavior—not scientific evidence, semantic interpretation, or production fitness. An inactive rule's cases are excluded from release checks.</p>
  </section>;
}
