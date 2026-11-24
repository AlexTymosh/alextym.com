import { useState, type ReactNode } from "react";
import styles from "./preferans-table.module.css";

type Panel = "rules" | "score" | "history" | "controls" | "last" | "media";
const labels: Record<Panel,string> = {rules:"Правила", score:"Пулька", history:"История и рейтинг", controls:"Управление",last:"Последняя взятка",media:"Связь за столом"};
export function ProjectSidebar({ children, rules, score, history, controls, last, media, urgent, active }: {
  children: ReactNode; rules: ReactNode; score: ReactNode; history: ReactNode; controls: ReactNode;
  last: ReactNode; media: ReactNode; urgent: boolean; active: boolean;
}) {
  const [panel, setPanel] = useState<Panel | null>(null);
  const [mediaVisited, setMediaVisited] = useState(false);
  const shown = urgent ? "controls" : panel;
  const nodes = {rules,score,history,controls,last,media};
  return <>
    {active && <div className={styles.rotatePrompt} role="status"><span aria-hidden="true">↻</span><strong>Поверни телефон</strong><p>Игровой стол работает в горизонтальной ориентации. Комната и соединение сохраняются.</p></div>}
    <div className={`${styles.roomLayout} ${active ? styles.landscapeOnly : ""}`}>
      <nav className={styles.projectMenu} aria-label="Меню игры">
        <span className={styles.menuTitle}>ЗА СТОЛОМ</span>
        {(Object.keys(labels) as Panel[]).map(key=><button key={key} type="button" aria-expanded={shown===key}
          onClick={()=>{if(key==="media") setMediaVisited(true); setPanel(old=>old===key?null:key);}}>{labels[key]}</button>)}
        <span className={styles.menuHint}>Музыка и общий просмотр — следующий этап.</span>
      </nav>
      <div className={styles.sceneColumn}>{children}
        {shown && shown!=="media" && <section className={styles.drawer} aria-label={labels[shown]}>{nodes[shown]}</section>}
        {mediaVisited && <section className={styles.drawer} hidden={shown!=="media"} aria-label={labels.media}>{media}</section>}
      </div>
    </div>
  </>;
}
