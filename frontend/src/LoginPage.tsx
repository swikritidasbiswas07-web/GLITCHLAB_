import './demo-entry.css';

import {useEffect, useState} from 'react';
import {
  ArrowRight, ShieldCheck, Sparkles, UserRound, ClipboardCheck, FilePenLine, Settings2
} from 'lucide-react';
import {
  API_BASE, authFetch, clearToken, getToken, saveToken
} from './authClient';

type User = {
  id:string;
  email:string;
  display_name:string;
};

type Session = {
  token:string;
  user:User;
};

type DemoPersona = {id:string;name:string;role:string;workspace:string};

type Props = {
  onAuthenticated:(user:User, restored:boolean)=>void;
};

function Scallop({className=''}:{className?:string}) {
  return (
    <svg className={className} viewBox="0 0 250 250" fill="none" aria-hidden="true">
      <path
        d="M125 217C81 200 39 166 29 127c-8-29 3-47 24-48-2-27 15-41 37-35 11-28 40-30 53-3 25-18 46-4 49 22 27-1 40 22 31 48-12 42-53 84-98 106Z"
        fill="#edf7f4"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <path
        d="M125 213 45 87M125 213 69 53M125 213 106 42M125 213 143 41M125 213 187 68M125 213 221 111"
        stroke="currentColor"
        strokeWidth="2.3"
        opacity=".58"
      />
      <path
        d="M105 219q20 14 40 0"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Conch({className=''}:{className?:string}) {
  return (
    <svg className={className} viewBox="0 0 230 230" fill="none" aria-hidden="true">
      <path
        d="M194 102c12-46-18-78-57-67-38 10-47 49-29 74 13 19 42 24 56 8 13-14 3-37-13-33-13 3-16 16-7 22M195 105c-16 40-49 56-69 61-28 7-44 17-65 38l-22-17c9-27 17-45 35-61 25-23 44-18 60-33"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="m40 188-15-15 29-8-8-20 25 4-1-24 25 9M55 175l53-52M75 193l35-39M95 176l25-17"
        stroke="currentColor"
        strokeWidth="2.6"
      />
      <path
        d="M146 36c25 15 39 37 35 61M133 45c17 15 27 32 29 47"
        stroke="currentColor"
        strokeWidth="2.2"
        opacity=".55"
      />
    </svg>
  );
}

export default function LoginPage({onAuthenticated}:Props) {
  const [checking,setChecking] = useState(Boolean(getToken()));
  const [error,setError] = useState('');
  const [demoPersonas,setDemoPersonas] = useState<DemoPersona[]>([]);
  const [demoBusy,setDemoBusy] = useState<string|null>(null);
  const [personasLoaded,setPersonasLoaded] = useState(false);

  useEffect(()=>{
    let active=true;
    fetch(`${API_BASE}/auth/demo/personas`)
      .then(async response=>response.ok?response.json():null)
      .then(payload=>{if(active&&Array.isArray(payload?.personas))setDemoPersonas(payload.personas);})
      .catch(()=>{})
      .finally(()=>{if(active)setPersonasLoaded(true);});
    return ()=>{active=false;};
  },[]);

  async function enterDemo(identity:string){
    setDemoBusy(identity);setError('');
    try {
      const response=await fetch(`${API_BASE}/auth/demo/enter`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({identity})
      });
      const data=await response.json().catch(()=>({detail:'Demo entry failed'}));
      if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Demo entry failed');
      const session=data as Session;
      saveToken(session.token);
      onAuthenticated(session.user,false);
    }catch(ex){setError(ex instanceof Error?ex.message:'Demo entry failed');}
    finally{setDemoBusy(null);}
  }


  useEffect(()=>{
    const token = getToken();

    if(!token) {
      setChecking(false);
      return;
    }

    authFetch(`${API_BASE}/auth/me`)
      .then(async response=>{
        if(!response.ok) {
          throw new Error('Session expired');
        }
        return response.json();
      })
      .then((user:User)=>onAuthenticated(user,true))
      .catch(()=>clearToken())
      .finally(()=>setChecking(false));
  },[onAuthenticated]);

  return (
    <div className="gl-login">

      <section
        className="gl-login-art"
        aria-label="Welcome to GLITCHLAB"
      >
        <div className="gl-login-art-top">
          <div className="gl-login-monogram">⌁</div>
          <span>
            AXIOM LABS
            <span className="gl-art-separator">/</span>
            AN EXPERIMENTAL WORKSPACE
          </span>
        </div>

        <div className="gl-login-art-center">
          <span className="gl-kicker">
            THE BRAND GOVERNANCE STUDIO
            <span> — EST. 2026</span>
          </span>

          <h1>
            GOOD IDEAS
            <br/>
            DESERVE
            <br/>
            <em>BETTER RULES.</em>
          </h1>

          <p>
            Step inside a space where words are questioned,
            guidelines are tested, and every claim earns its place.
          </p>
        </div>

        <Scallop className="gl-shell gl-shell-one"/>
        <Conch className="gl-shell gl-shell-two"/>

        <div className="gl-login-art-bottom">
          <span>01 / ENTER THE LAB</span>
          <span>
            AN OCEAN OF BETTER DECISIONS
            <Sparkles size={16}/>
          </span>
        </div>
      </section>

      <section className="gl-login-form-area">
        <div className="gl-form-brand">
          GLITCHLAB<span>_</span>
          <small>BRAND RULES, UNDER THE MICROSCOPE</small>
        </div>

        {demoPersonas.length>0 && <section className="gl-demo-entry" aria-label="Explore by role">
          <div className="gl-login-label"><span className="gl-bullet"/> THE FOUR PERSPECTIVES</div>
          <h2>Choose your place in the lab.</h2>
          <p>Step into Nivara Studio through four distinct perspectives. Explore a populated, read-only workspace with governance workflows, evidence trails, and review decisions.</p>
          <div className="gl-demo-grid">
            {demoPersonas.map(person=>{
              const Icon=person.role==='creator'?FilePenLine:person.role==='editor'?Settings2:person.role==='reviewer'?ClipboardCheck:UserRound;
              return <button type="button" key={person.id} className="gl-demo-person" onClick={()=>void enterDemo(person.id)} disabled={Boolean(demoBusy)||checking}>
                <span className="gl-demo-person-top"><span className="gl-demo-avatar">{person.name.split(' ').map(x=>x[0]).join('')}</span><Icon size={19}/></span>
                <strong>{person.name}</strong><span className="gl-demo-role">{person.role.toUpperCase()} · {person.workspace}</span>
                <span className="gl-demo-person-action">{demoBusy===person.id?'ENTERING…':'ENTER AS '+person.name.split(' ')[0].toUpperCase()} <ArrowRight size={15}/></span>
              </button>;
            })}
          </div>
          {error&&<p className="gl-login-error" role="alert">{error}</p>}
          <p className="gl-demo-note"><ShieldCheck size={16}/> Secure, read-only demonstration. All accounts, policies, and evidence are synthetic.</p>
          <a className="gl-demo-regular" href="https://glitchlab-eight.vercel.app/" target="_blank" rel="noopener noreferrer">
            ENTER GLITCHLAB_ WITH YOUR OWN ACCOUNT <ArrowRight size={16}/>
          </a>
        </section>}
        {demoPersonas.length===0 && <section className="gl-demo-entry" aria-label="Judge demonstration status">
          <div className="gl-login-label"><span className="gl-bullet"/> THE FOUR PERSPECTIVES</div>
          <h2>Choose your place in the lab.</h2>
          <p>{personasLoaded ? 'The judge demonstration is temporarily unavailable. Please try again shortly.' : 'Loading the four demo perspectives…'}</p>
          <p className="gl-demo-note"><ShieldCheck size={16}/> This is a read-only judging sandbox. Personal sign-in and registration are hosted separately.</p>
          <a className="gl-demo-regular" href="https://glitchlab-eight.vercel.app/" target="_blank" rel="noopener noreferrer">
            ENTER GLITCHLAB_ WITH YOUR OWN ACCOUNT <ArrowRight size={16}/>
          </a>
        </section>}

        <div className="gl-login-copyright">
          © 2026 AXIOM LABS
          <span>✳</span>
          BUILT FOR BRANDS THAT QUESTION EVERYTHING.
        </div>
      </section>

    </div>
  );
}
