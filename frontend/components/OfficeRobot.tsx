export default function OfficeRobot({name,variant=0}:{name:string;variant?:number}){
 return <svg className={`office-robot bot-shape-${variant%5}`} x="-24" y="-32" width="48" height="64" viewBox="-24 -32 48 64" aria-hidden="true">
  <ellipse className="bot-shadow" cx="0" cy="27" rx="18" ry="5"/>
  <path className="bot-antenna" d="M0-20V-28"/><circle className="bot-beacon" cy="-29" r="3"/>
  <rect className="bot-head" x="-18" y="-21" width="36" height="25" rx={variant%2?11:7}/>
  <rect className="bot-face" x="-13" y="-16" width="26" height="14" rx="5"/>
  <path className="bot-eyes" d="M-8-10v3M8-10v3"/><path className="bot-smile" d="M-3-5q3 3 6 0"/>
  <rect className="bot-torso" x="-13" y="6" width="26" height="20" rx="7"/>
  <text className="bot-letter" x="0" y="20" textAnchor="middle">{name.slice(0,1)}</text>
  <path className="bot-arm bot-left-arm" d="M-15 10l-5 9"/><path className="bot-arm bot-right-arm" d="M15 10l5 9"/>
  <path className="bot-feet" d="M-8 26v4M8 26v4"/>
 </svg>;
}
