
import React, {useCallback, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import LoginPage from './LoginPage';
import IntroPage from './IntroPage';
import {API_BASE, authFetch, clearToken, getToken} from './authClient';
import './style.css';
import './intro.css';

type User = {id:string;email:string;display_name:string};

function Root(){
 const [user,setUser] = useState<User|null>(null);
 const [showIntro,setShowIntro] = useState(false);
 const [sessionVersion,setSessionVersion] = useState(0);

 // New logins and registrations begin on the introduction screen.
 // Refreshing an already authenticated session returns to the workspace.
 const onAuthenticated = useCallback((nextUser:User,restored:boolean)=>{
   setUser(nextUser);
   setShowIntro(!restored);
 },[]);

 useEffect(()=>{
   const expired=()=>{
     setUser(null);
     setShowIntro(false);
     setSessionVersion(x=>x+1);
   };
   window.addEventListener('glitchlab-session-expired',expired);
   return()=>window.removeEventListener('glitchlab-session-expired',expired);
 },[]);

 async function logout(){
   try{
     if(getToken()){
       await authFetch(`${API_BASE}/auth/logout`,{method:'POST'});
     }
   }finally{
     clearToken();
     setUser(null);
     setShowIntro(false);
     setSessionVersion(x=>x+1);
   }
 }

 if(!user){
   return <LoginPage
     key={sessionVersion}
     onAuthenticated={onAuthenticated}
   />;
 }

 if(showIntro){
   return <IntroPage
     userName={user.display_name}
     onContinue={()=>setShowIntro(false)}
     onLogout={()=>void logout()}
   />;
 }

 return <App
   userName={user.display_name}
   onLogout={()=>void logout()}
 />;
}

createRoot(document.getElementById('root')!).render(
 <React.StrictMode>
   <Root/>
 </React.StrictMode>
);
