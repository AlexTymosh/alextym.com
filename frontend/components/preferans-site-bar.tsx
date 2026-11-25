"use client";
import Link from "next/link";
import { useAccountSession } from "./account-session";
export function PreferansSiteBar() {
  const {account}=useAccountSession();
  // eslint-disable-next-line @next/next/no-img-element
  const avatar=account?.avatarUrl?<img src={account.avatarUrl} alt="" width={32} height={32}/>:null;
  return <header className="preferans-site-bar">
    <Link href="/" className="preferans-site-return">{ "\u0412\u0435\u0440\u043d\u0443\u0442\u044c\u0441\u044f \u043d\u0430" } <strong>{"{<}"} ALEXTYM.COM</strong></Link>
    <div id="preferans-menu-slot" className="preferans-site-menu"/>
    <div className="preferans-site-account">{avatar}<span>{account?.displayName??""}</span></div>
  </header>;
}
