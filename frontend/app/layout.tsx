import type {Metadata} from 'next';
import './globals.css';
export const metadata:Metadata={title:'NOVA OS — Your AI command center',description:'One orchestrator, fourteen specialists. Plan and execute work from a living office.'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:'try{document.documentElement.dataset.theme=localStorage.getItem("nova-theme")||(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark")}catch{document.documentElement.dataset.theme="dark"}'}}/></head><body>{children}</body></html>;}
