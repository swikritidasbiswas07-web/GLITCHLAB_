import {useEffect,useState} from 'react';
import {authFetch} from './authClient';
import './workspace-evidence-atlas.css';
const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';
type Workspace={id:string;name:string;role:string};
type Draft={id:string;title:string;version:number};
type Version={id:string;number:number;content:string};
type Source={id:string;filename:string;kind:string;characters:number};
type Evidence={id:string;source_id:string;filename:string;quote:string;source_locator:string};
type Link={id:string;stance:string;rationale:string;quote:string;filename:string;attested_by:string|null};
type Claim={id:string;claim_text:string;status:string;version_number:number;links:Link[]};
async function req<T>(path:string, options:RequestInit={}):Promise<T>{
 const r=await authFetch(`${API}${path}`,{...options,headers:{'Content-Type':'application/json',...options.headers}});
 if(!r.ok){const body=await r.json().catch(()=>({detail:'Request failed'}));throw new Error(body.detail||`HTTP ${r.status}`)}
 return r.json();
}
export default function WorkspaceEvidenceAtlas(){
 const [workspaces,setWorkspaces]=useState<Workspace[]>([]),[workspaceId,setWorkspaceId]=useState('');
 const [drafts,setDrafts]=useState<Draft[]>([]),[draftId,setDraftId]=useState('');
 const [versions,setVersions]=useState<Version[]>([]),[versionId,setVersionId]=useState('');
 const [sources,setSources]=useState<Source[]>([]),[sourceId,setSourceId]=useState('');
 const [uploadFile,setUploadFile]=useState<File|null>(null);
 const [evidence,setEvidence]=useState<Evidence[]>([]),[evidenceId,setEvidenceId]=useState('');
 const [claims,setClaims]=useState<Claim[]>([]),[claimId,setClaimId]=useState('');
 const [quote,setQuote]=useState(''),[locator,setLocator]=useState(''),[claimText,setClaimText]=useState('');
 const [stance,setStance]=useState('supports'),[rationale,setRationale]=useState('');
 const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 const ws=workspaces.find(w=>w.id===workspaceId),canEdit=ws?.role==='admin'||ws?.role==='editor',
 canClaim=canEdit||ws?.role==='creator',canAttest=ws?.role==='admin'||ws?.role==='reviewer';
 const base=`/workspaces/${encodeURIComponent(workspaceId)}/evidence-atlas`;
 const post=async(path:string,body?:object)=>req(path,{method:'POST',...(body?{body:JSON.stringify(body)}:{})});
 const run=async(fn:()=>Promise<void>)=>{setError('');setNotice('');setBusy(true);try{await fn()}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
 useEffect(()=>{req<Workspace[]>('/workspaces').then(w=>{setWorkspaces(w);setWorkspaceId(w[0]?.id||'')}).catch(e=>setError(String(e)))},[]);
 useEffect(()=>{setDraftId('');setSourceId('');setClaims([]);setEvidence([]);if(!workspaceId)return;
 Promise.all([req<Draft[]>(`/workspaces/${workspaceId}/drafts`),req<Source[]>(`${base}/sources`),req<Evidence[]>(`${base}/items`)]).then(([d,s,e])=>{
 setDrafts(d);setDraftId(d[0]?.id||'');setSources(s);setSourceId(s[0]?.id||'');setEvidence(e);setEvidenceId(e[0]?.id||'')}).catch(e=>setError(String(e)))},[workspaceId]);
 useEffect(()=>{setVersionId('');setClaims([]);if(!draftId||!workspaceId)return;
 req<{versions:Version[]}>(`/workspaces/${workspaceId}/drafts/${draftId}`).then(d=>{
 setVersions(d.versions);setVersionId(d.versions[0]?.id||'')}).catch(e=>setError(String(e)))},[workspaceId,draftId]);
 const refreshClaims=async()=>{if(draftId){setClaims(await req<Claim[]>(`${base}/drafts/${draftId}/claims`))}};
 useEffect(()=>{refreshClaims().catch(e=>setError(String(e)))},[workspaceId,draftId]);
 const uploadSource=()=>run(async()=>{
  if(!uploadFile)throw new Error('Choose a .txt document first');
  if(!uploadFile.name.toLowerCase().endsWith('.txt'))throw new Error('Please select a .txt document');
  if(uploadFile.size>256*1024)throw new Error('The maximum text document size is 256 KiB');
  const text=await uploadFile.text();
  if(!text.trim())throw new Error('The selected text document is empty');
  const saved=await post(`${base}/sources/text`,{filename:uploadFile.name,content:text}) as {id:string};
  const updated=await req<Source[]>(`${base}/sources`);
  setSources(updated);setSourceId(saved.id);setUploadFile(null);
  const fileInput=document.getElementById('ea-source-file') as HTMLInputElement|null;
  if(fileInput)fileInput.value='';
  setNotice('Document saved in this workspace. Choose an exact quotation below.');
 });
 const selectedVersion=versions.find(v=>v.id===versionId);
 return <div className="ea-root">
 <div className="ea-intro"><span className="ea-kicker">EVIDENCE ATLAS / CLAIMSCOPE · 05I</span><h2>From claims to traceable evidence.</h2><p>Quotes are checked against stored source text. Reviewers attest whether a source actually supports or contradicts a claim. Statuses are human-attested—not AI-certified facts.</p></div>
 {error&&<p className="ea-error" role="alert">{error}</p>}{notice&&<p className="ea-notice" role="status">{notice}</p>}
 <div className="ea-controls">
 <label>Workspace<select value={workspaceId} onChange={e=>setWorkspaceId(e.target.value)}>{workspaces.map(w=><option value={w.id} key={w.id}>{w.name} · {w.role}</option>)}</select></label>
 <label>Draft<select value={draftId} onChange={e=>setDraftId(e.target.value)}>{drafts.map(d=><option value={d.id} key={d.id}>{d.title}</option>)}</select></label>
 <label>Saved version<select value={versionId} onChange={e=>setVersionId(e.target.value)}>{versions.map(v=><option value={v.id} key={v.id}>Version {v.number}</option>)}</select></label>
 </div>
 {selectedVersion&&<div className="ea-panel"><h3>Saved copy · v{selectedVersion.number}</h3><p className="ea-copy">{selectedVersion.content}</p><small>Copy an exact factual claim from this saved version into the form below.</small></div>}
 <div className="ea-grid">
 <section className="ea-panel"><div className="ea-kicker">01 · QUOTE A SOURCE</div><h3>Register evidence</h3>
 {canEdit?<><div className="ea-upload"><strong>Upload a source document</strong><p className="ea-muted">Import a UTF-8 .txt file, up to 256 KiB. Saved privately to the selected workspace.</p>
 <label>Choose .txt file<input id="ea-source-file" type="file" accept=".txt,text/plain" onChange={e=>setUploadFile(e.target.files?.[0]||null)}/></label>
 <button disabled={busy||!uploadFile} onClick={uploadSource}>Upload source to workspace</button></div>
 <label>Stored source<select value={sourceId} onChange={e=>setSourceId(e.target.value)}>{sources.map(s=><option value={s.id} key={s.id}>{s.filename}</option>)}</select></label>
 <label>Exact quotation<textarea value={quote} onChange={e=>setQuote(e.target.value)} rows={3} placeholder="Paste exact words from the stored source"/></label>
 <label>Page / section (optional)<input value={locator} onChange={e=>setLocator(e.target.value)} placeholder="e.g. Table 2, page 4"/></label>
 <button disabled={busy||!sourceId||!quote.trim()} onClick={()=>run(async()=>{await post(`${base}/items`,{source_id:sourceId,quote,locator});const e=await req<Evidence[]>(`${base}/items`);setEvidence(e);setEvidenceId(e[0]?.id||'');setQuote('');setNotice('Quote anchored to its stored source snapshot.')})}>Record source quote</button></>:<p className="ea-muted">Editors and admins may register evidence.</p>}
 {!sources.length&&<p className="ea-muted">No sources yet. Upload a .txt document using the form above.</p>}
 <p className="ea-muted">{evidence.length} verified quote location(s) in this workspace.</p></section>
 <section className="ea-panel"><div className="ea-kicker">02 · NAME THE CLAIM</div><h3>Extract a saved claim</h3>
 {canClaim?<><label>Verbatim draft excerpt<textarea value={claimText} onChange={e=>setClaimText(e.target.value)} rows={3} placeholder="Paste a factual sentence from the selected version"/></label>
 <button disabled={busy||!versionId||!claimText.trim()} onClick={()=>run(async()=>{await post(`${base}/claims`,{draft_id:draftId,version_id:versionId,claim_text:claimText});await refreshClaims();setClaimText('');setNotice('Claim linked to this exact saved draft version.')})}>Register claim</button></>:<p className="ea-muted">Draft editors and creators may register claims.</p>}
 <p className="ea-muted">Claims remain associated with their saved version even after edits.</p></section>
 <section className="ea-panel"><div className="ea-kicker">03 · CONNECT THE RECORD</div><h3>Relate evidence to claim</h3>
 {canEdit?<><label>Claim<select value={claimId} onChange={e=>setClaimId(e.target.value)}><option value="">Choose claim</option>{claims.map(c=><option value={c.id} key={c.id}>{c.claim_text.slice(0,85)} · v{c.version_number}</option>)}</select></label>
 <label>Source quotation<select value={evidenceId} onChange={e=>setEvidenceId(e.target.value)}><option value="">Choose evidence</option>{evidence.map(e=><option value={e.id} key={e.id}>{e.filename}: {e.quote.slice(0,70)}</option>)}</select></label>
 <label>Relationship<select value={stance} onChange={e=>setStance(e.target.value)}><option value="supports">Supports</option><option value="contradicts">Contradicts</option><option value="context">Context only</option></select></label>
 <label>Reasoning<textarea value={rationale} onChange={e=>setRationale(e.target.value)} rows={2} placeholder="Why does the quotation relate to this claim?"/></label>
 <button disabled={busy||!claimId||!evidenceId||rationale.trim().length<4} onClick={()=>run(async()=>{await post(`${base}/links`,{claim_id:claimId,evidence_id:evidenceId,stance,rationale});await refreshClaims();setRationale('');setNotice('Relationship proposed; requires independent reviewer attestation.')})}>Propose evidence link</button></>:<p className="ea-muted">Editors and admins can propose evidence relationships.</p>}</section>
 </div>
 <section className="ea-panel"><div className="ea-review-head"><div className="ea-kicker">04 · REVIEWED CLAIMS</div><button className="ea-secondary" onClick={()=>run(refreshClaims)} disabled={busy}>Refresh</button></div>
 {claims.length===0?<p className="ea-muted">No registered claims for this draft yet.</p>:claims.map(c=><article className="ea-claim" key={c.id}><div className="ea-claimtop"><strong>“{c.claim_text}”</strong><span className={`ea-state ea-${c.status}`}>{c.status.replaceAll('_',' ')}</span></div><small>Version {c.version_number} · Status derives only from independently attested evidence relationships</small>
 {c.links.length===0&&<p className="ea-muted">No linked evidence yet.</p>}
 {c.links.map(l=><div className="ea-link" key={l.id}><div><b>{l.stance.toUpperCase()}</b> · {l.filename} · {l.attested_by?'Attested':'Pending independent review'}</div><blockquote>“{l.quote}”</blockquote><p>{l.rationale}</p>{canAttest&&!l.attested_by&&<button disabled={busy} onClick={()=>run(async()=>{await post(`${base}/links/${l.id}/attest`);await refreshClaims();setNotice('Relationship attested by authenticated reviewer.')})}>Attest this relationship</button>}</div>)}
 </article>)}</section>
 </div>;
}
