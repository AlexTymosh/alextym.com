"use client";
import { PreferansHistory } from "./PreferansHistory.ru";
import { RulesFaq } from "./RulesFaq.ru";
import styles from "./preferans-game.module.css";

export function ReferencePage({kind}: {kind:"rules"|"history"}) {
  return <main className={styles.root}>
    {kind === "history" ? <><h1>История и рейтинг</h1><PreferansHistory/></> : <RulesFaq/>}
  </main>;
}
