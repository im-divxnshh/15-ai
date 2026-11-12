"use client";
import {useEffect,useState} from 'react';
export default function ThemeSwitch(){
 const [theme,setTheme]=useState('dark');
 useEffect(()=>setTheme(document.documentElement.dataset.theme||'dark'),[]);
 return <button className="theme-button" data-theme-toggle aria-label={`Switch to ${theme==='dark'?'light':'dark'} theme`} onClick={()=>{
  const next=theme==='dark'?'light':'dark';setTheme(next);document.documentElement.dataset.theme=next;
  try{localStorage.setItem('nova-theme',next);}catch{}
 }}>{theme==='dark'?'☀ Light':'☾ Dark'}</button>;
}
