import {useEffect, useMemo, useState} from 'react';
import {ArrowRight, CheckCircle2, ChevronDown, ChevronUp, CircleAlert, FileSearch, RotateCcw} from 'lucide-react';
import './annotated-review.css';

export type AnnotatedFinding = {
  id:string; rule_code:string; category:string; source:string; title:string;
  explanation:string; matched_text:string; start:number; end:number; suggestion:string;
};

type Props = {
  content:string;
  checkedContent:string;
  findings:AnnotatedFinding[];
  version:number;
  checkedRules:number;
  onApply:(finding:AnnotatedFinding)=>void;
  onRetest:()=>void;
  busy:boolean;
};

function safeRanges(text:string, findings:AnnotatedFinding[]) {
  const ordered = findings.filter(f => Number.isInteger(f.start) && Number.isInteger(f.end) &&
    f.start>=0 && f.end>f.start && f.end<=text.length && text.slice(f.start,f.end)===f.matched_text)
    .sort((a,b)=>a.start-b.start || b.end-a.end);
  const selected:AnnotatedFinding[]=[];
  let cursor=0;
  for(const f of ordered){if(f.start>=cursor){selected.push(f);cursor=f.end;}}
  return selected;
}

export default function AnnotatedReview({content,checkedContent,findings,version,checkedRules,onApply,onRetest,busy}:Props){
  const [activeId,setActiveId]=useState<string|null>(null);
  const [expanded,setExpanded]=useState(true);
  const valid=content===checkedContent;
  const ranges=useMemo(()=>safeRanges(checkedContent,findings),[checkedContent,findings]);
  useEffect(()=>{setActiveId(null)},[version,checkedContent]);
  const active=findings.find(f=>f.id===activeId) || findings[0] || null;
  const supported=active && checkedContent.slice(active.start,active.end)===active.matched_text;
  const canApply=Boolean(valid && supported && active?.suggestion && !busy);
  const proposed=active && supported && active.suggestion
    ? checkedContent.slice(0,active.start)+active.suggestion+checkedContent.slice(active.end)
    : null;
  const pieces:(string|AnnotatedFinding)[]=[];
  let pos=0;
  for(const range of ranges){
    if(range.start>pos)pieces.push(checkedContent.slice(pos,range.start));
    pieces.push(range);
    pos=range.end;
  }
  if(pos<checkedContent.length)pieces.push(checkedContent.slice(pos));
  return <section className="ar-shell" aria-label="Interactive annotated inspection">
    <div className="ar-heading">
      <div><div className="ar-kicker">CONTENT LAB / ANNOTATED INSPECTION</div><h3>Inspect the actual words.</h3></div>
      <button type="button" className="ar-collapse" aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)}>
        {expanded?<ChevronUp size={16}/>:<ChevronDown size={16}/>} {expanded?'Collapse':'Expand'}
      </button>
    </div>
    {expanded&&<>
      <div className="ar-summary">
        <span><FileSearch size={15}/> Version {version}</span>
        <span>{checkedRules} configured checks</span>
        <span className={findings.length?'ar-summary-bad':'ar-summary-good'}>{findings.length} finding{findings.length===1?'':'s'}</span>
      </div>
      {!valid&&<div className="ar-stale" role="status"><CircleAlert size={18}/><span>The editor has changed since this test. Highlights show the previously tested version; retest before applying a correction.</span><button type="button" disabled={busy} onClick={onRetest}><RotateCcw size={14}/> Retest</button></div>}
      <div className="ar-document" aria-label="Tested draft with clickable findings">
        {pieces.length===0?<span className="ar-empty-text">No text in the tested version.</span>:pieces.map((piece,i)=>typeof piece==='string'?<span key={`t-${i}`}>{piece}</span>:<button key={`f-${piece.id}-${i}`} type="button"
          aria-pressed={active?.id===piece.id} title={`Inspect ${piece.rule_code}: ${piece.title}`}
          className={`ar-highlight ${active?.id===piece.id?'ar-highlight-active':''}`}
          onClick={()=>setActiveId(piece.id)}>{piece.matched_text}</button>)}
      </div>
      <p className="ar-caption">Click any highlighted phrase to inspect its rule and a proposed correction. Only exact, non-overlapping matches are highlighted; all recorded findings remain in the list below.</p>
      {findings.length===0?<div className="ar-clear"><CheckCircle2 size={19}/><div><strong>No configured-rule findings detected.</strong><span>This does not establish factual correctness or approval.</span></div></div>:<div className="ar-detail-grid">
        <div className="ar-finding-list" aria-label="Finding selection">
          <div className="ar-field-title">ISSUES IN THIS TEST</div>
          {findings.map((f,i)=><button type="button" key={`${f.id}-${i}`} className={`ar-finding-item ${active?.id===f.id?'ar-finding-selected':''}`} onClick={()=>setActiveId(f.id)}>
            <span className="ar-finding-number">{String(i+1).padStart(2,'0')}</span>
            <span><strong>{f.title}</strong><small>{f.rule_code} · {f.category}</small></span>
            <ArrowRight size={16}/>
          </button>)}
        </div>
        {active&&<div className="ar-detail" aria-live="polite">
          <div className="ar-detail-top"><span className="ar-rule-label">{active.rule_code} · {active.category}</span><span className="ar-detected">FLAGGED BY RULE</span></div>
          <h4>{active.title}</h4>
          <div className="ar-evidence-block"><small>TRIGGERING TEXT</small><blockquote>“{active.matched_text}”</blockquote></div>
          <p>{active.explanation}</p>
          <div className="ar-source"><strong>Policy reference</strong><span>{active.source||'No reference label provided'}</span></div>
          <div className="ar-evidence-block ar-repair-block"><small>PROPOSED WORDING</small><strong>{active.suggestion||'No automated correction available — human edit required.'}</strong></div>
          {proposed&&<details className="ar-compare"><summary>Preview updated document</summary><p>{proposed}</p></details>}
          <button className="ar-apply" type="button" disabled={!canApply} onClick={()=>onApply(active)}>{active.suggestion?'Apply correction to editor':'Manual correction required'} <ArrowRight size={16}/></button>
          <p className="ar-fineprint">Applying changes the editor only. Save a revision and retest before review. Policy references are rule metadata, not independently verified factual evidence.</p>
        </div>}
      </div>}
    </>}
  </section>;
}
