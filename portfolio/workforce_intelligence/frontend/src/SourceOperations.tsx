import { useEffect, useId, useState, type FormEvent } from "react";
import { datasetVersion, sameGeneration, WorkforceApiError, workforceRequest, workforceWrite,
  type Dataset, type Snapshot } from "./data-api";
import { operationForms, type Action, type Input } from "./operation-forms";
import styles from "./workforce-scaffold.module.css";

type Scalar = string | number | boolean | null;
type Row = Record<string, Scalar | Record<string, Scalar>>;
type Page = Snapshot & { items: Row[]; next_offset: number | null };
type EmployeeProfile = Snapshot & {
  employee: {
    id: string; display_name: string; employment_status: string; leaving_date: string | null;
    contracts: Row[]; assignments: Row[];
  };
};
type Props = {
  dataset: Dataset;
  selectedId: string | null;
  onSaved: (message: string) => void;
  onConflict: () => void;
  onError: (error: WorkforceApiError) => void;
};
type Group = {
  id: string; title: string; description: string; section?: string; columns?: string[];
  actions: Action[]; pick?: string;
};

const groups: Group[] = [
  { id: "assignment-history", title: "Organisational assignments", description: "Transfers and progression add effective history. Look up earlier assignments in Employee profile.",
    actions: ["set_assignment"] },
  { id: "manage-vacancies", title: "Vacancies", description: "Request a vacancy, approve it, and then publish it before receiving applications.",
    section: "vacancies", columns: ["id", "title", "line_id", "status", "approved_positions", "filled_positions", "exception_reason"],
    actions: ["add_vacancy", "move_vacancy", "add_campaign"], pick: "vacancy_id" },
  { id: "manage-candidates", title: "Candidates", description: "Record applications, then screen, shortlist and record an interview outcome.",
    section: "candidates", columns: ["id", "vacancy_id", "received_on", "source_code", "status", "interview_outcome"],
    actions: ["add_application", "move_application", "record_interview"], pick: "application_id" },
  { id: "offers-checks", title: "Offers & checks", description: "Record the decision on a conditional offer, the simulated checks and a planned start.",
    section: "offers", columns: ["id", "application_id", "outcome", "check_status", "planned_start_on"],
    actions: ["add_offer", "decide_offer", "record_check", "confirm_start"], pick: "offer_id" },
  { id: "new-starters", title: "New starters", description: "An actual start creates linked employment. Use its employee ID to record probation.",
    section: "starters", columns: ["employee_id", "offer_id", "started_on", "fte", "probation"],
    actions: ["record_starter", "record_probation"], pick: "employee_id" },
  { id: "learning-pdr", title: "Learning & PDR", description: "Use stable event IDs to add or update an employee’s development records.",
    section: "learning", columns: ["id", "employee_id", "occurred_on", "kind", "activity_code", "status"],
    actions: ["record_learning", "record_pdr"], pick: "employee_id" },
  { id: "leavers", title: "Leavers", description: "Record the first inactive date. Earlier assignments and contracts remain in history.",
    section: "leavers", columns: ["employee_id", "display_name", "leaving_date", "reason"], actions: ["record_leaver"] },
  { id: "reference-data", title: "Reference data", description: "Maintain synthetic service areas, locations, roles and recruitment sources. Existing history keeps its codes.",
    section: "references", columns: ["id", "label", "kind", "active", "pay_band"],
    actions: ["set_reference", "add_establishment_line"] },
  { id: "audit-history", title: "Audit history", description: "Review the latest source changes, the request reference and the recorded values.",
    section: "audit", columns: ["occurred_at", "action", "entity_type", "entity_key", "source_channel", "correlation_id", "old_values", "new_values"],
    actions: [] },
];

export const operationalOutline: [string, string][] = [
  ["directory", "People Directory"], ["employee-profile", "Employee Profile"], ["contracts", "Contracts & FTE"],
  ...groups.map(({ id, title }): [string, string] => [id, title]),
  ["import-export", "Import / Export"],
];

const labelFor = (name: string) => name.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());

function Values({ columns, rows, identity, onPick }: {
  columns: string[]; rows: Row[]; identity?: string; onPick?: (row: Row) => void;
}) {
  if (!rows.length) return <p className={styles.message}>No records on this page.</p>;
  return <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Source records">
    <table className={styles.table}>
      <thead><tr>{columns.map((column) => <th key={column} scope="col">{labelFor(column)}</th>)}
        {onPick ? <th scope="col">Select</th> : null}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>
        {columns.map((column) => {
          const value = row[column];
          return <td key={column}>{value === null || value === undefined ? "—" :
            typeof value === "object" ? <details><summary>Values</summary>
              <dl className={styles.auditValues}>{Object.entries(value).map(([key, field]) =>
                <div key={key}><dt>{labelFor(key)}</dt><dd>{field === null ? "—" : String(field)}</dd></div>)}</dl>
            </details> : ["active", "is_substantive"].includes(column) ? value ? "Yes" : "No" : String(value)}</td>;
        })}
        {onPick ? <td><button type="button" className={styles.linkButton}
          aria-label={`Use ${row[identity ?? "id"] ?? "record"}`} onClick={() => onPick(row)}>Use record</button></td> : null}
      </tr>)}</tbody>
    </table>
  </div>;
}

export function OperationForm({ actions, defaults, dataset, onSaved, onConflict, onError }: Props & {
  actions: Action[]; defaults: Record<string, string>;
}) {
  const [action, setAction] = useState<Action>(actions[0]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [referenceOptions, setOptions] = useState<Partial<Record<NonNullable<Input["list"]>, Row[]>>>({});
  const optionsId = useId();
  const fields: Input[] = operationForms[action].fields;
  const needLines = fields.some((field) => field.list === "establishment");
  const needRefs = fields.some((field) => field.list && field.list !== "establishment");
  const { dataset_id, dataset_generation, revision } = dataset;

  useEffect(() => {
    if (!needLines && !needRefs) return;
    const controller = new AbortController();
    const load = (path: string) => workforceRequest<Page>(`operations/${path}?limit=100`, { signal: controller.signal });
    void Promise.all([needLines ? load("establishment") : null, needRefs ? load("references") : null]).then(([lines, refs]) => {
      if (controller.signal.aborted) return;
      const active = (kind: string) => refs?.items.filter((item) => item.kind === kind && item.active);
      setOptions({ establishment: lines?.items, organisation: active("organisation"), location: active("location"),
        role: active("role"), recruitment_source: active("recruitment_source") });
    }).catch((failure: unknown) => {
      if (!controller.signal.aborted && failure instanceof WorkforceApiError) {
        if ([401, 403].includes(failure.status)) onError(failure);
        else setError(failure.message);
      }
    });
    return () => controller.abort();
  }, [needLines, needRefs, dataset_id, dataset_generation, revision, onError]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const form = new FormData(event.currentTarget);
    const command: Record<string, Scalar> = { action };
    for (const field of fields) {
      const raw = String(form.get(field.name) ?? "").trim();
      if (field.optional && !raw) continue;
      command[field.name] = field.type === "boolean" ? raw === "true" : field.type === "integer" ? Number(raw) : raw;
    }
    setSaving(true);
    setError("");
    try {
      const result = await workforceWrite<Snapshot & { change: string }>("operations", "POST", {
        ...datasetVersion(dataset), revision: dataset.revision, command,
      });
      onSaved(result.change === "unchanged" ? "Already recorded. No source data changed." :
        `Saved · Dataset revision ${result.dataset.revision}. Reports reflect the updated records.`);
    } catch (failure) {
      if (failure instanceof WorkforceApiError) {
        if (failure.status === 409) { setError(failure.message); onConflict(); }
        else if ([401, 403].includes(failure.status)) onError(failure);
        else setError(failure.message);
      }
    } finally {
      setSaving(false);
    }
  }

  return <form className={styles.operationForm} onSubmit={save} aria-label={operationForms[action].label}>
    <div className={styles.filterBar}>
      {actions.length > 1 ? <label>Action<select value={action} disabled={saving}
        onChange={(event) => { setAction(event.target.value as Action); setError(""); }}>
        {actions.map((value) => <option key={value} value={value}>{operationForms[value].label}</option>)}
      </select></label> : null}
      {fields.map((field) => {
        const date = field.type === "date" || field.type === "planned-date";
        const number = field.type === "integer" || field.type === "fte" || field.type === "wte";
        const defaultValue = defaults[field.name] ?? field.initial ?? (date && !field.optional ? dataset.as_of_date : "");
        const options = field.options ?? (field.type === "boolean" ? ["true", "false"] : undefined);
        const id = `${optionsId}-${field.name}`;
        return <label key={`${action}:${field.name}:${defaultValue}`}>{field.label}
          {options ? <select name={field.name} disabled={saving} required={!field.optional}
            defaultValue={defaultValue || (field.optional ? "" : options?.[0] ?? "")}>
            {field.optional ? <option value="">—</option> : null}
            {options.map((value) => <option key={value} value={value}>
              {field.type === "boolean" ? value === "true" ? "Yes" : "No" : labelFor(value)}</option>)}
          </select> : <>
            <input name={field.name} type={date ? "date" : number ? "number" : "text"}
              defaultValue={defaultValue} disabled={saving} required={!field.optional}
              min={date ? dataset.history_start : number ? field.type === "integer" ? 1 : 0.001 : undefined}
              max={field.type === "date" ? dataset.as_of_date : number ? field.type === "fte" ? 1 : 100 : undefined}
              step={number ? field.type === "integer" ? "1" : "0.001" : undefined}
              maxLength={field.type === "id" ? 64 : 80}
              pattern={field.type === "id" ? "[a-z0-9][a-z0-9\\-]{0,63}" : undefined}
              list={field.list ? id : undefined} />
            {field.list ? <datalist id={id}>{menu(referenceOptions[field.list])}</datalist> : null}
          </>}
        </label>;
      })}
      <button type="submit" className={styles.primaryButton} disabled={saving}>
        {saving ? "Saving…" : operationForms[action].label}</button>
    </div>
    {error ? <p className={styles.errorText} role="alert">{error}</p> : null}
  </form>;
}

function menu(rows: Row[] | undefined) {
  return rows?.map((item) => <option key={String(item.id)} value={String(item.id)}>{String(item.label)}</option>);
}

function Panel({ group, ...props }: Props & { group: Group }) {
  const [expanded, setExpanded] = useState(false);
  const [offset, setOffset] = useState(0);
  const [read, setRead] = useState<{ key: string; data?: Page; error?: string } | null>(null);
  const [selected, setSelected] = useState<Row | null>(null);
  const { dataset, onError, selectedId } = props;
  const readKey = `${dataset.dataset_id}:${dataset.dataset_generation}:${dataset.revision}:${offset}`;
  const page = read?.key === readKey ? read.data : undefined;
  const error = read?.key === readKey ? read.error : undefined;

  useEffect(() => {
    if (!expanded || !group.section) return;
    const controller = new AbortController();
    void workforceRequest<Page>(`operations/${group.section}?limit=15&offset=${offset}`, { signal: controller.signal }).then((data) => {
      if (controller.signal.aborted) return;
      if (!sameGeneration(data.dataset, dataset) || data.dataset.revision !== dataset.revision) {
        setRead({ key: readKey, error: "Source records changed. Refresh data before editing." });
      } else setRead({ key: readKey, data });
    }).catch((failure: unknown) => {
      if (controller.signal.aborted || !(failure instanceof WorkforceApiError)) return;
      if ([401, 403].includes(failure.status)) onError(failure);
      else setRead({ key: readKey, error: failure.message });
    });
    return () => controller.abort();
  }, [dataset, expanded, group.section, offset, onError, readKey]);

  const defaults: Record<string, string> = {};
  if (selectedId) defaults.employee_id = selectedId;
  if (selected) {
    if (group.pick) defaults[group.pick] = String(selected[group.pick] ?? selected.id);
    for (const key of ["offer_id", "employee_id", "application_id", "vacancy_id"]) {
      if (typeof selected[key] === "string") defaults[key] = selected[key];
    }
  }
  return <details id={group.id} className={styles.panel} onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary className={styles.operationHeading}>{group.title}</summary>
    <p className={styles.message}>{group.description}</p>
    {expanded && group.section && !page && !error ? <p role="status" className={styles.message}>Loading records…</p> : null}
    {error ? <p role="alert" className={styles.errorText}>{error}</p> : null}
    {page && group.columns ? <Values columns={group.columns} rows={page.items}
      identity={group.pick} onPick={group.pick ? setSelected : undefined} /> : null}
    {page && (offset > 0 || page.next_offset !== null) ? <div className={styles.pagination}>
      <button type="button" className={styles.secondaryButton} disabled={!offset}
        onClick={() => setOffset(Math.max(0, offset - 15))}>Previous {group.title.toLowerCase()}</button>
      <button type="button" className={styles.secondaryButton} disabled={page.next_offset === null}
        onClick={() => setOffset(page.next_offset ?? offset)}>Next {group.title.toLowerCase()}</button>
    </div> : null}
    {expanded && group.actions.length ? <OperationForm {...props} actions={group.actions} defaults={defaults} /> : null}
  </details>;
}

export function EmployeeOperations(props: Props) {
  const { dataset, selectedId, onError } = props;
  const [lookup, setLookup] = useState<{ id: string; selectedId: string | null }>();
  const [expanded, setExpanded] = useState(false);
  const personId = lookup && lookup.selectedId === selectedId ? lookup.id : selectedId;
  const readKey = `${personId}:${dataset.dataset_id}:${dataset.dataset_generation}:${dataset.revision}`;
  const [read, setRead] = useState<{ key: string; data?: EmployeeProfile; error?: string } | null>(null);
  const employee = read?.key === readKey ? read.data?.employee : undefined;
  const error = read?.key === readKey ? read.error : undefined;

  useEffect(() => {
    if (!personId || !expanded) return;
    const controller = new AbortController();
    void workforceRequest<EmployeeProfile>(`employees/${encodeURIComponent(personId)}`, { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setRead({ key: readKey, data }); })
      .catch((failure: unknown) => {
        if (controller.signal.aborted || !(failure instanceof WorkforceApiError)) return;
        if ([401, 403].includes(failure.status)) onError(failure);
        else setRead({ key: readKey, error: failure.message });
      });
    return () => controller.abort();
  }, [personId, expanded, readKey, onError]);

  function find(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLookup({ id: String(new FormData(event.currentTarget).get("employee")).trim(), selectedId });
  }

  return <details className={styles.panel} id="employee-profile" onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary className={styles.operationHeading}>Employee profile</summary>
    <p className={styles.message}>Only enter fictional display names and source codes. Search by ID to find active employees or leavers.</p>
    <form className={styles.filterBar} onSubmit={find}>
      <label>Find employee by ID<input name="employee" pattern="[a-z0-9][a-z0-9\-]{0,63}" required
        maxLength={64} key={selectedId} defaultValue={selectedId ?? undefined} /></label>
      <button type="submit" className={styles.secondaryButton}>View history</button>
    </form>
    {personId && !employee && !error ? <p className={styles.message} role="status">Loading employee history…</p> : null}
    {error ? <p role="alert" className={styles.errorText}>{error}</p> : null}
    {employee ? <>
      <p className={styles.message}><strong>{employee.display_name}</strong> · {employee.id} · {employee.employment_status}
        {employee.leaving_date ? ` since ${employee.leaving_date}` : ""}</p>
      <h3>Contract history</h3>
      <Values columns={["valid_from", "valid_to", "contracted_fte", "is_substantive", "change_reason"]} rows={employee.contracts} />
      <h3>Assignment history</h3>
      <Values columns={["valid_from", "valid_to", "line_id", "organisation", "location", "role", "pay_band", "change_reason"]}
        rows={employee.assignments} />
    </> : null}
    {expanded ? <OperationForm {...props} actions={["add_employee", "edit_profile"]}
      defaults={employee ? { employee_id: employee.id, display_name: employee.display_name } : {}} /> : null}
  </details>;
}

export function SourceOperations(props: Props) {
  return <>{groups.map((group) => <Panel key={group.id} {...props} group={group} />)}</>;
}
