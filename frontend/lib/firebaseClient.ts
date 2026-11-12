import {initializeApp,getApps} from '@firebase/app';
import {getAuth,GoogleAuthProvider,signInWithPopup,signOut,type Auth} from '@firebase/auth';
const config={apiKey:process.env.NEXT_PUBLIC_FIREBASE_API_KEY,authDomain:process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,projectId:process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,appId:process.env.NEXT_PUBLIC_FIREBASE_APP_ID};
export let auth:Auth|null=null;
try{if(config.apiKey&&config.projectId){auth=getAuth(getApps()[0]||initializeApp(config));}}catch{}
export const login=()=>auth?signInWithPopup(auth,new GoogleAuthProvider()):Promise.reject(new Error('Fill the public Firebase configuration in frontend/.env.local and restart the frontend.'));
export const logout=()=>auth?signOut(auth):Promise.resolve();
