import { useRef, useState, type FormEvent } from "react";
import { loadFullWorkforceDataset, resetWorkforceDataset, WorkforceApiError, type Dataset } from "./data-api";
import styles from "./workforce-scaffold.module.css";

export function ResetDemo({ dataset, onReset, onConflict, onAccessError }: {
  dataset: Dataset;
  onReset: (result: Dataset) => void;
  onConflict: () => void;
  onAccessError: (error: WorkforceApiError) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const idempotencyKey = useRef<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [target, setTarget] = useState<"interview" | "full">("interview");
  const [exploratory, setExploratory] = useState(false);
  const [generationSeed, setGenerationSeed] = useState("");

  function open(next: "interview" | "full") {
    if (next !== target) idempotencyKey.current = null;
    setTarget(next);
    setError("");
    dialog.current?.showModal();
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    idempotencyKey.current ??= crypto.randomUUID();
    setSaving(true);
    setError("");
    try {
      const result = target === "interview" ? await resetWorkforceDataset(dataset, idempotencyKey.current) :
        await loadFullWorkforceDataset(dataset, idempotencyKey.current, exploratory ? "exploratory" : "controlled",
          exploratory && generationSeed !== "" ? Number(generationSeed) : undefined);
      idempotencyKey.current = null;
      dialog.current?.close();
      onReset(result.dataset);
    } catch (failure) {
      if (failure instanceof WorkforceApiError && failure.status === 409) {
        dialog.current?.close();
        onConflict();
      } else if (failure instanceof WorkforceApiError && [401, 403, 404].includes(failure.status)) {
        dialog.current?.close();
        onAccessError(failure);
      } else setError(failure instanceof WorkforceApiError ? failure.message : "The dataset could not be reset. Try again.");
    } finally { setSaving(false); }
  }

  return (
    <>
      <button type="button" className={styles.secondaryButton} onClick={() => open("full")}>Load full dataset</button>
      <button type="button" className={styles.secondaryButton} onClick={() => open("interview")}>Reset demo</button>
      <dialog ref={dialog} className={styles.dialog} aria-labelledby="reset-demo-heading"
        aria-describedby="reset-demo-description" onCancel={(event) => { if (saving) event.preventDefault(); }}>
        <form onSubmit={confirm}>
          <h2 id="reset-demo-heading">{target === "full" ? "Load the full synthetic dataset?" : "Reset the shared Workforce demo?"}</h2>
          <p id="reset-demo-description">Generation {dataset.dataset_generation} and its changes will be replaced for every Workforce member.
            {target === "full" ? " The full dataset has 4,400 synthetic employees and 36 months of history." :
              " Reset restores the original interview fixture."}</p>
          {target === "full" ? <div className={styles.filterBar}>
            <label>Generation mode<select value={exploratory ? "exploratory" : "controlled"}
              disabled={saving} onChange={(event) => {
                setExploratory(event.target.value === "exploratory"); idempotencyKey.current = null;
              }}><option value="controlled">Controlled baseline</option>
              <option value="exploratory">Exploratory</option></select></label>
            {exploratory ? <label>Seed (leave blank for a random seed)<input type="number" min="0" max="4294967295"
              step="1" disabled={saving} value={generationSeed} onChange={(event) => {
                setGenerationSeed(event.target.value); idempotencyKey.current = null;
              }} /></label> : null}
          </div> : null}
          {error ? <p role="alert" className={styles.errorText}>{error}</p> : null}
          <div className={styles.guideActions}>
            <button type="button" className={styles.secondaryButton} disabled={saving} onClick={() => dialog.current?.close()}>Cancel</button>
            <button type="submit" className={styles.primaryButton} disabled={saving}>
              {saving ? "Replacing…" : target === "full" ? "Confirm dataset replacement" : "Confirm reset"}</button>
          </div>
        </form>
      </dialog>
    </>
  );
}
