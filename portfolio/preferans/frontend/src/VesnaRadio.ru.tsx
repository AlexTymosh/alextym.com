/** Original vector illustration inspired by the Vesna M-212S-4 cassette recorder. */
export function VesnaRadio({className}:{className:string}) {
  return <svg viewBox="0 0 420 174" className={className} aria-hidden="true">
    <path d="M30 48V14H390V48" fill="none" stroke="#242525" strokeWidth="12" strokeLinejoin="round"/>
    <path d="M36 15H384" stroke="#a6a396" strokeWidth="2"/>
    <rect x="4" y="45" width="412" height="124" rx="3" fill="#252726" stroke="#aaa99d" strokeWidth="2"/>
    {[122,145,168,191,214,237].map((x,i)=><rect key={x} x={x} y="37" width="19" height="9" rx="1" fill={i===0?"#ab4940":"#c1c0b6"}/>)}
    {[274,300,326,352].map(x=><ellipse key={x} cx={x} cy="40" rx="8" ry="5" fill="#151616" stroke="#77786f"/>)}
    {[9,305].map(x=><g key={x}><rect x={x} y="54" width="106" height="108" fill="#202222"/><path d={`M${x+20} 61h66l15 16v66l-15 13h-66l-15-13V77z`} fill="#151717" stroke="#b6b4a6" strokeWidth="4"/>{Array.from({length:12},(_,i)=><path key={i} d={`M${x+19} ${79+i*6}h68`} stroke="#3f4140" strokeWidth="2"/>)}<circle cx={x+53} cy="112" r="34" stroke="#333635" strokeWidth="1" fill="none"/></g>)}
    <rect x="120" y="54" width="180" height="21" fill="#161817"/>
    <text x="128" y="68" fontSize="12" fontWeight="bold" fill="#dfd9c8">ВЕСНА</text><text x="292" y="68" fontSize="12" fontWeight="bold" textAnchor="end" fill="#dfd9c8">212 С-4</text>
    <rect x="120" y="80" width="99" height="60" rx="2" fill="#353937" stroke="#797b72"/>
    <rect x="128" y="93" width="83" height="27" fill="#171a19" stroke="#5a605a"/>
    <rect x="139" y="98" width="61" height="15" fill="#9b9788"/>{[148,190].map(x=><circle key={x} cx={x} cy="105" r="5" fill="#262a28" stroke="#ded6bc"/>)}
    {[227,264].map(x=><g key={x}><rect x={x} y="87" width="31" height="20" rx="1" fill="#e4d2a4" stroke="#969080"/><path d={`M${x+5} 100q11-14 21 0M${x+15} 104l-6-12`} fill="none" stroke="#543c2b"/><circle cx={x+15} cy="128" r="10" fill="#141716" stroke="#a3a096"/><path d={`M${x+15} 121v5`} stroke="#ddd7c6" strokeWidth="2"/></g>)}
    <rect x="120" y="145" width="180" height="14" fill="#171918"/><circle cx="290" cy="152" r="3" fill="#65b65b"/><text x="126" y="155" fontSize="6" fill="#c1c0b6">СТЕРЕО · КАССЕТНЫЙ МАГНИТОФОН</text>
  </svg>;
}
