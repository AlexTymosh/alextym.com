import { useEffect, useRef, useState } from "react";
import type { CommandAction, RoomView } from "./game-model.ru";
import styles from "./preferans-game.module.css";

type Parameters = Record<string,number|number[]>;
type Policy = {counter_seconds:number;counter_multiplier:number;undo_seconds:number};
type Template = {id:string;version:number;name:string;description:string;parameters:Parameters;policy:Policy;sha256:string;snapshot_hash:string};
const labels:Record<string,string> = {pool_target:"Размер пули",regular_costs:"Стоимость 6–10",misere_cost:"Стоимость мизера",passout_costs:"Стоимость распасов 6–8",half_vist_award:"Полвиста",trick_vist_multiplier:"Множитель вистов за взятки",consolation_multiplier:"Множитель консоляции",help_vists_per_point:"Висты за помощь",surplus_vists_per_opponent:"Висты за остаток на соперника",hill_vist_numerator:"Перевод горы: числитель",hill_vist_denominator:"Перевод горы: знаменатель"};
const policyLabels:Record<keyof Policy,string>={counter_seconds:"Счётчик, сек.",counter_multiplier:"Множитель счётчика",undo_seconds:"Голосование, сек."};
const path="/api/preferans/rulesets";
const positive=(x:unknown):x is number=>typeof x==="number"&&Number.isSafeInteger(x)&&x>0;
function isTemplate(x:unknown):x is Template {
  if(!x||typeof x!=="object")return false;
  const t=x as Template;
  return typeof t.id==="string"&&(/^[a-f0-9]{32}$/.test(t.id)||t.id==="zaporizhzhia-classic")&&positive(t.version)&&typeof t.name==="string"&&typeof t.description==="string"&&typeof t.sha256==="string"&&/^[a-f0-9]{64}$/.test(t.sha256)&&typeof t.snapshot_hash==="string"&&/^[a-f0-9]{64}$/.test(t.snapshot_hash)&&!!t.parameters&&Object.keys(t.parameters).length===Object.keys(labels).length&&Object.keys(labels).every(k=>k==="regular_costs"||k==="passout_costs"?Array.isArray(t.parameters[k])&&(t.parameters[k] as number[]).length===(k==="regular_costs"?5:3)&&(t.parameters[k] as number[]).every(positive):positive(t.parameters[k]))&&!!t.policy&&Object.keys(policyLabels).every(k=>positive(t.policy[k as keyof Policy]));
}
export function RulesetEditor({view,busy,command}:{view:RoomView;busy:boolean;command:(action:CommandAction,args?:Record<string,unknown>)=>void}) {
  const [templates,setTemplates]=useState<Template[]>([]);
  const [selected,setSelected]=useState("");
  const [draft,setDraft]=useState<Template|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [canEdit,setCanEdit]=useState(false);
  const [reload,setReload]=useState(0);
  const [open,setOpen]=useState(false);
  const copyId=useRef<string|null>(null);
  const [truncated,setTruncated]=useState(false);
  const t=templates.find(x=>x.id===selected);
  useEffect(()=>{
    if(!open)return;
    const ctl=new AbortController();
    fetch(path,{credentials:"same-origin",cache:"no-store",signal:ctl.signal}).then(async r=>{if(!r.ok)throw new Error();const data=await r.json();if(!Array.isArray(data.templates)||data.templates.length>101||!data.templates.every(isTemplate)||typeof data.can_edit!=="boolean")throw new Error();if(!ctl.signal.aborted){setTemplates(data.templates);setCanEdit(data.can_edit);setTruncated(data.truncated===true);setError("");setSelected(old=>data.templates.some((x:Template)=>x.id===old)?old:data.templates[0]?.id??"");}}).catch(()=>{if(!ctl.signal.aborted)setError("Не удалось получить наборы правил.");});
    return ()=>ctl.abort();
  },[reload,open]);
  const save=async(copy:boolean)=>{
    if(!draft||!canEdit||loading)return;
    if(!copy&&(draft.id==="zaporizhzhia-classic"||!window.confirm("Создать новую версию? Уже начатые партии не изменятся.")))return;
    setLoading(true);setError("");
    if(copy&&!copyId.current)copyId.current=crypto.randomUUID().replace(/-/g,"");
    try{
      const r=await fetch(path,{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:copy?copyId.current:draft.id,expected_version:copy?0:draft.version,name:draft.name,description:draft.description,parameters:draft.parameters,policy:draft.policy})});
      if(!r.ok)throw new Error();const data=await r.json();if(!isTemplate(data.template))throw new Error();setSelected(data.template.id);copyId.current=null;setDraft(null);setReload(x=>x+1);
    }catch{setError("Не удалось сохранить. Проверь значения и обнови список перед повтором.");}finally{setLoading(false);}
  };
  const setParameter=(key:string,index:number|null,value:number)=>setDraft(old=>{
    if(!old)return old;const params={...old.parameters};if(index===null)params[key]=value;else {const list=[...(params[key] as number[])];list[index]=value;params[key]=list;}return {...old,parameters:params};
  });
  return <details className={styles.panel} onToggle={e=>setOpen(e.currentTarget.open)}><summary>Наборы правил</summary>
    {error&&<p role="alert">{error}</p>}
    {truncated&&<p>Список ограничен 100 пользовательскими наборами.</p>}
    <button type="button" disabled={loading} onClick={()=>{copyId.current=null;setDraft(null);setReload(x=>x+1);}}>Обновить список</button>
    <label className={styles.field}>Набор<select value={selected} onChange={e=>{setSelected(e.target.value);setDraft(null);}}>{templates.map(x=><option key={x.id} value={x.id}>{x.name} · v{x.version}</option>)}</select></label>
    {view.lobby_setup?.ruleset_parameters&&<div><h4>Фактический снимок комнаты</h4><p>{view.lobby_setup.ruleset_name} · v{view.lobby_setup.ruleset_version} · {view.lobby_setup.ruleset_snapshot_hash?.slice(0,12)}</p><dl>{Object.entries(view.lobby_setup.ruleset_parameters).map(([k,v])=><div key={k}><dt>{labels[k]??k}</dt><dd>{Array.isArray(v)?v.join(" / "):v}</dd></div>)}</dl><p>Счётчик: {view.controls?.policy?.counter_seconds} с · ×{view.controls?.policy?.counter_multiplier} · отмена: {view.controls?.policy?.undo_seconds} с</p></div>}
    {t&&<><p>{t.description}</p><p>Хеш снимка: {t.snapshot_hash.slice(0,12)}</p>
      <dl>{Object.entries(t.parameters).map(([k,v])=><div key={k}><dt>{labels[k]}</dt><dd>{Array.isArray(v)?v.join(" / "):v}{templates[0]&&JSON.stringify(v)!==JSON.stringify(templates[0].parameters[k])?" (отличается от базового)":""}</dd></div>)}
      {Object.entries(t.policy).map(([k,v])=><div key={k}><dt>{policyLabels[k as keyof Policy]}</dt><dd>{v}{templates[0]&&v!==templates[0].policy[k as keyof Policy]?" (отличается от базового)":""}</dd></div>)}</dl>
      {view.room_admin&&<button type="button" disabled={busy||Boolean(view.seat_swap)||loading||Number(t.parameters.pool_target)<2||Number(t.parameters.pool_target)>40||Number(t.parameters.pool_target)%2!==0} onClick={()=>command("ruleset_select",{id:t.id,version:t.version})}>Применить к комнате и сбросить готовность</button>}
      {canEdit&&<button type="button" disabled={loading} onClick={()=>{copyId.current=null;setDraft({...t,parameters:{...t.parameters},policy:{...t.policy}});}}>Редактировать / копировать шаблон</button>}
    </>}
    {draft&&canEdit&&<div className={styles.field}>
      <label>Название<input value={draft.name} maxLength={80} onChange={e=>setDraft({...draft,name:e.target.value})}/></label>
      <label>Описание<textarea value={draft.description} maxLength={240} onChange={e=>setDraft({...draft,description:e.target.value})}/></label>
      {Object.entries(draft.parameters).map(([k,v])=><fieldset key={k}><legend>{labels[k]}</legend>{(Array.isArray(v)?v:[v]).map((n,i)=><label key={i}>{Array.isArray(v)?(6+i):labels[k]}<input type="number" min={k==="pool_target"?2:1} max={k==="pool_target"?40:100} step={k==="pool_target"?2:1} value={n} onChange={e=>setParameter(k,Array.isArray(v)?i:null,Number(e.target.value))}/></label>)}</fieldset>)}
      {(Object.keys(policyLabels) as (keyof Policy)[]).map(k=><label key={k}>{policyLabels[k]}<input type="number" min={1} value={draft.policy[k]} onChange={e=>setDraft({...draft,policy:{...draft.policy,[k]:Number(e.target.value)}})}/></label>)}
      <button type="button" disabled={loading||!draft.name.trim()} onClick={()=>void save(true)}>Сохранить как шаблон</button>
      {draft.id!=="zaporizhzhia-classic"&&<button type="button" disabled={loading||!draft.name.trim()} onClick={()=>void save(false)}>Сохранить новую версию</button>}
      <button type="button" disabled={loading} onClick={()=>setDraft(null)}>Отмена</button>
    </div>}
  </details>;
}
