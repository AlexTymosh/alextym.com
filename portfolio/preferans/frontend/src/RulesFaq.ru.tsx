import { Fragment, type ReactNode } from "react";
import source from "./rules-source.ru.json";
import { ruleTopics } from "./rules-faq";
import styles from "./preferans-faq.module.css";

// Render a small safe Markdown subset. Never inject HTML; all text is escaped by React.
function inline(text:string):ReactNode {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).map((part,i)=>part.startsWith("**")&&part.endsWith("**")?<strong key={i}>{part.slice(2,-2)}</strong>:part.startsWith("`")&&part.endsWith("`")?<code key={i}>{part.slice(1,-1)}</code>:part.startsWith("*")&&part.endsWith("*")?<em key={i}>{part.slice(1,-1)}</em>:<Fragment key={i}>{part}</Fragment>);
}
function answer(body:string):ReactNode {
  const blocks=body.trim().split(/\n\s*\n/).filter(Boolean);
  return blocks.map((block,index)=>{
    const lines=block.split("\n");
    if(lines.every(l=>l.trim()==="---"))return null;
    if(lines.length>=2&&lines[0].startsWith("|")&&/^\|[\s:|-]+\|$/.test(lines[1])){
      const cells=(line:string)=>line.trim().replace(/^\||\|$/g,"").split("|").map(c=>c.trim());
      const header=cells(lines[0]);
      return <div key={index} className={styles.tableWrap}><table><thead><tr>{header.map((c,i)=><th scope="col" key={i}>{inline(c)}</th>)}</tr></thead><tbody>{lines.slice(2).filter(l=>l.startsWith("|")).map((row,i)=><tr key={i}>{cells(row).map((c,j)=><td key={j}>{inline(c)}</td>)}</tr>)}</tbody></table></div>;
    }
    if(lines.every(l=>/^\s*[-*] /.test(l)))return <ul key={index}>{lines.map((l,i)=><li key={i}>{inline(l.replace(/^\s*[-*] /,""))}</li>)}</ul>;
    if(lines.every(l=>/^\s*\d+[.)] /.test(l)))return <ol key={index}>{lines.map((l,i)=><li key={i}>{inline(l.replace(/^\s*\d+[.)] /,""))}</li>)}</ol>;
    return <p key={index} className={styles.paragraph}>{inline(lines.join("\n").replace(/^> /gm,""))}</p>;
  });
}
export function RulesFaq(){
  const groups=ruleTopics(source.rules);
  const decisions=ruleTopics(source.decisions);
  return <article className={styles.faq}>
    <h1>Правила игры — вопросы и ответы</h1>
    <p>Преферанс по-запорожски. Базовые домашние правила; числовые параметры выбранного набора могут отличаться. Уточнения от 23 ноября 2026 года имеют приоритет. Все упомянутые удары — условные шуточные наказания.</p>
    {groups.map(group=><details className={styles.topic} key={group.title}><summary>{group.title}</summary><div className={styles.answers}>{answer(group.intro)}{group.questions.map(q=><details key={q.title} className={styles.question}><summary>{q.title}</summary><div className={styles.answer}>{answer(q.body)}</div></details>)}</div></details>)}
    <details className={styles.topic}><summary>Подтверждённые уточнения от 23 ноября 2026 года</summary><div className={styles.answers}>{decisions.filter(d=>d.title.startsWith("Решение")).map(d=><details key={d.title} className={styles.question}><summary>{d.title}</summary><div className={styles.answer}>{answer(d.intro)}{d.questions.map(q=><div key={q.title}><strong>{q.title}</strong>{answer(q.body)}</div>)}</div></details>)}</div></details>
  </article>;
}
