import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";
const subscribeMenuSlot = () => () => {};
const menuSlot = () => document.getElementById("preferans-menu-slot");
const serverMenuSlot = () => null;
import styles from "./preferans-table.module.css";
import type { OverlayKind } from "./presentation-model";

type Panel = "controls" | "media" | "settings";
const items: {key:Panel; label:string; icon:string}[] = [
  {key:"controls", label:"Управление игрой", icon:"☷"}, {key:"media", label:"Связь за столом", icon:"◉"},
  {key:"settings", label:"Настройки", icon:"⚙"},
];
export function ProjectSidebar({children, controls, media, settings, urgent, active, shared, copy, leave}: {
  children:ReactNode; controls:ReactNode; media:ReactNode; settings:ReactNode;
  urgent:boolean; active:boolean; shared?:(kind:OverlayKind)=>void; copy:()=>void; leave:()=>void;
}) {
  const [panel,setPanel] = useState<Panel|null>(null);
  const slot = useSyncExternalStore(subscribeMenuSlot,menuSlot,serverMenuSlot);
  useEffect(()=>{if(urgent)setPanel("controls");},[urgent]);
  const shown = panel ?? (urgent ? "controls" : null);
  const nodes = {controls,media,settings};
  const reference = (kind:"rules"|"history") => window.open(`/portfolio/preferans?view=${kind}`,"_blank","noopener,noreferrer");
  const select = (key:Panel) => {
    setPanel(old=>old===key?null:key);
  };
  const action=(icon:string,label:string,run:()=>void,expanded?:boolean)=><button type="button" className={styles.menuButton} title={label} aria-label={label} aria-expanded={expanded} onClick={run}><span aria-hidden="true" className={styles.menuIcon}>{icon}</span><span>{label}</span>{expanded!==undefined&&<span aria-hidden="true">{expanded?"⌄":"›"}</span>}</button>;
  const menu = <nav className={styles.projectMenu} data-top-menu={slot?"true":undefined} aria-label="Меню игры">
        {items.map(item=><div key={item.key}>
          {action(item.icon,item.label,()=>select(item.key),shown===item.key)}
          {shown===item.key&&<section className={styles.menuDrawer} aria-label={item.label}>{nodes[item.key]}</section>}
        </div>)}
        {shared&&action("♫","Магнитофон",()=>{setPanel(null);shared("radio");})}
        {action("↗","Скопировать приглашение",copy)}
        {action("⇥","К выбору комнаты",leave)}
        {action("▥","Правила игры",()=>reference("rules"))}
        {action("♜","История и рейтинг",()=>reference("history"))}
  </nav>;
  return <>
    {active&&<div className={styles.rotatePrompt} role="status"><span aria-hidden="true">↻</span><strong>Поверни телефон</strong><p>Игровой стол работает в горизонтальной ориентации. Комната и соединение сохраняются.</p></div>}
    <div className={`${styles.roomLayout} ${active?styles.landscapeOnly:""}`} data-top-menu={slot?"true":undefined}>
      {slot?createPortal(menu,slot):menu}
      <div className={styles.sceneColumn}>{children}</div>
    </div>
  </>;
}
