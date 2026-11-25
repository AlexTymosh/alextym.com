import { useEffect, useState, type ReactNode } from "react";
import styles from "./preferans-table.module.css";
import type { OverlayKind } from "./presentation-model";

type Panel = "score" | "controls" | "media" | "settings";
const items: {key:Panel; label:string; icon:string}[] = [
  {key:"score", label:"Пулька", icon:"▤"},
  {key:"controls", label:"Управление игрой", icon:"☷"}, {key:"media", label:"Связь за столом", icon:"◉"},
  {key:"settings", label:"Настройки", icon:"⚙"},
];
export function ProjectSidebar({children, score, controls, media, settings, urgent, active, shared, copy, leave, collapsed, onCollapse}: {
  children:ReactNode; score:ReactNode; controls:ReactNode; media:ReactNode; settings:ReactNode;
  urgent:boolean; active:boolean; shared?:(kind:OverlayKind)=>void; copy:()=>void; leave:()=>void; collapsed:boolean; onCollapse:()=>void;
}) {
  const [panel,setPanel] = useState<Panel|null>(null);
  useEffect(()=>{if(urgent)setPanel("controls");},[urgent]);
  const shown = panel ?? (urgent ? "controls" : null);
  const nodes = {score,controls,media,settings};
  const reference = (kind:"rules"|"history") => window.open(`/portfolio/preferans?view=${kind}`,"_blank","noopener,noreferrer");
  const select = (key:Panel) => {
    if (shared && key==="score") { setPanel(null); shared("score_sheet"); return; }
    setPanel(old=>old===key?null:key);
  };
  const action=(icon:string,label:string,run:()=>void,expanded?:boolean)=><button type="button" className={styles.menuButton} title={label} aria-label={label} aria-expanded={expanded} onClick={run}><span aria-hidden="true" className={styles.menuIcon}>{icon}</span>{!collapsed&&<span>{label}</span>}{expanded!==undefined&&!collapsed&&<span aria-hidden="true">{expanded?"⌄":"›"}</span>}</button>;
  return <>
    {active&&<div className={styles.rotatePrompt} role="status"><span aria-hidden="true">↻</span><strong>Поверни телефон</strong><p>Игровой стол работает в горизонтальной ориентации. Комната и соединение сохраняются.</p></div>}
    <div className={`${styles.roomLayout} ${active?styles.landscapeOnly:""}`} data-collapsed={collapsed?"true":"false"}>
      <nav className={styles.projectMenu} aria-label="Меню игры">
        <button type="button" className={styles.menuButton} onClick={onCollapse} aria-label={collapsed?"Развернуть меню":"Свернуть меню"} aria-expanded={!collapsed} title={collapsed?"Развернуть меню":"Свернуть меню"}><span aria-hidden="true" className={styles.menuIcon}>{collapsed?"›":"‹"}</span>{!collapsed&&<span>ЗА СТОЛОМ</span>}</button>
        {action("▥","Правила игры",()=>reference("rules"))}
        {action("♜","История и рейтинг",()=>reference("history"))}
        {items.map(item=><div key={item.key}>
          {action(item.icon,item.label,()=>select(item.key),shown===item.key)}
          {!collapsed&&shown===item.key&&item.key!=="score"&&<section className={styles.menuDrawer} aria-label={item.label}>{nodes[item.key]}</section>}
        </div>)}
        {shared&&action("♫","Магнитофон",()=>{setPanel(null);shared("radio");})}
        {action("↗","Скопировать приглашение",copy)}
        {action("⇥","К выбору комнаты",leave)}
      </nav>
      <div className={styles.sceneColumn}>{children}{shown==="score"&&<section className={`${styles.localDrawer} ${styles.scoreDrawer}`} role="dialog" aria-label="Пулька"><button type="button" onClick={()=>setPanel(null)}>Закрыть</button>{score}</section>}{collapsed&&shown&&shown!=="score"&&<section className={`${styles.localDrawer} ${styles.railDrawer}`} role="dialog" aria-label={items.find(item=>item.key===shown)?.label}><button type="button" onClick={()=>setPanel(null)}>Закрыть</button>{nodes[shown]}</section>}</div>
    </div>
  </>;
}
