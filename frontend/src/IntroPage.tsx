import {ArrowDown, ArrowRight, BookOpen, CheckCheck, ClipboardCheck, FileSearch, FlaskConical, GitCompareArrows, LogOut, ShieldCheck, Sparkles} from 'lucide-react';

type Props = {userName:string;onContinue:()=>void;onLogout:()=>void};
const stations = [
 {number:'01',title:'Content Lab',desc:'Draft, test, revise, and trace every rule finding to its evidence.',Icon:FlaskConical},
 {number:'02',title:'Policy Vault',desc:'Organize brand rules, channel scopes, and imported reference material.',Icon:BookOpen},
 {number:'03',title:'Governance Lab',desc:'Explore numeric claim conflicts, policy unit tests, and multi-patch previews.',Icon:GitCompareArrows},
 {number:'04',title:'Insights',desc:'Inspect activity counts generated from the shared demonstration database.',Icon:FileSearch},
 {number:'05',title:'Review Station',desc:'Record human decisions against the latest tested draft version.',Icon:ClipboardCheck},
];

export default function IntroPage({userName,onContinue,onLogout}:Props){
 return <div className="gl-intro">
   <header className="gl-intro-top">
     <div className="gl-intro-brand"><span className="gl-intro-icon">⌁</span><span><b>GLITCHLAB<span>_</span></b><small>AN AXIOM LABS EXPERIMENT</small></span></div>
     <div className="gl-intro-actions">
       <span className="gl-intro-user">WELCOME, {userName}</span>
       <button type="button" className="gl-intro-skip" onClick={onContinue}>SKIP TO DASHBOARD <ArrowRight size={17}/></button>
     </div>
   </header>
   <main className="gl-intro-main">
     <section className="gl-intro-hero">
       <div className="gl-intro-hero-copy">
         <div className="gl-intro-eyebrow"><span className="gl-intro-dot"/> 00 / THE OPENING NOTE</div>
         <h1>WELCOME TO<br/><em>THE LAB.</em></h1>
         <p className="gl-intro-lead">A little context before the experiments begin.</p>
         <p>GLITCHLAB_ is an experimental brand-content governance studio. It brings together rule-based checks, optional AI-assisted analysis, explainable suggestions, and human review—so a draft can be challenged before it is published.</p>
         <button type="button" className="gl-intro-explore" onClick={()=>document.getElementById('gl-intro-tour')?.scrollIntoView({behavior:'smooth'})}>EXPLORE THE STUDIO <ArrowDown size={17}/></button>
       </div>
       <div className="gl-intro-art" aria-hidden="true"><div className="gl-intro-art-ring"><span>GL</span><b>✳</b></div><div className="gl-intro-art-caption">A SPACE FOR<br/>BETTER QUESTIONS.</div><span className="gl-intro-art-cross">+</span></div>
     </section>

     <section className="gl-intro-note" aria-label="The project philosophy">
       <span>THE IDEA</span><p>“GOOD IDEAS DESERVE <em>BETTER RULES.</em>”</p><span>EST. 2026 / AXIOM LABS</span>
     </section>

     <section className="gl-intro-section" id="gl-intro-tour">
       <div className="gl-intro-section-head"><div><span className="gl-intro-eyebrow">01 / INSIDE THE WORKSPACE</span><h2>FIVE PLACES.<br/>ONE PURPOSE.</h2></div><p>This is an introductory map, not a replacement for the detailed Features and How It Works pages inside the dashboard.</p></div>
       <div className="gl-intro-stations">{stations.map(({number,title,desc,Icon})=><article className="gl-intro-station" key={number}><div className="gl-intro-station-top"><span>{number}</span><Icon size={25} strokeWidth={1.6}/></div><h3>{title}</h3><p>{desc}</p></article>)}</div>
     </section>

     <section className="gl-intro-section gl-intro-split">
       <div className="gl-intro-principles"><span className="gl-intro-eyebrow">02 / THE NON-NEGOTIABLES</span><h2>BUILT TO<br/>BE QUESTIONED.</h2><div className="gl-intro-principle"><CheckCheck size={22}/><p><b>Show the evidence.</b> Deterministic checks identify matched text and the configured rule.</p></div><div className="gl-intro-principle"><ShieldCheck size={22}/><p><b>Keep humans in charge.</b> AI suggestions and automated checks never constitute factual or legal approval.</p></div><div className="gl-intro-principle"><Sparkles size={22}/><p><b>Make revision visible.</b> Save versions, rerun tests, and review the latest state before a decision.</p></div></div>
       <div className="gl-intro-credits"><span className="gl-intro-eyebrow">03 / THE CREDITS</span><h2>THE PEOPLE &<br/>THE PIECES.</h2><dl><div><dt>CONCEPT, DESIGN & DEVELOPMENT</dt><dd>Swikriti Das Biswas</dd></div><div><dt>PROJECT / TEAM</dt><dd>Axiom · GLITCHLAB_</dd></div><div><dt>BUILT WITH</dt><dd>React, TypeScript, Vite, FastAPI, Python & SQLite</dd></div><div><dt>OPTIONAL AI INTEGRATION</dt><dd>Google Gemini (configured backend provider)</dd></div><div><dt>INTERFACE LANGUAGE</dt><dd>Coastal editorial · Ocean-ink neo-brutalism</dd></div></dl><p className="gl-intro-credit-note">A standalone experimental project. Third-party technologies are identified for attribution, not as sponsors or endorsers.</p></div>
     </section>

     <section className="gl-intro-finish"><div><span className="gl-intro-eyebrow">04 / BEFORE YOU ENTER</span><h2>READY TO BREAK<br/>A BAD DRAFT?</h2><p>The accounts in this demonstration share one synthetic workspace. Do not upload confidential materials. A clean rule-check result is not proof that content is accurate or compliant.</p></div><button className="gl-intro-enter" type="button" onClick={onContinue}>ENTER THE DASHBOARD <ArrowRight size={22}/></button></section>
   </main>
   <footer className="gl-intro-footer"><span>© 2026 AXIOM LABS · GLITCHLAB_</span><button onClick={onLogout} type="button"><LogOut size={15}/> SIGN OUT</button><span>BUILT FOR BRANDS THAT QUESTION EVERYTHING.</span></footer>
 </div>;
}
