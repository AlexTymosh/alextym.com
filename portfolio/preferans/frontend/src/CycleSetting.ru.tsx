import styles from "./preferans-game.module.css";

export function CycleSetting<T extends string>({label,value,options,onChange,disabled=false}: {
  label:string; value:T; options:readonly (readonly [T,string])[]; onChange:(value:T)=>void; disabled?:boolean;
}) {
  const index=Math.max(0,options.findIndex(([key])=>key===value));
  const move=(delta:number)=>onChange(options[(index+delta+options.length)%options.length][0]);
  return <div className={styles.cycleSetting} role="group" aria-label={label}>
    <strong>{label}</strong>
    <div><button type="button" aria-label={`${label}: предыдущий вариант`} disabled={disabled} onClick={()=>move(-1)}>‹</button>
      <span aria-live="polite">{options[index][1]}</span>
      <button type="button" aria-label={`${label}: следующий вариант`} disabled={disabled} onClick={()=>move(1)}>›</button></div>
  </div>;
}
