"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./workflow-settings.module.css";
import WorkflowLibraryPanel from "./WorkflowLibraryPanel";

type Item = { stage_index: number; item_key: string; label: string; required: boolean };
const STAGES = [
  "Defect Registered", "Diagnosis Scheduled", "Awaiting Quotation", "Repair Approval",
  "Repair in Progress", "Release Check", "Operations Desk Closure", "Post-Repair Documentation",
];
const ID = (item: Item) => `${item.stage_index}:${item.item_key}`;
const valid = (item: Item) => item.label.trim().length >= 3 && item.label.trim().length <= 100;

async function readItems(): Promise<Item[]> {
  const res = await fetch("/api/vor/ops/templates", { credentials: "same-origin", cache: "no-store" });
  const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return (data.items as Item[]) || [];
}

export default function WorkflowSettingsPanel() {
  const [items, setItems] = useState<Item[]>([]);
  const [saved, setSaved] = useState<Record<string, Item>>({});
  const [expanded, setExpanded] = useState<number | null>(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let live = true;
    readItems()
      .then(rows => {
        if (!live) return;
        setItems(rows);
        setSaved(Object.fromEntries(rows.map(item => [ID(item), item])));
        setLoading(false);
      })
      .catch(e => { if (live) { setError((e as Error).message); setLoading(false); } });
    return () => { live = false; };
  }, []);

  const changes = useMemo(() => items.filter(item => {
    const prev = saved[ID(item)];
    return !prev || item.label !== prev.label || item.required !== prev.required;
  }), [items, saved]);
  const change = (key: string, field: "label" | "required", value: string | boolean) => {
    setItems(old => old.map(item => ID(item) === key ? { ...item, [field]: value } : item));
    setNotice("");
  };
  const resetStage = (index: number) => {
    setItems(old => old.map(item => item.stage_index === index ? (saved[ID(item)] || item) : item));
    setError(""); setNotice("");
  };
  const saveStage = async (index: number) => {
    const changed = changes.filter(item => item.stage_index === index);
    if (!changed.length) return;
    if (changed.some(item => !valid(item))) { setError("Each checklist label must contain 3–100 characters."); return; }
    setSaving(true); setError(""); setNotice("");
    const completed: Item[] = [];
    try {
      // The existing API saves one row at a time. Preserve successful rows even if a later one fails.
      for (const item of changed) {
        const res = await fetch("/api/vor/ops/templates", {
          method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ stage_index: item.stage_index, key: item.item_key, label: item.label.trim(), required: item.required }),
        });
        const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
        completed.push({ ...item, label: item.label.trim() });
        setSaved(old => ({ ...old, [ID(item)]: { ...item, label: item.label.trim() } }));
      }
      setItems(old => old.map(item => {
        const updated = completed.find(row => ID(row) === ID(item));
        return updated || item;
      }));
      setNotice(`Stage ${index + 1} saved. Existing completed-stage history is unchanged.`);
    } catch (e) {
      setError(`Could not save all settings. ${completed.length} of ${changed.length} changes saved. ${(e as Error).message}`);
    } finally { setSaving(false); }
  };

  const requiredCount = items.filter(item => item.required).length;
  return <div className={styles.page}>
    <WorkflowLibraryPanel/>
    <header className={styles.hero}>
      <div className={styles.heroCopy}>
        <span className={styles.eyebrow}>OPERATIONS CONFIGURATION</span>
        <h2>Workflow Settings</h2>
        <p>Review each repair stage, edit its checklist labels and choose which checks are mandatory.</p>
        <p className={styles.muted}>These settings apply to future stage completions. Previously completed stages and their audit history remain unchanged.</p>
      </div>
      <div className={styles.stats} aria-label="Template summary">
        <div><strong>{STAGES.length}</strong><span>Stages</span></div>
        <div><strong>{items.length}</strong><span>Checks</span></div>
        <div><strong>{requiredCount}</strong><span>Required</span></div>
      </div>
    </header>

    {error && <p className={styles.error} role="alert">{error}</p>}
    {notice && <p className={styles.notice} role="status">{notice}</p>}
    {loading ? <p className={styles.loading}>Loading workflow settings…</p> : <section className={styles.stageList} aria-label="Workflow stages">
      {STAGES.map((name, index) => {
        const rows = items.filter(item => item.stage_index === index);
        const dirty = changes.filter(item => item.stage_index === index);
        const opened = expanded === index;
        return <article key={index} className={`${styles.stage} ${opened ? styles.open : ""}`}>
          <button type="button" className={styles.stageHeader} aria-expanded={opened} onClick={() => setExpanded(opened ? null : index)}>
            <span className={styles.number}>{String(index + 1).padStart(2, "0")}</span>
            <span className={styles.stageName}><strong>{name}</strong><small>{rows.length} checks · {rows.filter(item => item.required).length} required</small></span>
            {dirty.length > 0 && <span className={styles.unsaved}>{dirty.length} unsaved</span>}
            <span className={styles.chevron} aria-hidden="true">{opened ? "⌃" : "⌄"}</span>
          </button>
          {opened && <div className={styles.stageBody}>
            <div className={styles.columnHead}><span>Checklist item</span><span>Mandatory</span></div>
            {rows.map(item => <div className={styles.item} key={ID(item)}>
              <input className={styles.textInput} aria-label={`Label for ${name}: ${item.item_key}`} maxLength={100}
                value={item.label} onChange={e => change(ID(item), "label", e.target.value)} disabled={saving}/>
              <label className={`${styles.toggleLabel} ${item.item_key === "diagnosis_date" ? styles.locked : ""}`}>
                <input type="checkbox" checked={item.required} disabled={saving || item.item_key === "diagnosis_date"}
                  onChange={e => change(ID(item), "required", e.target.checked)}/>
                <span>{item.required ? "Required" : "Optional"}</span>
              </label>
            </div>)}
            <footer className={styles.stageFooter}>
              <span>{dirty.length ? "Review and save this stage." : "All changes saved."}</span>
              <div className={styles.footerActions}>
                <button className={styles.cancel} type="button" disabled={saving || dirty.length === 0} onClick={() => resetStage(index)}>Discard</button>
                <button className={styles.save} type="button" disabled={saving || dirty.length === 0 || dirty.some(item => !valid(item))}
                  onClick={() => void saveStage(index)}>{saving ? "Saving…" : "Save stage"}</button>
              </div>
            </footer>
          </div>}
        </article>;
      })}
    </section>}
  </div>;
}
