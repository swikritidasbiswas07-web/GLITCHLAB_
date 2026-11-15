import {useCallback, useEffect, useMemo, useState} from 'react';
import {ArrowDownUp, ArrowRight, CircleAlert, FilePlus2, Filter, LoaderCircle, RefreshCw, Search, ShieldCheck, X} from 'lucide-react';
import {API_BASE, authFetch} from './authClient';

type DraftListItem = {id:string;title:string;version:number};
type Review = {id:string;decision:string;reviewer:string;created_at:string;version_id?:string};
type Detail = {id:string;title:string;channel:string;current:{id:string;number:number;content:string};reviews:Review[];runs:{id:string;version_id:string;created_at:string}[]};
type Run = {id:string;findings:{id:string}[]};
type RecordRow = {item:DraftListItem; detail?:Detail; issues?:number; status:'untested'|'checking'|'issues'|'clear'|'reviewed'|'unknown'; latestRunAt?:string; error?:string};

async function readJSON<T>(path:string):Promise<T>{
  const res=await authFetch(`${API_BASE}${path}`);
  if(!res.ok){const body=await res.json().catch(()=>null); throw new Error(typeof body?.detail==='string'?body.detail:`Request failed (${res.status})`)}
  return res.json() as Promise<T>;
}
function statusFor(d:Detail,issues:number|undefined):RecordRow['status']{
  if(issues===undefined)return 'untested';
  if(issues>0)return 'issues';
  // A review record alone is not proof of approval for the current version unless linked.
  if(d.reviews.some(r=>r.decision==='approved'&&r.version_id===d.current.id))return 'reviewed';
  return 'clear';
}
function displayChannel(channel?:string){return ({social:'Social media',email:'Email',website:'Website',general:'General'} as Record<string,string>)[channel||''] || channel || '—';}
function dateLabel(raw?:string){if(!raw)return '—';const n=Date.parse(raw);return Number.isNaN(n)?raw:new Date(n).toLocaleString();}

export default function DraftRadar({onOpen,onNew}:{onOpen:(id:string)=>void;onNew:()=>void}){
  const [rows,setRows]=useState<RecordRow[]>([]);
  const [loading,setLoading]=useState(true);
  const [refreshing,setRefreshing]=useState(false);
  const [message,setMessage]=useState('');
  const [search,setSearch]=useState('');
  const [channel,setChannel]=useState('all');
  const [status,setStatus]=useState('all');
  const [sort,setSort]=useState('recent');
  const [page,setPage]=useState(1);
  const pageSize=10;
  const refresh=useCallback(async(initial=false)=>{
    if(initial)setLoading(true);else setRefreshing(true);
    setMessage('');
    try{
      const items=await readJSON<DraftListItem[]>('/drafts');
      // Concurrency is bounded to avoid opening one request per draft at once.
      const next:RecordRow[]=[];
      for(let i=0;i<items.length;i+=5){
        const chunk=await Promise.all(items.slice(i,i+5).map(async(item):Promise<RecordRow>=>{
          try{
            const detail=await readJSON<Detail>(`/drafts/${encodeURIComponent(item.id)}`);
            const latest=detail.runs.find(r=>r.version_id===detail.current.id);
            if(!latest)return {item,detail,status:'untested'};
            const run=await readJSON<Run>(`/runs/${encodeURIComponent(latest.id)}`);
            const issues=run.findings.length;
            return {item,detail,issues,latestRunAt:latest.created_at,status:statusFor(detail,issues)};
          }catch(e){return {item,status:'unknown',error:e instanceof Error?e.message:String(e)};}
        }));
        next.push(...chunk);
      }
      setRows(next);
      if(next.some(x=>x.error))setMessage('Some draft details could not be loaded. Try refreshing.');
    }catch(e){setMessage(e instanceof Error?e.message:String(e));}
    finally{setLoading(false);setRefreshing(false);}
  },[]);
  useEffect(()=>{void refresh(true)},[refresh]);
  const filtered=useMemo(()=>{
    const q=search.trim().toLocaleLowerCase();
    return rows.filter(r=>{
      if(q && !`${r.item.title} ${r.detail?.channel||''}`.toLocaleLowerCase().includes(q))return false;
      if(channel!=='all' && r.detail?.channel!==channel)return false;
      if(status!=='all' && r.status!==status)return false;
      return true;
    }).sort((a,b)=>{
      if(sort==='title')return a.item.title.localeCompare(b.item.title);
      if(sort==='issues')return (b.issues??-1)-(a.issues??-1);
      if(sort==='version')return b.item.version-a.item.version;
      return (b.latestRunAt||'').localeCompare(a.latestRunAt||'');
    });
  },[rows,search,channel,status,sort]);
  const pageCount=Math.max(1,Math.ceil(filtered.length/pageSize));
  const shown=filtered.slice((Math.min(page,pageCount)-1)*pageSize,Math.min(page,pageCount)*pageSize);
  const changeFilter=(update:()=>void)=>{update();setPage(1)};
  const counts={total:rows.length,issues:rows.filter(r=>r.status==='issues').length,clear:rows.filter(r=>r.status==='clear'||r.status==='reviewed').length,untested:rows.filter(r=>r.status==='untested').length};
  return <div className="dr-root">
    <div className="dr-heading"><div><div className="dr-eyebrow">CONTENT REGISTRY / LIVE WORKSPACE</div><h2>Draft Radar</h2><p>Find saved content, inspect the latest checks, and open a draft for editing or human review.</p></div><div className="dr-heading-actions"><button type="button" className="dr-secondary" onClick={()=>void refresh()} disabled={refreshing||loading}><RefreshCw size={16} className={refreshing?'dr-spin':''}/> Refresh</button><button type="button" className="dr-primary" onClick={onNew}><FilePlus2 size={17}/> New draft</button></div></div>
    <div className="dr-metrics"><div><span>Saved drafts</span><strong>{loading?'—':counts.total}</strong></div><div><span>With open findings</span><strong>{loading?'—':counts.issues}</strong></div><div><span>Zero findings on latest run</span><strong>{loading?'—':counts.clear}</strong></div><div><span>Current version not tested</span><strong>{loading?'—':counts.untested}</strong></div></div>
    <section className="dr-card" aria-label="Saved draft registry"><div className="dr-toolbar"><label className="dr-search"><Search size={17}/><input aria-label="Search drafts" value={search} placeholder="Search title or channel" onChange={e=>changeFilter(()=>setSearch(e.target.value))}/>{search&&<button aria-label="Clear search" type="button" onClick={()=>changeFilter(()=>setSearch(''))}><X size={15}/></button>}</label><div className="dr-filter"><Filter size={16}/><select aria-label="Filter by channel" value={channel} onChange={e=>changeFilter(()=>setChannel(e.target.value))}><option value="all">All channels</option><option value="social">Social media</option><option value="email">Email</option><option value="website">Website</option><option value="general">General</option></select></div><select aria-label="Filter by result" value={status} onChange={e=>changeFilter(()=>setStatus(e.target.value))}><option value="all">All results</option><option value="issues">Has findings</option><option value="clear">No findings</option><option value="reviewed">Verified current approval</option><option value="untested">Not tested</option><option value="unknown">Unavailable</option></select><div className="dr-filter"><ArrowDownUp size={15}/><select aria-label="Sort drafts" value={sort} onChange={e=>setSort(e.target.value)}><option value="recent">Latest test activity</option><option value="title">Title A–Z</option><option value="issues">Most findings</option><option value="version">Highest version</option></select></div></div>
    {message&&<div role="alert" className="dr-message"><CircleAlert size={17}/>{message}</div>}
    {loading?<div className="dr-empty"><LoaderCircle className="dr-spin" size={30}/><h3>Loading saved drafts…</h3></div>:shown.length===0?<div className="dr-empty"><Search size={32}/><h3>{rows.length?'No matching drafts':'Your draft registry is empty'}</h3><p>{rows.length?'Adjust your search and filters.':'Create your first draft to start a real content review.'}</p><button type="button" className="dr-primary" onClick={rows.length?()=>{setSearch('');setChannel('all');setStatus('all');setPage(1)}:onNew}>{rows.length?'Clear filters':'Create draft'}</button></div>:<><div className="dr-table-wrap"><table className="dr-table"><thead><tr><th>DRAFT</th><th>CHANNEL</th><th>VERSION</th><th>FINDINGS</th><th>REVIEW STATE</th><th>LAST TEST</th><th><span className="dr-sr-only">ACTION</span></th></tr></thead><tbody>{shown.map(r=><tr key={r.item.id}><td><button type="button" className="dr-draft-link" onClick={()=>onOpen(r.item.id)}>{r.item.title}</button><small>Saved content</small></td><td>{displayChannel(r.detail?.channel)}</td><td>v{r.detail?.current.number??r.item.version}</td><td>{r.issues===undefined?<span className="dr-text-muted">{r.error?'Unavailable':'Not tested'}</span>:<span className={'dr-issue '+(r.issues?'dr-issue-alert':'dr-issue-good')}>{r.issues} {r.issues===1?'finding':'findings'}</span>}</td><td><span className={'dr-pill dr-pill-'+r.status}>{r.status==='issues'?'Needs fixes':r.status==='clear'?'Ready for review':r.status==='reviewed'?'Approved current version':r.status==='untested'?'Awaiting test':'Data unavailable'}</span></td><td>{dateLabel(r.latestRunAt)}</td><td><button type="button" className="dr-open" aria-label={`Open ${r.item.title}`} onClick={()=>onOpen(r.item.id)}><ArrowRight size={17}/></button></td></tr>)}</tbody></table></div><div className="dr-pagination"><span>{filtered.length} matching draft{filtered.length===1?'':'s'} · Page {Math.min(page,pageCount)} of {pageCount}</span><div><button type="button" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>Previous</button><button type="button" disabled={page>=pageCount} onClick={()=>setPage(p=>p+1)}>Next</button></div></div></>}
    <div className="dr-footnote"><ShieldCheck size={17}/><span>Figures are loaded from your current backend. “Ready for review” means zero configured-rule findings, not factual or legal approval. Reviewer identity, dated authorship, and verified sign-off are not fabricated where the backend does not provide them.</span></div>
    </section>
  </div>;
}
