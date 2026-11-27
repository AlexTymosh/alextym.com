"use client";
import { useState, type FormEvent } from "react";
import { preferansAlias } from "../lib/portfolio-lab/preferans-alias";
import styles from "./lab-auth.module.css";

export function PreferansAliasEditor({uid,initial,disabled}:{uid:string;initial:string;disabled:boolean}) {
  const [value,setValue]=useState(initial);
  const [busy,setBusy]=useState(false);
  const [notice,setNotice]=useState("");
  const save=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();
    const alias=preferansAlias(value);
    if(alias===null||busy)return;
    setBusy(true);setNotice("");
    try {
      const response=await fetch("/auth/access/preferans-alias",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({uid,alias})});
      const result=await response.json().catch(()=>null);
      if(!response.ok){setNotice(result?.code==="RECENT_LOGIN_REQUIRED"?"Log In again to save the nickname.":"Could not save nickname.");return;}
      setValue(alias);setNotice(alias?"Nickname saved.":"Nickname removed.");
    }catch{setNotice("Could not save nickname.");}finally{setBusy(false);}
  };
  return <form className={styles.grantForm} onSubmit={save}>
    <label className={styles.field}><span>Preferans nickname</span><input value={value} maxLength={40} disabled={disabled||busy} onChange={e=>setValue(e.target.value)} placeholder="Account name"/></label>
    <button type="submit" className={styles.secondaryButton} disabled={disabled||busy||preferansAlias(value)===null}>Save nickname</button>
    {notice&&<p role="status" className={styles.hint}>{notice}</p>}
  </form>;
}
