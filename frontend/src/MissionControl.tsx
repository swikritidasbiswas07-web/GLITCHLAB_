import {useState} from 'react';
import {ArrowRight, BookOpenCheck, ChevronDown, ChevronUp, ClipboardCheck, FlaskConical, GitCompareArrows, Play, RotateCcw, ShieldCheck} from 'lucide-react';
import './mission-control.css';

type Destination = 'Draft Radar' | 'Content Lab' | 'Policy Vault' | 'Governance Lab' | 'Review Station';
type Mission = {title:string; label:string; summary:string; instructions:string[]; target:Destination; action:string; icon:typeof Play};

const MISSIONS:Mission[]=[
 {title:'Inspect a live draft',label:'01 / FIND THE GLITCH',summary:'Choose saved content, run its configured policy rules and select a highlighted finding.',instructions:['Open an existing draft from Draft Radar, ideally one showing open findings.','In Content Lab, click Save revision & test if the latest version has not been checked.','Select a highlighted phrase in Annotated Inspection to see its rule and proposed wording.'],target:'Draft Radar',action:'Open Draft Radar',icon:FlaskConical},
 {title:'Repair and retest',label:'02 / TEST THE REPAIR',summary:'Preview a suggested change, edit the text, save a new version and check the result.',instructions:['In Content Lab, select a flagged phrase and open the correction preview.','Apply a correction to the editor; revise awkward grammar manually if needed.','Click Save revision & test. Verify the new version and updated finding count.'],target:'Content Lab',action:'Open Content Lab',icon:GitCompareArrows},
 {title:'Examine the policy source',label:'03 / INSPECT THE RULE',summary:'Inspect configured rules and source-document imports without confusing policy metadata with verified evidence.',instructions:['Open Policy Vault and inspect the rule that triggered your finding.','Optionally import a permitted TXT or text-based PDF guideline.','Review proposed rules before manually activating anything.'],target:'Policy Vault',action:'Open Policy Vault',icon:BookOpenCheck},
 {title:'Record a human decision',label:'04 / CLOSE THE LOOP',summary:'Inspect the tested version, leave a review decision, and check its recorded history.',instructions:['Open Review Station with a selected and tested draft.','Only approve when checks are clear and wording is acceptable; otherwise request changes.','Inspect the history for the recorded reviewer, decision and timestamp.'],target:'Review Station',action:'Open Review Station',icon:ClipboardCheck},
];

const STORAGE_KEY='glitchlab_round3_mission_visits';
function getVisited():number[]{
 try{const raw=window.sessionStorage.getItem(STORAGE_KEY); const parsed:unknown=raw?JSON.parse(raw):[];return Array.isArray(parsed)?parsed.filter((x):x is number=>typeof x==='number'&&Number.isInteger(x)&&x>=0&&x<MISSIONS.length):[];}catch{return []}
}

export default function MissionControl({onNavigate}:{onNavigate:(page:Destination)=>void}){
 const [visited,setVisited]=useState<number[]>(getVisited);
 const [expanded,setExpanded]=useState<number|null>(0);
 const [hidden,setHidden]=useState(false);
 function visit(index:number){
   const next=Array.from(new Set([...visited,index]));
   setVisited(next);
   try{window.sessionStorage.setItem(STORAGE_KEY,JSON.stringify(next));}catch{/* Private browsing may prevent session storage. */}
   onNavigate(MISSIONS[index].target);
 }
 function reset(){setVisited([]);setExpanded(0);try{window.sessionStorage.removeItem(STORAGE_KEY)}catch{/* optional */}}
 if(hidden)return <div className="mc-reopen"><span><ShieldCheck size={17}/> GLITCHLAB_ / MISSION CONTROL</span><button type="button" onClick={()=>setHidden(false)}>Show walkthrough <ChevronDown size={16}/></button></div>;
 return <section className="mc-shell" aria-label="Interactive GLITCHLAB_ walkthrough">
  <div className="mc-heading">
   <div><span className="mc-eyebrow">THE OBSERVATORY / GUIDED EXPLORATION</span><h2>Find the glitch. Follow the evidence.</h2><p>Four real workflows. Choose a mission to explore the live application at your own pace.</p></div>
   <button type="button" className="mc-hide" onClick={()=>setHidden(true)}>Hide guide <ChevronUp size={16}/></button>
  </div>
  <div className="mc-progress"><div><strong>{visited.length} of {MISSIONS.length} opened</strong><span>Tracks visited destinations on this browser tab — not verified task completion.</span></div><div className="mc-track"><div style={{width:`${100*visited.length/MISSIONS.length}%`}}/></div></div>
  <div className="mc-missions">
   {MISSIONS.map((mission,index)=>{const Icon=mission.icon;return <article className={'mc-card '+(expanded===index?'mc-card-active':'')} key={mission.title}>
     <button className="mc-card-head" type="button" onClick={()=>setExpanded(expanded===index?null:index)} aria-expanded={expanded===index}>
      <span className="mc-icon"><Icon size={19}/></span><span className="mc-titleblock"><small>{mission.label}</small><strong>{mission.title}</strong></span><span className="mc-chevron">{expanded===index?<ChevronUp size={17}/>:<ChevronDown size={17}/>}</span>
     </button>
     <p>{mission.summary}</p>
     {expanded===index&&<div className="mc-details"><strong>WHAT TO TRY</strong><ol>{mission.instructions.map(step=><li key={step}>{step}</li>)}</ol></div>}
     <button type="button" className="mc-go" onClick={()=>visit(index)}>{mission.action}<ArrowRight size={16}/></button>
     {visited.includes(index)&&<span className="mc-visited"><ShieldCheck size={13}/> Destination opened</span>}
   </article>})}
  </div>
  <div className="mc-bottom"><p><b>For final-round judging:</b> This guide links only to implemented Round 2/Build 02 capabilities. Persistent isolated workspaces, source-grounded claim classifications, and versioned policy releases remain separate Round 3 engineering deliverables.</p><button type="button" onClick={reset}><RotateCcw size={15}/> Reset guide visits</button></div>
 </section>
}
