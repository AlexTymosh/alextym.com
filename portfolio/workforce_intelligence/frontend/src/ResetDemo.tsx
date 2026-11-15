import { useRef, useState, type FormEvent } from "react";
import { resetWorkforceDataset, WorkforceApiError, type Dataset } from "./data-api";
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

  function open() {
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
      const result = await resetWorkforceDataset(dataset, idempotencyKey.current);
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
      <button type="button" className={styles.secondaryButton} onClick={open}>Reset demo</button>
      <dialog ref={dialog} className={styles.dialog} aria-labelledby="reset-demo-heading"
        aria-describedby="reset-demo-description" onCancel={(event) => { if (saving) event.preventDefault(); }}>
        <form onSubmit={confirm}>
          <h2 id="reset-demo-heading">Reset the shared Workforce demo?</h2>
          <p id="reset-demo-description">Generation {dataset.dataset_generation} and its changes will be replaced with the original synthetic interview fixture for every Workforce member.</p>
          {error ? <p role="alert" className={styles.errorText}>{error}</p> : null}
          <div className={styles.guideActions}>
            <button type="button" className={styles.secondaryButton} disabled={saving} onClick={() => dialog.current?.close()}>Cancel</button>
            <button type="submit" className={styles.primaryButton} disabled={saving}>{saving ? "Resetting…" : "Confirm reset"}</button>
          </div>
        </form>
      </dialog>
    </>
  );
}
