import {useCallback, useEffect, useMemo, useState} from 'react';
import {BookOpen, Plus, RefreshCw, ShieldCheck, Code2, FlaskConical} from 'lucide-react';
import {API_BASE, authFetch} from './authClient';
import './workspace-policy-vault.css';

type Role='admin'|'editor'|'creator'|'reviewer';
type Workspace={id:string;name:string;role:Role};
type PolicyRule={id:string;code:string;category:string;title:string;pattern:string;replacement:string;active:number;version:number};
type BuilderMode='phrase'|'regex';
const categories=['fact','claim','tone','terminology'] as const;
const initial={code:'',category:'claim',title:'',phrase:'',pattern:'',replacement:''};
const escapeRegex=(value:string)=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
function describe(rule:PolicyRule):string{
  if(rule.pattern===String.raw`72\s*[- ]?hours?`){
    return 'Flags 72-hour battery-duration wording. A replacement is configured, but the claim still needs evidence review.';
  }
  const simple=rule.pattern.match(/^\\b(.+)\\b$/);
  if(simple && !/[\\()[\]{}*+?|^$]/.test(simple[1]))return `Flags the expression “${simple[1]}” (case-insensitive).`;
  if(!/[\\()[\]{}*+?|^$]/.test(rule.pattern))return `Flags wording containing “${rule.pattern}” (case-insensitive).`;
  return 'Checks content against a configured detection expression. See advanced details for the exact matching logic.';
}
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await authFetch(`${API_BASE}${path}`,{...init,headers:{'Content-Type':'application/json',...init.headers}});
  if(!response.ok){const detail=await response.json().catch(()=>null);throw new Error(typeof detail?.detail==='string'?detail.detail:`Request failed (${response.status})`);}
  return response.json() as Promise<T>;
}
export default function WorkspacePolicyVault(){
  const [workspaces,setWorkspaces]=useState<Workspace[]>([]);
  const [active,setActive]=useState('');
  const [rules,setRules]=useState<PolicyRule[]>([]);
  const [search,setSearch]=useState('');
  const [category,setCategory]=useState('all');
  const [form,setForm]=useState({...initial});
  const [mode,setMode]=useState<BuilderMode>('phrase');
  const [sample,setSample]=useState('');
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const current=workspaces.find(w=>w.id===active);
  const loadWorkspaces=useCallback(async()=>{
    try{const list=await api<Workspace[]>('/workspaces');setWorkspaces(list);setActive(old=>list.some(w=>w.id===old)?old:(list[0]?.id||''));}
    catch(e){setError(e instanceof Error?e.message:String(e));setLoading(false);}
  },[]);
  useEffect(()=>{void loadWorkspaces();},[loadWorkspaces]);
  const loadRules=useCallback(async()=>{
    if(!active){setRules([]);setLoading(false);return;}
    setLoading(true);setError('');
    try{setRules(await api<PolicyRule[]>(`/workspaces/${encodeURIComponent(active)}/rules`));}
    catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setLoading(false);}
  },[active]);
  useEffect(()=>{void loadRules();},[loadRules]);
  const visible=useMemo(()=>rules.filter(r=>(category==='all'||r.category===category)&&(!search.trim()||`${r.code} ${r.title} ${r.pattern}`.toLowerCase().includes(search.toLowerCase().trim()))),[rules,search,category]);
  const generatedPattern=mode==='phrase'?escapeRegex(form.phrase.trim()):form.pattern;
  const valid=/^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$/.test(form.code.trim())&&form.title.trim().length>=2&&generatedPattern.length>0&&generatedPattern.length<=160;
  const matchPreview=useMemo(()=>{
    if(mode!=='phrase'||!form.phrase.trim()||!sample.trim())return null;
    // Literal substring preview: the escaped regex submitted to Python has
    // equivalent case-insensitive matching semantics for ordinary text.
    return sample.toLowerCase().includes(form.phrase.trim().toLowerCase());
  },[mode,form.phrase,sample]);
  async function createRule(){
    if(!current||current.role!=='admin'||!valid||busy)return;
    setBusy(true);setError('');setMessage('');
    try{
      await api(`/workspaces/${encodeURIComponent(active)}/rules`,{method:'POST',body:JSON.stringify({code:form.code.trim(),category:form.category,title:form.title.trim(),pattern:generatedPattern,replacement:form.replacement})});
      setForm({...initial});setSample('');setMode('phrase');await loadRules();
      setMessage('Rule created in this workspace. Retest drafts to apply the new rule.');
    }catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  }
  return <section className="wpv-root" aria-label="Workspace Policy Vault">
    <div className="wpv-heading"><div><span className="kicker">AUTHORIZED POLICY LIBRARY</span><h2>Policy Vault</h2><p>Readable rules, clear suggestions and workspace-specific governance.</p></div><button className="ghost" onClick={()=>void loadRules()} disabled={busy||loading||!active}><RefreshCw size={16}/> Refresh</button></div>
    <div className="wpv-banner"><ShieldCheck size={19}/><span>Only workspace administrators can create rules. A matching rule does not establish factual correctness or an approved policy release.</span></div>
    <div className="wpv-controls"><label>Workspace<select value={active} onChange={e=>setActive(e.target.value)}>{workspaces.map(w=><option key={w.id} value={w.id}>{w.name} · {w.role}</option>)}</select></label><label>Search<input value={search} placeholder="Search rule code or title" onChange={e=>setSearch(e.target.value)}/></label><label>Category<select value={category} onChange={e=>setCategory(e.target.value)}><option value="all">All categories</option>{categories.map(c=><option key={c} value={c}>{c}</option>)}</select></label></div>
    {error&&<p role="alert" className="wpv-error">{error}</p>}{message&&<p role="status" className="wpv-success">{message}</p>}
    <div className="wpv-summary"><BookOpen size={18}/><b>{rules.length}</b> workspace rule(s) · <b>{rules.filter(r=>r.active).length}</b> active</div>
    {loading?<p className="wpv-empty">Loading authorized rules…</p>:visible.length?<div className="wpv-list">{visible.map(r=><article key={r.id} className="wpv-rule"><div className="wpv-rule-top"><b>{r.code}</b><span>{r.category} · v{r.version} · {r.active?'Active':'Inactive'}</span></div><h3>{r.title}</h3><p className="wpv-readable">{describe(r)}</p><div className="wpv-detail"><small>SUGGESTED CORRECTION</small><span>{r.replacement||'Human correction required'}</span></div><details className="wpv-advanced"><summary><Code2 size={15}/> Advanced detection details</summary><p>Technical matching expression (Python regex):</p><code>{r.pattern}</code></details></article>)}</div>:<p className="wpv-empty">No matching rules in this workspace.</p>}
    {current?.role==='admin'&&<section className="wpv-create"><span className="kicker">ADMINISTRATOR ACTION</span><h3>Build a rule</h3><p>Create a straightforward wording check without writing code. New rules become active immediately; Protocol Studio will later introduce reviewed releases.</p>
      <div className="wpv-form"><label>Rule code<input maxLength={32} value={form.code} placeholder="NV-102" onChange={e=>setForm({...form,code:e.target.value})}/></label><label>Category<select value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>{categories.map(c=><option key={c} value={c}>{c}</option>)}</select></label><label className="wpv-wide">Rule title<input maxLength={120} value={form.title} placeholder="Unqualified guarantee" onChange={e=>setForm({...form,title:e.target.value})}/></label></div>
      <div className="wpv-mode"><button type="button" className={mode==='phrase'?'wpv-mode-selected':''} onClick={()=>setMode('phrase')}>Simple wording</button><button type="button" className={mode==='regex'?'wpv-mode-selected':''} onClick={()=>setMode('regex')}>Advanced regex</button></div>
      {mode==='phrase'?<div className="wpv-form"><label className="wpv-wide">Flag this exact wording (case-insensitive)<input maxLength={100} placeholder="guaranteed" value={form.phrase} onChange={e=>setForm({...form,phrase:e.target.value})}/></label><p className="wpv-wide wpv-help">This detects the phrase anywhere in the draft. For example, “guaranteed” will also match inside longer words. Use advanced mode for word boundaries.</p></div>:<div className="wpv-form"><label className="wpv-wide">Technical Python regex<input maxLength={160} value={form.pattern} placeholder={String.raw`\bguaranteed\b`} onChange={e=>setForm({...form,pattern:e.target.value})}/></label><p className="wpv-wide wpv-help">Advanced regex is validated by the backend when saved. Live preview is disabled in this mode because browser regex can differ from Python matching.</p></div>}
      <div className="wpv-form"><label className="wpv-wide">Suggested correction<input maxLength={250} placeholder="designed to" value={form.replacement} onChange={e=>setForm({...form,replacement:e.target.value})}/></label></div>
      {mode==='phrase'&&<div className="wpv-test"><h4><FlaskConical size={18}/> Test wording before saving</h4><label>Sample sentence<textarea rows={3} value={sample} onChange={e=>setSample(e.target.value)} placeholder="Try a sentence containing the phrase…"/></label><p aria-live="polite" className={matchPreview===true?'wpv-test-hit':matchPreview===false?'wpv-test-clear':''}>{matchPreview===null?'Enter wording and a sample sentence to preview the match.':matchPreview?'MATCH: This wording would be flagged.':'NO MATCH: The sample does not contain the wording.'}</p><small>This is a local literal-phrase preview, not a saved evaluation. The backend remains authoritative.</small></div>}
      <button type="button" className="primary" disabled={!valid||busy} onClick={()=>void createRule()}><Plus size={16}/>{busy?'Saving…':'Create workspace rule'}</button><p className="wpv-footnote">Rules require human review. Newly created rules affect subsequent evaluations; historical results are not rewritten.</p>
    </section>}
    {current&&current.role!=='admin'&&<p className="wpv-footnote">Your role is {current.role}. Only administrators can create rules; this restriction is enforced by FastAPI.</p>}
  </section>;
}
