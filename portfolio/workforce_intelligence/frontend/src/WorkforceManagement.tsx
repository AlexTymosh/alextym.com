import { useState, type FormEvent } from "react";
import { changeContractFte, DIRECTORY_PAGE_SIZE, WorkforceApiError, type Directory, type Employee } from "./data-api";
import { displayNumber } from "./format";
import { ImportExport } from "./ImportExport";
import { EmployeeOperations, OperationForm, SourceOperations } from "./SourceOperations";
import styles from "./workforce-scaffold.module.css";

export function WorkforceManagement({ directory, offset, onPage, onSaved, onConflict, initialEmployee, effectiveDate, onError }: {
  directory: Directory;
  offset: number;
  onPage: (offset: number) => void;
  onSaved: (message: string) => void;
  onConflict: () => void;
  initialEmployee?: string;
  effectiveDate?: string;
  onError: (error: WorkforceApiError) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(initialEmployee ?? null);
  const selected = directory.items.find((employee) => employee.id === selectedId);
  const operations = { dataset: directory.dataset, selectedId, onSaved, onConflict, onError };
  return (
    <div className={styles.stack}>
      <section id="directory" className={styles.panel} aria-labelledby="directory-heading">
        <div className={styles.sectionHeader}>
          <div><h2 id="directory-heading">People directory</h2><p>Active synthetic employees and current contracts.</p></div>
        </div>
        {directory.items.length ? (
          <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="People directory table">
            <table className={styles.table}>
              <thead><tr><th scope="col">Name</th><th scope="col">Service area</th>
                <th scope="col">Role</th><th scope="col">FTE</th><th scope="col">Contract</th></tr></thead>
              <tbody>{directory.items.map((employee) => (
                <tr key={employee.id}>
                  <th scope="row"><button type="button" className={styles.linkButton}
                    onClick={() => {
                      setSelectedId(employee.id);
                      const profile = document.getElementById("employee-profile");
                      if (profile instanceof HTMLDetailsElement) profile.open = true;
                      profile?.scrollIntoView({ block: "nearest" });
                    }}>{employee.display_name}</button><small className={styles.sourceCode}>{employee.id}</small></th>
                  <td>{employee.organisation ?? "Unassigned"}</td>
                  <td>{employee.role ?? "—"}</td><td>{displayNumber(employee.contracted_fte)}</td>
                  <td><button type="button" className={styles.linkButton}
                    aria-label={`Edit FTE for ${employee.display_name}`} aria-controls="contracts"
                    aria-expanded={selectedId === employee.id}
                    onClick={() => {
                      setSelectedId(employee.id);
                      document.getElementById("contracts")?.scrollIntoView({ block: "nearest" });
                    }}>Edit FTE</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className={styles.message}>There are no employees on this page.</p>}
        {offset > 0 || directory.next_offset !== null ? (
          <div className={styles.pagination}>
            <button type="button" className={styles.secondaryButton} disabled={offset === 0}
              onClick={() => onPage(Math.max(0, offset - DIRECTORY_PAGE_SIZE))}>Previous</button>
            <span>{offset + 1}–{offset + directory.items.length}</span>
            <button type="button" className={styles.secondaryButton} disabled={directory.next_offset === null}
              onClick={() => onPage(directory.next_offset ?? offset)}>Next</button>
          </div>
        ) : null}
      </section>
      <EmployeeOperations {...operations} />
      <section id="contracts" className={styles.panel} aria-labelledby="contracts-heading">
        <div className={styles.sectionHeader}><h2 id="contracts-heading">Contracts & FTE</h2></div>
        {selected ? <FteForm key={selected.id} directory={directory} employee={selected}
          effectiveDate={effectiveDate} onCancel={() => setSelectedId(null)}
          onSaved={(message) => { setSelectedId(null); onSaved(message); }}
          onConflict={onConflict} onError={onError} /> :
          <p className={styles.message}>Choose Edit FTE next to an employee to record an effective-dated change.</p>}
        <details className={styles.planned}><summary>Add or change a contract period</summary>
          <OperationForm {...operations} actions={["set_contract"]}
            defaults={selectedId ? { employee_id: selectedId } : {}} />
        </details>
      </section>
      <SourceOperations {...operations} />
      <ImportExport dataset={directory.dataset} onSaved={onSaved} onError={onError} />
    </div>
  );
}

function FteForm({ directory, employee, effectiveDate, onCancel, onSaved, onConflict, onError }: {
  directory: Directory; employee: Employee; effectiveDate?: string; onCancel: () => void;
  onSaved: (message: string) => void; onConflict: () => void; onError: (error: WorkforceApiError) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { dataset } = directory;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const values = new FormData(event.currentTarget);
    const fte = String(values.get("fte"));
    if (Number(fte) === employee.contracted_fte && values.get("date") === dataset.as_of_date) {
      setError("Enter a different FTE for the current contract.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await changeContractFte(dataset, employee, String(values.get("date")), fte);
      onSaved(result.record_version === employee.record_version ? "The contract already has that FTE on the selected date." :
        `${employee.display_name} contract saved. Open Recruitment overview to see the updated metrics.`);
    } catch (failure) {
      if (failure instanceof WorkforceApiError) {
        if (failure.status === 409) onConflict();
        else if ([401, 403, 404].includes(failure.status)) onError(failure);
        else setError(failure.message);
      } else setError("The contract could not be saved. Refresh the directory and retry.");
    } finally { setSaving(false); }
  }

  return <form className={styles.editForm} aria-label={`Change FTE for ${employee.display_name}`} onSubmit={save}>
    <p><strong>{employee.display_name}</strong> · Current contract {displayNumber(employee.contracted_fte)} FTE</p>
    <div className={styles.filterBar}>
      <label>Effective date<input name="date" type="date" min={dataset.history_start} max={dataset.as_of_date}
        defaultValue={effectiveDate ?? dataset.as_of_date} required disabled={saving} /></label>
      <label>New contracted FTE<input name="fte" type="number" min="0.001" max="1" step="0.001"
        defaultValue={employee.contracted_fte} required disabled={saving} /></label>
      <button type="submit" className={styles.primaryButton} disabled={saving}>{saving ? "Saving…" : "Save FTE"}</button>
      <button type="button" className={styles.secondaryButton} onClick={onCancel} disabled={saving}>Cancel</button>
    </div>
    {error ? <p className={styles.errorText} role="alert">{error}</p> : null}
  </form>;
}
