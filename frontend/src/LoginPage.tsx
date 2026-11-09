
import {useEffect, useState, type FormEvent} from 'react';
import {
  ArrowRight, Eye, EyeOff, LockKeyhole,
  Mail, ShieldCheck, Sparkles
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
  const [mode,setMode] = useState<'login'|'register'>('login');
  const [checking,setChecking] = useState(Boolean(getToken()));
  const [email,setEmail] = useState('');
  const [name,setName] = useState('');
  const [password,setPassword] = useState('');
  const [show,setShow] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');

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

  async function submit(e:FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError('');

    try {
      const response = await fetch(
        `${API_BASE}/auth/${mode==='login'?'login':'register'}`,
        {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify(
            mode==='login'
              ? {email,password}
              : {email,password,display_name:name}
          )
        }
      );

      const data = await response.json().catch(()=>({
        detail:'Unable to reach server.'
      }));

      if(!response.ok) {
        throw new Error(
          typeof data.detail==='string'
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((x:{msg:string})=>x.msg).join('; ')
              : 'Sign-in failed'
        );
      }

      const session = data as Session;
      saveToken(session.token);

      // A fresh login or registration displays the introduction.
      onAuthenticated(session.user,false);

    } catch(ex) {
      setError(
        ex instanceof Error
          ? ex.message
          : 'Unable to sign in.'
      );
    } finally {
      setBusy(false);
    }
  }

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

        <div className="gl-login-card">
          <div className="gl-login-label">
            <span className="gl-bullet"/>
            AUTHORIZED WORKSPACE ENTRY
          </div>

          <h2>
            {mode==='login'
              ? 'Welcome back.'
              : 'Make your mark.'}
          </h2>

          <p className="gl-login-description">
            {mode==='login'
              ? 'Your workspace is ready when you are.'
              : 'Create an account to explore the shared demonstration lab.'}
          </p>

          <div
            className="gl-auth-tabs"
            role="group"
            aria-label="Authentication method"
          >
            <button
              type="button"
              className={mode==='login'?'selected':''}
              onClick={()=>{
                setMode('login');
                setError('');
              }}
            >
              SIGN IN
            </button>

            <button
              type="button"
              className={mode==='register'?'selected':''}
              onClick={()=>{
                setMode('register');
                setError('');
              }}
            >
              CREATE ACCOUNT
            </button>
          </div>

          <form onSubmit={submit}>

            {mode==='register'&&(
              <label className="gl-form-field">
                YOUR NAME
                <input
                  autoComplete="name"
                  required
                  minLength={2}
                  maxLength={70}
                  value={name}
                  onChange={e=>setName(e.target.value)}
                  placeholder="e.g. Axiom Reviewer"
                />
              </label>
            )}

            <label className="gl-form-field">
              EMAIL ADDRESS
              <div className="gl-input-wrap">
                <Mail aria-hidden="true" size={17}/>
                <input
                  autoComplete="email"
                  type="email"
                  required
                  value={email}
                  onChange={e=>setEmail(e.target.value)}
                  placeholder="you@studio.com"
                />
              </div>
            </label>

            <label className="gl-form-field">
              PASSWORD
              <div className="gl-input-wrap">
                <LockKeyhole aria-hidden="true" size={17}/>

                <input
                  autoComplete={
                    mode==='login'
                      ? 'current-password'
                      : 'new-password'
                  }
                  type={show?'text':'password'}
                  minLength={mode==='register'?12:undefined}
                  required
                  value={password}
                  onChange={e=>setPassword(e.target.value)}
                  placeholder={
                    mode==='register'
                      ? 'At least 12 characters'
                      : 'Enter your password'
                  }
                />

                <button
                  type="button"
                  className="gl-show"
                  aria-label={show?'Hide password':'Show password'}
                  onClick={()=>setShow(!show)}
                >
                  {show
                    ? <EyeOff size={17}/>
                    : <Eye size={17}/>}
                </button>
              </div>
            </label>

            {error&&(
              <p className="gl-login-error" role="alert">
                {error}
              </p>
            )}

            <button
              className="gl-enter"
              type="submit"
              disabled={busy||checking}
            >
              {checking
                ? 'CHECKING SESSION…'
                : busy
                  ? 'PLEASE WAIT…'
                  : mode==='login'
                    ? 'ENTER GLITCHLAB'
                    : 'CREATE ACCOUNT & ENTER'}
              <ArrowRight size={19}/>
            </button>

          </form>

          <p className="gl-login-disclosure">
            <ShieldCheck size={16}/>
            Demo accounts share the same synthetic workspace.
            Do not upload private or confidential materials.
          </p>
        </div>

        <div className="gl-login-copyright">
          © 2026 AXIOM LABS
          <span>✳</span>
          BUILT FOR BRANDS THAT QUESTION EVERYTHING.
        </div>
      </section>

    </div>
  );
}
