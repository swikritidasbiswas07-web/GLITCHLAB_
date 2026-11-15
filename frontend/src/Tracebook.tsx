import {useCallback,useEffect,useState} from 'react';
import {History,GitCompareArrows,RefreshCcw,Filter} from 'lucide-react';
import {API_BASE,authFetch} from './authClient';
import './tracebook.css';

type Entry={id:string;type:string;actor_id:string|null;actor_name:string;created_at:string;version_id:string;version_number:number|null;description:string};
type Part={kind:'unchanged'|'added'|'removed';text:string};
type Diff={before_version:number;after_version:number;before_parts:Part[];after_parts:Part[]};
export type TracebookVersion={id:string;number:number;content:string;created_at:string};
async function get<T>(path:string):Promise<T>{
 const r=await authFetch(`${API_BASE}${path}`);if(!r.ok){const data=await r.json().catch(()=>({}));throw new Error(data.detail||`Request failed (${r.status})`)}return r.json() as Promise<T>;
}
const fmt=(s:string)=>{const date=new Date(s);return Number.isNaN(date.getTime())?s:date.toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'});};
const labels:Record<string,string>={draft_created:'Created draft',revision_saved:'Saved revision',policy_test:'Ran policy checks',review_approved:'Approved version',review_changes_requested:'Requested changes'};
export default function Tracebook({workspaceId,draftId,versions,activityTick}:{workspaceId:string;draftId:string;versions:TracebookVersion[];activityTick:number}){
 const [entries,setEntries]=useState<Entry[]>([]);const [diff,setDiff]=useState<Diff|null>(null);
 const [before,setBefore]=useState('');const [after,setAfter]=useState('');
 const [filter,setFilter]=useState('all');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 const url=`/workspaces/${encodeURIComponent(workspaceId)}/drafts/${encodeURIComponent(draftId)}`;
 const load=useCallback(async()=>{setBusy(true);setError('');try{setEntries(await get<Entry[]>(url+'/activity'))}catch(e){setError(String(e))}finally{setBusy(false)}},[url]);
 useEffect(()=>{setEntries([]);setDiff(null);setFilter('all');void load()},[load]);
 useEffect(()=>{if(activityTick>0)void load()},[activityTick,load]);
 useEffect(()=>{setAfter(String(versions[0]?.number||''));setBefore(String(versions[1]?.number||''));setDiff(null)},[draftId,versions]);
 async function compare(a:string,b:string){if(!a||!b||a===b)return;setBusy(true);setError('');try{setDiff(await get<Diff>(url+`/compare?before=${encodeURIComponent(a)}&after=${encodeURIComponent(b)}`))}catch(e){setError(String(e))}finally{setBusy(false)}}
 const shown=entries.filter(e=>filter==='all'||e.type===filter);
 return <section className="tb-root" aria-label="Tracebook activity and version comparison">
  <div className="tb-header"><div><span className="kicker">GLITCHLAB_ / COLLABORATION RECORD</span><h3><History size={22}/> Tracebook</h3><p>Who did what, and when. Recorded by the authenticated backend.</p></div><button type="button" className="ghost" disabled={busy} onClick={()=>void load()}><RefreshCcw size={15}/> Refresh activity</button></div>
  {error&&<p className="tb-error" role="alert">{error}</p>}
  <div className="tb-grid"><div className="tb-panel"><div className="tb-panelhead"><h4>Activity timeline</h4><label><Filter size={14}/><select value={filter} onChange={e=>setFilter(e.target.value)} aria-label="Filter activity"><option value="all">All activity</option>{Object.entries(labels).map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label></div>
    {busy&&!entries.length?<p className="tb-muted">Loading activity…</p>:!shown.length?<p className="tb-muted">No matching records yet.</p>:<ol className="tb-timeline">{shown.map(e=><li key={e.id}><span className="tb-initials">{e.actor_name==='Unknown editor'?'?':e.actor_name.split(' ').map(s=>s.charAt(0)).slice(0,2).join('')}</span><div><strong>{e.actor_name}</strong><div className="tb-event">{labels[e.type]||e.type}{e.version_number?` · v${e.version_number}`:''}</div><small>{fmt(e.created_at)}</small><p>{e.description}</p></div></li>)}</ol>}
    <p className="tb-muted">Older revisions without stored editor IDs are explicitly marked Unknown editor. Dates come from saved records, not browser guesses.</p>
  </div><div className="tb-panel"><div className="tb-panelhead"><h4><GitCompareArrows size={17}/> DiffScope</h4></div><p className="tb-muted">Compare any two saved versions. Red shows removed text; green shows added text.</p>
   <div className="tb-compareselect"><label>From<select value={before} onChange={e=>setBefore(e.target.value)}>{versions.map(v=><option key={v.id} value={v.number}>Version {v.number}</option>)}</select></label><label>To<select value={after} onChange={e=>setAfter(e.target.value)}>{versions.map(v=><option key={v.id} value={v.number}>Version {v.number}</option>)}</select></label></div>
   <button type="button" className="primary" disabled={busy||!before||!after||before===after} onClick={()=>void compare(before,after)}>Compare versions</button>
   {diff&&<div className="tb-diffgrid"><article><h5>Version {diff.before_version} · Before</h5><div className="tb-difftext">{diff.before_parts.map((p,i)=><span key={i} className={p.kind==='removed'?'tb-removed':''}>{p.text}</span>)}</div></article><article><h5>Version {diff.after_version} · After</h5><div className="tb-difftext">{diff.after_parts.map((p,i)=><span key={i} className={p.kind==='added'?'tb-added':''}>{p.text}</span>)}</div></article></div>}
   {versions.length<2&&<p className="tb-muted">Save another version to enable comparison.</p>}
  </div></div>
 </section>;
}
