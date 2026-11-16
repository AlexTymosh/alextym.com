import { useState, type FormEvent } from "react";
import { datasetVersion, MAX_WORKBOOK_BYTES, sameGeneration, WorkforceApiError,
  workforceDownload, workforceRequest, workforceWrite, XLSX_CONTENT_TYPE, type Dataset, type Snapshot } from "./data-api";
import { displayNumber } from "./format";
import styles from "./workforce-scaffold.module.css";

type Counts = { insert: number; update: number; unchanged: number; warnings: number; invalid: number };
type Impact = { metric: string; label: string; before: number | null; after: number | null };
type Preview = Snapshot & {
  batch_id: string;
  expires_at: number;
  committed: boolean;
  counts: Counts;
  rows: Array<{ sheet: string; row: number; action: string | null;
    result: "insert" | "update" | "unchanged" | "invalid"; message: string | null; warning: string | null }>;
  impact: Impact[];
};
type Receipt = Snapshot & { batch_id: string; counts: Counts; impact: Impact[]; replayed: boolean };

export function ImportExport({ dataset, onSaved, onError }: {
  dataset: Dataset;
  onSaved: (message: string) => void;
  onError: (error: WorkforceApiError) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [working, setWorking] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const [exportKind, setExportKind] = useState("analytics");
  const obsolete = preview && (!sameGeneration(preview.dataset, dataset) || preview.dataset.revision !== dataset.revision);
  const result = receipt ?? preview;
  const reportingDates = exportKind === "analytics" || exportKind === "quality";

  async function run(apply: () => Promise<void>) {
    if (working) return;
    setWorking(true);
    setError("");
    try {
      await apply();
    } catch (failure) {
      if (failure instanceof WorkforceApiError && [401, 403].includes(failure.status)) onError(failure);
      else setError(failure instanceof Error ? failure.message : "Workbook request failed.");
    } finally {
      setWorking(false);
    }
  }

  function validate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !file.name.toLowerCase().endsWith(".xlsx") || !file.size || file.size > MAX_WORKBOOK_BYTES) {
      setError("Choose a nonempty .xlsx workbook up to 1 MiB.");
      return;
    }
    setPreview(null);
    setReceipt(null);
    setAccepted(false);
    setPage(0);
    void run(async () => {
      setPreview(await workforceRequest<Preview>("import/validate", {
        method: "POST", headers: { "Content-Type": XLSX_CONTENT_TYPE }, body: file,
      }));
    });
  }

  function commit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preview || preview.counts.invalid || !accepted || obsolete) return;
    void run(async () => {
      const result = await workforceWrite<Receipt>("import/commit", "POST", {
        ...datasetVersion(preview.dataset), batch_id: preview.batch_id, confirmed: true,
      });
      setReceipt(result);
      setPreview(null);
      setAccepted(false);
      onSaved(`Workbook confirmed · Dataset revision ${result.dataset.revision}.`);
    });
  }

  function exportReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    void run(() => workforceDownload("export", `workforce-${exportKind}.xlsx`, {
      kind: exportKind, as_of_date: fields.get("as_of_date") || undefined,
      period_start: fields.get("period_start") || undefined, vacancy_id: fields.get("vacancy_id") || undefined,
    }));
  }

  return <section id="import-export" className={styles.panel} aria-labelledby="import-export-heading">
    <h2 id="import-export-heading">Import / Export</h2>
    <p className={styles.message}>Use only synthetic records. A workbook can contain up to 500 data rows and be at most 1 MiB.
      Validation previews changes for 15 minutes. It does not save source records.</p>
    <form className={styles.filterBar} aria-label="Validate Excel workbook" onSubmit={validate}>
      <button type="button" className={styles.secondaryButton} disabled={working}
        onClick={() => void run(() => workforceDownload("import/template", "workforce-template.xlsx"))}>Download template</button>
      <label>Excel workbook<input name="workbook" type="file" accept=".xlsx" disabled={working} required
        onChange={(event) => {
          setFile(event.target.files?.[0] ?? null); setPreview(null); setReceipt(null); setAccepted(false); setError("");
        }} /></label>
      <button type="submit" className={styles.primaryButton} disabled={working || !file}>Validate workbook</button>
    </form>
    {working ? <p role="status" className={styles.message}>Working on workbook…</p> : null}
    {error ? <p role="alert" className={styles.errorText}>{error}</p> : null}
    {result ? <div className={styles.finding}>
      <h3>{receipt ? "Import receipt" : "Import preview"}</h3>
      <p role="status">{result.counts.insert} to insert · {result.counts.update} to update · {result.counts.unchanged} unchanged ·{" "}
        {result.counts.warnings} warnings · {result.counts.invalid} rejected</p>
      <p className={styles.sourceCode}>Batch {result.batch_id} ·{" "}
        {receipt ? `Committed revision ${receipt.dataset.revision}` : `Source revision ${result.dataset.revision}`}</p>
      {result.impact.length ? <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Dashboard impact">
        <table className={styles.table}><thead><tr><th scope="col">Dashboard metric</th>
          <th scope="col">Before</th><th scope="col">{receipt ? "After" : "Projected"}</th></tr></thead>
          <tbody>{result.impact.map((metric) => <tr key={metric.metric}>
            <th scope="row">{metric.label}</th>
            <td>{metric.before === null ? "—" : displayNumber(metric.before)}</td>
            <td>{metric.after === null ? "—" : displayNumber(metric.after)}</td>
          </tr>)}</tbody></table>
      </div> : null}
    </div> : null}
    {preview ? <>
      <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Validated workbook rows">
        <table className={styles.table}><thead><tr><th scope="col">Sheet and row</th><th scope="col">Action</th>
          <th scope="col">Result</th><th scope="col">Details</th></tr></thead>
          <tbody>{preview.rows.slice(page * 15, page * 15 + 15).map((row) => <tr key={`${row.sheet}:${row.row}`}>
            <th scope="row">{row.sheet} · {row.row}</th><td>{row.action?.replaceAll("_", " ") ?? "—"}</td>
            <td>{row.result}</td><td>{row.message ?? row.warning ?? "—"}</td>
          </tr>)}</tbody></table>
      </div>
      {preview.rows.length > 15 ? <div className={styles.pagination}>
        <button type="button" className={styles.secondaryButton} disabled={page === 0}
          onClick={() => setPage(page - 1)}>Previous rows</button>
        <button type="button" className={styles.secondaryButton} disabled={preview.rows.length <= (page + 1) * 15}
          onClick={() => setPage(page + 1)}>Next rows</button>
      </div> : null}
      {obsolete ? <p className={styles.errorText} role="alert">The shared dataset changed. Validate the workbook again before confirming.</p> : null}
      {preview.committed ? <p className={styles.message}>This batch was already committed.</p> : null}
      <form className={styles.filterBar} aria-label="Confirm Excel import" onSubmit={commit}>
        <button type="button" className={styles.secondaryButton} disabled={working}
          onClick={() => void run(() => workforceDownload(`import/${preview.batch_id}/errors`, "workforce-import-issues.xlsx"))}>
          Download validation report</button>
        <label className={styles.inlineCheck}><input type="checkbox" checked={accepted}
          onChange={(event) => setAccepted(event.target.checked)}
          disabled={working || Boolean(obsolete) || preview.counts.invalid > 0 || preview.committed} />
          Apply these changes to the shared demo</label>
        <button type="submit" className={styles.primaryButton}
          disabled={working || !accepted || Boolean(obsolete) || preview.counts.invalid > 0 || preview.committed}>Confirm import</button>
      </form>
    </> : null}
    <div className={styles.finding}>
      <h3>Export a report</h3>
      <form className={styles.filterBar} aria-label="Export a report" onSubmit={exportReport}>
        <label>Report<select value={exportKind} onChange={(event) => setExportKind(event.target.value)} disabled={working}>
          <option value="analytics">Filtered analytics</option><option value="metrics">Metric catalogue</option>
          <option value="quality">Data quality</option><option value="survey">Reviewed survey findings</option>
        </select></label>
        {reportingDates ? <label>As of<input type="date" name="as_of_date" min={dataset.history_start}
          max={dataset.as_of_date} disabled={working} /></label> : null}
        {exportKind === "analytics" ? <>
          <label>Period start<input type="date" name="period_start" min={dataset.history_start}
            max={dataset.as_of_date} disabled={working} /></label>
          <label>Vacancy ID (funnel only)<input name="vacancy_id" pattern="[a-z0-9][a-z0-9\-]{0,63}"
            maxLength={64} disabled={working} /></label>
        </> : null}
        <button type="submit" className={styles.secondaryButton} disabled={working}>Download workbook</button>
      </form>
    </div>
  </section>;
}
