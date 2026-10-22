"""V2-only Fleet operations: tasks, blockers, paperwork and explicit status confirmation.

This module never imports or writes to the frozen v1 store. All records are demo data.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.services import vor_data

CHECKS = (
    ("garage_complete", "Garage confirmed repair completed"),
    ("safety_checked", "Safety and roadworthiness checks completed"),
    ("equipment_checked", "Required vehicle equipment checked"),
    ("fleet_release_approved", "Fleet release approval recorded"),
)
STAGE_ITEMS: tuple[tuple[tuple[str, str], ...], ...] = (
    (("notification_sent", "Details sent to service company"), ("response_received", "Acknowledgement received")),
    (("information_forwarded", "Defect information passed on"), ("visit_date_agreed", "Inspection date agreed"), ("diagnosis_date", "Agreed inspection date"), ("maintenance_combination_reviewed", "Combining with MOT / inspection / service checked")),
    (("inspected", "Specialist inspection completed"), ("initial_quote_received", "Initial quotation received"), ("preliminary_estimate_confirmed", "Preliminary estimate confirmed")),
    (("approval_recorded", "Repair authorised"),),
    (("work_started", "Work started"), ("repair_finished", "Work completed")),
    (("repair_verified", "Repair completion confirmed"), ("release_checked", "Release and safety checks completed")),
    (("hoth_informed", "Operations desk notified"), ("hoth_closed_confirmed", "Ticket closure confirmed")),
    (("documents_received", "Post-repair documents received"), ("documents_checked", "Documents reviewed")),
)
BLOCKER_TYPES = {"Awaiting response", "Parts", "Supplier", "Approval", "Booking", "Documents", "Other"}
DOCUMENT_TYPES = {"Repair report", "Invoice", "Work completion confirmation", "Release certificate", "Other"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _setup(db: Any) -> None:
    db.executescript("""
      CREATE TABLE IF NOT EXISTS ops_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        ticket_id TEXT NOT NULL REFERENCES tickets(id),
        title TEXT NOT NULL, owner TEXT NOT NULL, due_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','done')),
        created_at TEXT NOT NULL, completed_at TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_ops_actions_vehicle ON ops_actions(vehicle_id,status,due_at);
      CREATE TABLE IF NOT EXISTS ops_blockers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        ticket_id TEXT NOT NULL REFERENCES tickets(id),
        kind TEXT NOT NULL, detail TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','resolved')),
        created_at TEXT NOT NULL, resolved_at TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_ops_blockers_vehicle ON ops_blockers(vehicle_id,status);
      CREATE TABLE IF NOT EXISTS ops_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        ticket_id TEXT NOT NULL REFERENCES tickets(id),
        kind TEXT NOT NULL, reference TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL CHECK(status IN ('missing','received','verified')),
        recorded_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS ops_release_checks (
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        ticket_id TEXT NOT NULL REFERENCES tickets(id),
        item_key TEXT NOT NULL, checked INTEGER NOT NULL DEFAULT 0,
        recorded_at TEXT NOT NULL,
        PRIMARY KEY(ticket_id,item_key)
      );
      CREATE TABLE IF NOT EXISTS ops_stage_settings (
        stage_index INTEGER NOT NULL, item_key TEXT NOT NULL,
        label TEXT NOT NULL, required INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(stage_index,item_key)
      );
      CREATE TABLE IF NOT EXISTS ops_stage_skips (
        ticket_id TEXT NOT NULL REFERENCES tickets(id), stage_index INTEGER NOT NULL,
        actor TEXT NOT NULL, reason TEXT NOT NULL, skipped_at TEXT NOT NULL,
        PRIMARY KEY(ticket_id,stage_index)
      );
      CREATE TABLE IF NOT EXISTS ops_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        ticket_id TEXT REFERENCES tickets(id), action TEXT NOT NULL,
        actor TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_ops_audit_vehicle ON ops_audit(vehicle_id,id);
    """)
    stamp = now()
    db.executemany("""INSERT OR IGNORE INTO ops_stage_settings(stage_index,item_key,label,required,updated_at)
      VALUES(?,?,?,1,?)""", [(i, k, label, stamp) for i, items in enumerate(STAGE_ITEMS) for k,label in items])
    db.commit()


def _ticket(db: Any, vehicle_id: int, ticket_id: str) -> Any:
    record = db.execute("""SELECT t.id,t.status FROM tickets t JOIN vehicles v ON v.id=t.vehicle_id
      WHERE t.id=? AND t.vehicle_id=? AND COALESCE(v.is_archived,0)=0""", (ticket_id, vehicle_id)).fetchone()
    if not record:
        raise ValueError("Ticket / active vehicle combination not found")
    return record


def _audit(db: Any, vehicle_id: int, ticket_id: str | None, action: str, details: str, actor: str="Fleet Department") -> None:
    db.execute("INSERT INTO ops_audit(vehicle_id,ticket_id,action,actor,details,created_at) VALUES(?,?,?,?,?,?)",
               (vehicle_id,ticket_id,action,actor,details,now()))


def _rows(db: Any, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in db.execute(sql,params)]


def templates() -> dict:
    with vor_data.database() as db:
        _setup(db)
        records=_rows(db,"SELECT stage_index,item_key,label,required FROM ops_stage_settings ORDER BY stage_index,item_key")
        return {"items": [{**x,"required":bool(x["required"])} for x in records]}


def update_template(stage_index: int, key: str, label: str, required: bool) -> dict:
    if not (0<=stage_index<len(STAGE_ITEMS)) or key not in dict(STAGE_ITEMS[stage_index]):
        raise ValueError("Unknown stage checklist item")
    label=label.strip()
    if len(label)<3 or len(label)>100:
        raise ValueError("Label must contain 3–100 characters")
    # Appointment date is mandatory so an agreed visit has an actual date.
    if key=="diagnosis_date" and not required:
        raise ValueError("Agreed inspection date must remain required")
    with vor_data.database() as db:
        _setup(db)
        db.execute("UPDATE ops_stage_settings SET label=?, required=?,updated_at=? WHERE stage_index=? AND item_key=?",
                   (label,int(required),now(),stage_index,key))
        db.commit()
        return {"ok":True}


def required_keys(db: Any, stage_index: int) -> set[str]:
    _setup(db)
    return {r[0] for r in db.execute("SELECT item_key FROM ops_stage_settings WHERE stage_index=? AND required=1",(stage_index,))}


def overview() -> dict:
    with vor_data.database() as db:
        _setup(db)
        actions=_rows(db,"SELECT * FROM ops_actions WHERE status='open' ORDER BY due_at,id")
        blockers=_rows(db,"SELECT * FROM ops_blockers WHERE status='active' ORDER BY created_at")
        documents=_rows(db,"SELECT * FROM ops_documents ORDER BY id")
        release=_rows(db,"SELECT * FROM ops_release_checks WHERE checked=1")
        steps=_rows(db,"SELECT t.vehicle_id,s.ticket_id,s.step_index,s.status,s.label FROM ticket_steps s JOIN tickets t ON t.id=s.ticket_id WHERE t.status='open' ORDER BY t.opened_at DESC")
        today=date.today().isoformat()
        result:dict[str,dict]={}
        for a in actions:
            row=result.setdefault(str(a['vehicle_id']), {"actions":0,"overdue":0,"blockers":0,"documents":0,"docs_verified":0,"release_ready":False,"next_action":None,"stage_done":0,"stage_total":0})
            row['actions']+=1
            row['overdue']+=int(a['due_at'][:10]<today)
            if row['next_action'] is None: row['next_action']={"title":a['title'],"owner":a['owner'],"due_at":a['due_at']}
        for b in blockers:
            row=result.setdefault(str(b['vehicle_id']), {"actions":0,"overdue":0,"blockers":0,"documents":0,"docs_verified":0,"release_ready":False,"next_action":None,"stage_done":0,"stage_total":0})
            row['blockers']+=1
        for d in documents:
            row=result.setdefault(str(d['vehicle_id']), {"actions":0,"overdue":0,"blockers":0,"documents":0,"docs_verified":0,"release_ready":False,"next_action":None,"stage_done":0,"stage_total":0})
            row['documents']+=1
            row['docs_verified']+=int(d['status']=="verified")
        ready_tickets={r['ticket_id'] for r in release if all(any(x['ticket_id']==r['ticket_id'] and x['item_key']==key for x in release) for key,_ in CHECKS)}
        for s in steps:
            row=result.setdefault(str(s['vehicle_id']), {"actions":0,"overdue":0,"blockers":0,"documents":0,"docs_verified":0,"release_ready":False,"next_action":None,"stage_done":0,"stage_total":0})
            row['stage_total']+=1
            row['stage_done']+=int(s['status'] in ('done','skipped'))
            row['release_ready']|=s['ticket_id'] in ready_tickets
            if s['status']=='current' and 'stage_current' not in row:row['stage_current']=s['label']
        return {"vehicles":result}


def queue() -> dict:
    with vor_data.database() as db:
        _setup(db)
        return {
            "actions":_rows(db,"""SELECT a.*,v.registration FROM ops_actions a JOIN vehicles v ON v.id=a.vehicle_id
                WHERE a.status='open' AND COALESCE(v.is_archived,0)=0 ORDER BY a.due_at,a.id LIMIT 500"""),
            "blockers":_rows(db,"""SELECT b.*,v.registration FROM ops_blockers b JOIN vehicles v ON v.id=b.vehicle_id
                WHERE b.status='active' AND COALESCE(v.is_archived,0)=0 ORDER BY b.created_at,b.id LIMIT 500"""),
        }


def details(vehicle_id: int, ticket_id: str) -> dict:
    with vor_data.database() as db:
        _setup(db)
        _ticket(db,vehicle_id,ticket_id)
        return {
            "actions":_rows(db,"SELECT * FROM ops_actions WHERE ticket_id=? ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END,due_at,id",(ticket_id,)),
            "blockers":_rows(db,"SELECT * FROM ops_blockers WHERE ticket_id=? ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,id DESC",(ticket_id,)),
            "documents":_rows(db,"SELECT * FROM ops_documents WHERE ticket_id=? ORDER BY id DESC",(ticket_id,)),
            "release":_rows(db,"SELECT * FROM ops_release_checks WHERE ticket_id=?",(ticket_id,)),
            "audit":_rows(db,"SELECT action,actor,details,created_at FROM ops_audit WHERE vehicle_id=? ORDER BY id DESC LIMIT 25",(vehicle_id,)),
            "status":dict(db.execute("SELECT availability_status,registration FROM vehicles WHERE id=?",(vehicle_id,)).fetchone()),
            "skips":_rows(db,"SELECT stage_index,actor,reason,skipped_at FROM ops_stage_skips WHERE ticket_id=?",(ticket_id,)),
        }


def add_action(vehicle_id:int,ticket_id:str,title:str,owner:str,due_at:str)->dict:
    title,owner=title.strip(),owner.strip()
    if not (3<=len(title)<=220 and 2<=len(owner)<=100):raise ValueError("Action title and owner required")
    try: due=date.fromisoformat(due_at)
    except ValueError as e: raise ValueError("Invalid due date") from e
    if due.isoformat()!=due_at:raise ValueError("Invalid due date")
    with vor_data.database() as db:
        _setup(db)
        if _ticket(db,vehicle_id,ticket_id)['status']!='open':raise ValueError("Ticket is closed")
        cur=db.execute("INSERT INTO ops_actions(vehicle_id,ticket_id,title,owner,due_at,created_at) VALUES(?,?,?,?,?,?)",(vehicle_id,ticket_id,title,owner,due_at,now()))
        _audit(db,vehicle_id,ticket_id,"action_created",f"{title} · {owner} · {due_at}")
        db.commit()
        return {"id":cur.lastrowid}


def complete_action(vehicle_id:int,ticket_id:str,action_id:int)->dict:
    with vor_data.database() as db:
        _setup(db);_ticket(db,vehicle_id,ticket_id)
        row=db.execute("SELECT title,status FROM ops_actions WHERE id=? AND ticket_id=? AND vehicle_id=?",(action_id,ticket_id,vehicle_id)).fetchone()
        if not row:raise ValueError("Action not found")
        if row['status']=='done':return {"ok":True,"changed":False}
        db.execute("UPDATE ops_actions SET status='done',completed_at=? WHERE id=?",(now(),action_id))
        _audit(db,vehicle_id,ticket_id,"action_completed",row['title']);db.commit();return {"ok":True,"changed":True}


def add_blocker(vehicle_id:int,ticket_id:str,kind:str,detail:str)->dict:
    detail=detail.strip()
    if kind not in BLOCKER_TYPES or not 3<=len(detail)<=500:raise ValueError("Invalid blocker type or detail")
    with vor_data.database() as db:
        _setup(db)
        if _ticket(db,vehicle_id,ticket_id)['status']!='open':raise ValueError("Ticket is closed")
        cur=db.execute("INSERT INTO ops_blockers(vehicle_id,ticket_id,kind,detail,created_at) VALUES(?,?,?,?,?)",(vehicle_id,ticket_id,kind,detail,now()))
        _audit(db,vehicle_id,ticket_id,"blocker_added",kind+": "+detail);db.commit();return {"id":cur.lastrowid}


def resolve_blocker(vehicle_id:int,ticket_id:str,blocker_id:int)->dict:
    with vor_data.database() as db:
        _setup(db);_ticket(db,vehicle_id,ticket_id)
        row=db.execute("SELECT kind,status FROM ops_blockers WHERE id=? AND ticket_id=? AND vehicle_id=?",(blocker_id,ticket_id,vehicle_id)).fetchone()
        if not row:raise ValueError("Blocker not found")
        if row['status']=='resolved':return {"ok":True,"changed":False}
        db.execute("UPDATE ops_blockers SET status='resolved',resolved_at=? WHERE id=?",(now(),blocker_id))
        _audit(db,vehicle_id,ticket_id,"blocker_resolved",row['kind']);db.commit();return {"ok":True,"changed":True}


def add_document(vehicle_id:int,ticket_id:str,kind:str,reference:str,status:str)->dict:
    if kind not in DOCUMENT_TYPES or status not in {'missing','received','verified'}:raise ValueError("Invalid document type/status")
    if len(reference)>180:raise ValueError("Reference too long")
    with vor_data.database() as db:
        _setup(db);_ticket(db,vehicle_id,ticket_id)
        cur=db.execute("INSERT INTO ops_documents(vehicle_id,ticket_id,kind,reference,status,recorded_at) VALUES(?,?,?,?,?,?)",(vehicle_id,ticket_id,kind,reference.strip(),status,now()))
        _audit(db,vehicle_id,ticket_id,"document_recorded",f"{kind}: {status}");db.commit();return {"id":cur.lastrowid}


def update_document(vehicle_id:int,ticket_id:str,document_id:int,status:str)->dict:
    if status not in {'missing','received','verified'}:raise ValueError("Invalid document status")
    with vor_data.database() as db:
        _setup(db);_ticket(db,vehicle_id,ticket_id)
        row=db.execute("SELECT kind FROM ops_documents WHERE id=? AND vehicle_id=? AND ticket_id=?",(document_id,vehicle_id,ticket_id)).fetchone()
        if not row:raise ValueError("Document not found")
        db.execute("UPDATE ops_documents SET status=?,recorded_at=? WHERE id=?",(status,now(),document_id))
        _audit(db,vehicle_id,ticket_id,"document_status",f"{row['kind']}: {status}");db.commit();return {"ok":True}


def release_check(vehicle_id:int,ticket_id:str,key:str,checked:bool)->dict:
    if key not in dict(CHECKS):raise ValueError("Unknown release checklist item")
    with vor_data.database() as db:
        _setup(db);_ticket(db,vehicle_id,ticket_id)
        db.execute("""INSERT INTO ops_release_checks(vehicle_id,ticket_id,item_key,checked,recorded_at) VALUES(?,?,?,?,?)
          ON CONFLICT(ticket_id,item_key) DO UPDATE SET checked=excluded.checked,recorded_at=excluded.recorded_at""",
          (vehicle_id,ticket_id,key,int(checked),now()))
        _audit(db,vehicle_id,ticket_id,"release_check",f"{key}: {checked}");db.commit();return {"ok":True}


def confirm_status(vehicle_id:int,ticket_id:str,new_status:str,reason:str,confirmation:bool,override:bool=False)->dict:
    if new_status not in {'VOR','Operational'}:raise ValueError("Unsupported availability status")
    reason=reason.strip()
    if not confirmation or len(reason)<5 or len(reason)>400:raise ValueError("Explicit confirmation and reason (5–400 characters) are required")
    with vor_data.database() as db:
        _setup(db);_ticket(db,vehicle_id,ticket_id)
        row=db.execute("SELECT availability_status FROM vehicles WHERE id=?",(vehicle_id,)).fetchone()
        old=row['availability_status']
        if old==new_status:return {"ok":True,"changed":False}
        completed={r[0] for r in db.execute("SELECT item_key FROM ops_release_checks WHERE ticket_id=? AND checked=1",(ticket_id,))}
        missing={k for k,_ in CHECKS}-completed
        if new_status=='Operational' and missing and not override:
            raise ValueError("Release checklist incomplete: confirm override to proceed with manual status change")
        timestamp=now()
        db.execute("UPDATE vehicles SET availability_status=?,vor_days=CASE WHEN ?='Operational' THEN 0 ELSE vor_days END WHERE id=?",(new_status,new_status,vehicle_id))
        db.execute("""INSERT INTO vor_status_events(vehicle_id,old_status,new_status,event_kind,actor,source,reason,effective_at,recorded_at)
          VALUES (?,?,?,'manual','Fleet Department','manual confirmation',?,?,?)""",(vehicle_id,old,new_status,reason,timestamp,timestamp))
        _audit(db,vehicle_id,ticket_id,"manual_status",f"{old} → {new_status}. {reason}"+(" · checklist override" if override and missing else ""))
        db.commit()
        return {"ok":True,"changed":True,"status":new_status}


def skip_stage(vehicle_id:int,ticket_id:str,actor:str,reason:str)->dict:
    actor,reason=actor.strip(),reason.strip()
    if len(actor)<2 or len(reason)<8:raise ValueError("Actor and skip reason (min 8 characters) required")
    with vor_data.database() as db:
        _setup(db)
        if _ticket(db,vehicle_id,ticket_id)['status']!='open':raise ValueError("Ticket is closed")
        step=db.execute("SELECT step_index,label FROM ticket_steps WHERE ticket_id=? AND status='current'",(ticket_id,)).fetchone()
        if not step:raise ValueError("No active workflow step")
        idx=int(step['step_index'])
        # One transaction: never bypass the recorded stage or its audit.
        next_step=db.execute("SELECT step_index,label FROM ticket_steps WHERE ticket_id=? AND step_index>? ORDER BY step_index LIMIT 1",(ticket_id,idx)).fetchone()
        db.execute("UPDATE ticket_steps SET status='skipped' WHERE ticket_id=? AND step_index=?",(ticket_id,idx))
        if next_step:db.execute("UPDATE ticket_steps SET status='current' WHERE ticket_id=? AND step_index=?",(ticket_id,next_step['step_index']))
        db.execute("UPDATE vehicles SET workflow_current_step=?,next_action=? WHERE id=?",(next_step['step_index'] if next_step else idx+1,next_step['label'] if next_step else 'All workflow stages completed',vehicle_id))
        db.execute("INSERT INTO ops_stage_skips(ticket_id,stage_index,actor,reason,skipped_at) VALUES(?,?,?,?,?)",(ticket_id,idx,actor,reason,now()))
        _audit(db,vehicle_id,ticket_id,"stage_not_required",f"{idx+1}: {step['label']} · {reason}",actor)
        db.commit()
        return {"ok":True,"skipped_stage":idx}
