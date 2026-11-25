"use client";
import Link from "next/link";
import { useAccountSession } from "./account-session";
export function PreferansSiteBar() {
  const {account}=useAccountSession();
  // eslint-disable-next-line @next/next/no-img-element
  const avatar=account?.avatarUrl?<img src={account.avatarUrl} alt="" width={32} height={32}/>:null;
  return <header className="preferans-site-bar">
    <Link href="/" className="preferans-site-return brand-mark">{ "\u0412\u0435\u0440\u043d\u0443\u0442\u044c\u0441\u044f \u043d\u0430" } <span className="brand-mark__braces">{"{<}"}</span><span>ALEXTYM.COM</span></Link>
    <div id="preferans-menu-slot" className="preferans-site-menu"/>
    <div className="preferans-site-account"><button type="button" className="preferans-fullscreen" aria-label={"\u041f\u043e\u043b\u043d\u043e\u044d\u043a\u0440\u0430\u043d\u043d\u044b\u0439 \u0440\u0435\u0436\u0438\u043c"} title="Fullscreen" onClick={()=>{if(document.fullscreenElement)void document.exitFullscreen().catch(()=>undefined);else void document.documentElement.requestFullscreen?.().catch(()=>undefined);}}>⛶</button>{avatar}<span>{account?.displayName??""}</span></div>
  </header>;
}
