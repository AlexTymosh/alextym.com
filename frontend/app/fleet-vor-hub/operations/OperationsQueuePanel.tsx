"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./queue-redesign.module.css";

type Item = {
  id: number;
  registration: string;
  vehicle_id: number;
  ticket_id: string;
  title?: string;
  owner?: string;
  due_at?: string;
  kind?: string;
  detail?: string;
  status: string;
};

type Queue = { actions: Item[]; blockers: Item[] };
type View = "actions" | "blockers";

type ActionRow = {
  registration: string;
  ticket_id: string;
  title: string;
  owner: string;
  due_at: string;
  status: string;
};

type BlockerRow = {
  registration: string;
  ticket_id: string;
  kind: string;
  detail: string;
  status: string;
};

const EXAMPLES: ActionRow[] = [
  {
    registration: "LT23 XBM",
    ticket_id: "PS000121",
    title: "Request updated quotation from service partner",
    owner: "Fleet coordinator",
    due_at: "",
    status: "Example",
  },
  {
    registration: "KY22 XDT",
    ticket_id: "PS000129",
    title: "Confirm inspection booking slot",
    owner: "Fleet planner",
    due_at: "",
    status: "Example",
  },
  {
    registration: "GX24 KLM",
    ticket_id: "PS000136",
    title: "Request diagnosis report",
    owner: "Fleet analyst",
    due_at: "",
    status: "Example",
  },
];

const BLOCKER_EXAMPLES: BlockerRow[] = [
  {
    registration: "LT23 XBM",
    ticket_id: "PS000121",
    kind: "Awaiting quote",
    detail: "Supplier has not returned a replacement-unit quotation",
    status: "Example",
  },
  {
    registration: "KY22 XDT",
    ticket_id: "PS000129",
    kind: "No booking slot",
    detail: "Next available inspection date has not been confirmed",
    status: "Example",
  },
  {
    registration: "GX24 KLM",
    ticket_id: "PS000136",
    kind: "Missing documentation",
    detail: "Post-repair report still outstanding",
    status: "Example",
  },
];

export default function OperationsQueuePanel({
  onOpenVehicle,
}: {
  onOpenVehicle: (registration: string) => void;
}) {
  const [data, setData] = useState<Queue | null>(null);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("actions");
  const [search, setSearch] = useState("");
  const [showExamples, setShowExamples] = useState(false);

  useEffect(() => {
    fetch("/api/vor/ops/queue", {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || `HTTP ${response.status}`);
        }
        setData(payload as Queue);
      })
      .catch((cause) => setError((cause as Error).message));
  }, []);

  const actions = data?.actions || [];
  const blockers = data?.blockers || [];
  const hasLiveData = actions.length + blockers.length > 0;
  const displayExamples = showExamples || (!hasLiveData && data !== null);

  const actionRows = useMemo<ActionRow[]>(
    () =>
      (displayExamples
        ? EXAMPLES
        : actions.map((item) => ({
            registration: item.registration,
            ticket_id: item.ticket_id,
            title: item.title || "Action",
            owner: item.owner || "Unassigned",
            due_at: item.due_at || "",
            status: item.status,
          })))
        .filter((item) =>
          `${item.registration} ${item.ticket_id} ${item.title} ${item.owner}`
            .toLowerCase()
            .includes(search.toLowerCase()),
        ),
    [displayExamples, actions, search],
  );

  const blockerRows = useMemo<BlockerRow[]>(
    () =>
      (displayExamples
        ? BLOCKER_EXAMPLES
        : blockers.map((item) => ({
            registration: item.registration,
            ticket_id: item.ticket_id,
            kind: item.kind || "Blocker",
            detail: item.detail || "",
            status: item.status,
          })))
        .filter((item) =>
          `${item.registration} ${item.ticket_id} ${item.kind} ${item.detail}`
            .toLowerCase()
            .includes(search.toLowerCase()),
        ),
    [displayExamples, blockers, search],
  );

  const overdue = actions.filter(
    (item) =>
      item.due_at &&
      item.due_at.slice(0, 10) < new Date().toISOString().slice(0, 10),
  ).length;

  return (
    <main className={styles.page}>
      <header className={styles.titleRow}>
        <div>
          <h2>Actions &amp; Blockers</h2>
          <p>
            Track issues, owners, deadlines and external dependencies across
            active cases.
          </p>
        </div>
        <button
          type="button"
          className={styles.exampleToggle}
          onClick={() => setShowExamples((value) => !value)}
          aria-pressed={showExamples}
        >
          {showExamples ? "Show live queue" : "View illustrative scenarios"}
        </button>
      </header>

      {error && <p role="alert" className={styles.error}>{error}</p>}

      <section className={styles.kpis} aria-label="Live operational summary">
        {[
          { name: "Open actions", count: actions.length, icon: "▣" },
          { name: "Active blockers", count: blockers.length, icon: "!" },
          { name: "Overdue actions", count: overdue, icon: "◷" },
          {
            name: "Vehicles affected",
            count: new Set([...actions, ...blockers].map((item) => item.vehicle_id)).size,
            icon: "▤",
          },
        ].map((item) => (
          <article key={item.name}>
            <span className={styles.kpiIcon}>{item.icon}</span>
            <div>
              <strong>{item.count}</strong>
              <small>{item.name}</small>
            </div>
          </article>
        ))}
      </section>

      <div className={styles.grid}>
        <section className={styles.contentCard}>
          <nav className={styles.tabs} aria-label="Operational queue views">
            <button
              type="button"
              onClick={() => setView("actions")}
              className={view === "actions" ? styles.active : ""}
            >
              Actions
            </button>
            <button
              type="button"
              onClick={() => setView("blockers")}
              className={view === "blockers" ? styles.active : ""}
            >
              Blockers
            </button>
          </nav>

          <div className={styles.searchRow}>
            <input
              aria-label="Search actions and blockers"
              placeholder="Search vehicle, ticket, action or owner…"
              value={search}
              onChange={(event: { target: { value: string } }) => setSearch(event.target.value)}
            />
            <span>
              {displayExamples
                ? "Illustrative scenarios · not stored"
                : "Live records"}
            </span>
          </div>

          {view === "actions" ? (
            <div className={styles.tableWrap}>
              <table>
                <thead>
                  <tr>
                    <th>Ticket</th>
                    <th>Vehicle</th>
                    <th>Action</th>
                    <th>Owner</th>
                    <th>Due date</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {actionRows.map((item, index) => (
                    <tr key={`${item.ticket_id}-${index}`}>
                      <td><span className={styles.ticket}>{item.ticket_id}</span></td>
                      <td>
                        <button
                          type="button"
                          disabled={displayExamples}
                          className={styles.link}
                          onClick={() => onOpenVehicle(item.registration)}
                        >
                          {item.registration}
                        </button>
                      </td>
                      <td>{item.title}</td>
                      <td>{item.owner}</td>
                      <td>{item.due_at || "—"}</td>
                      <td><span className={styles.state}>{item.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {actionRows.length === 0 && (
                <p className={styles.empty}>No matching actions.</p>
              )}
            </div>
          ) : (
            <div className={styles.tableWrap}>
              <table>
                <thead>
                  <tr>
                    <th>Ticket</th>
                    <th>Vehicle</th>
                    <th>Blocker</th>
                    <th>Details</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {blockerRows.map((item, index) => (
                    <tr key={`${item.ticket_id}-${index}`}>
                      <td><span className={styles.ticket}>{item.ticket_id}</span></td>
                      <td>
                        <button
                          type="button"
                          disabled={displayExamples}
                          className={styles.link}
                          onClick={() => onOpenVehicle(item.registration)}
                        >
                          {item.registration}
                        </button>
                      </td>
                      <td>{item.kind}</td>
                      <td>{item.detail}</td>
                      <td><span className={styles.state}>{item.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {blockerRows.length === 0 && (
                <p className={styles.empty}>No matching blockers.</p>
              )}
            </div>
          )}
        </section>

        <aside className={styles.sideCard}>
          <h3>
            Blockers <span>{displayExamples ? "examples" : blockers.length}</span>
          </h3>
          {blockerRows.slice(0, 7).map((item, index) => (
            <div className={styles.blocker} key={`${item.ticket_id}-${index}`}>
              <span className={styles.warning}>!</span>
              <div>
                <strong>{item.kind}</strong>
                <small>{item.registration} · {item.ticket_id}</small>
                <p>{item.detail}</p>
              </div>
            </div>
          ))}
          {blockerRows.length === 0 && (
            <p className={styles.empty}>No outstanding blockers.</p>
          )}
          <div className={styles.help}>
            <strong>How to manage live records</strong>
            <p>
              Select a vehicle in Issue Hub, then use Operational Control in
              the Repair Workflow panel. Example scenarios do not change SQLite.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}
