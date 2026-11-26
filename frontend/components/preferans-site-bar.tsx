"use client";
import Link from "next/link";
import { useAccountSession } from "./account-session";
export function PreferansSiteBar() {
  const {account}=useAccountSession();
  // eslint-disable-next-line @next/next/no-img-element
  const avatar=account?.avatarUrl?<img src={account.avatarUrl} alt="" width={32} height={32}/>:null;
  return <header className="preferans-site-bar">
    <Link href="/" className="preferans-site-return brand-mark" title="Back to homepage" aria-label="ALEXTYM.COM homepage">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ff5733" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="m3 10 9-7 9 7v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
        <path d="M9 21v-8h6v8"/>
      </svg>
      <span>ALEXTYM.COM</span>
    </Link>
    <div id="preferans-menu-slot" className="preferans-site-menu"/>
    <div className="preferans-site-account"><button type="button" className="preferans-fullscreen" aria-label={"\u041f\u043e\u043b\u043d\u043e\u044d\u043a\u0440\u0430\u043d\u043d\u044b\u0439 \u0440\u0435\u0436\u0438\u043c"} title="Fullscreen" onClick={()=>{if(document.fullscreenElement)void document.exitFullscreen().catch(()=>undefined);else void document.documentElement.requestFullscreen?.().catch(()=>undefined);}}>⛶ <span>Fullscreen</span></button><span aria-hidden="true" className="preferans-site-divider">|</span>{avatar}<span>{account?.displayName??""}</span></div>
  </header>;
}
