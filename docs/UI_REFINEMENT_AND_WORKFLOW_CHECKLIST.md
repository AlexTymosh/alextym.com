# Fleet VOR Hub — UI refinement and persisted stage checklists

## Scope

Frontend v2 only, plus new v2-only SQLite checklist endpoint. Frozen `/fleet-vor-hub-01` is not changed.

1. Remove visible references to NHS / KEY2 in v2 UI labels, status history, process design, and selected chat entries. Keep underlying stored data and existing public APIs intact.
2. **Dashboard**: Planned as **PR-07 / Milestone 6** in Session_Notes. Covers operational requirement of 25, shortfall, reason mix, mean/median/P90 repair times, outliers, daily reports and forecasting preview. Not implemented in this patch.
3. Calendar: 25% taller desktop cells (100px to 125px) and drop-downs for city/base, booked garage/partner, booking type. **Data constraint:** existing booking records have one `garage` field; the city selector uses the linked vehicle base. This is not guaranteed to be the actual booking city. A future data migration should add explicit `booking_city` and `partner_name` to bookings.
4. Defect VOR reason: required radio selection with no default. Exclude COMMS and Misfuelled from presented options.
5. Process Design: compact, muted Visio-style horizontal swimlane with movable task cards. Cards are movable **horizontally within their assigned lane**, session only, and diagram links recalculate; Reset layout restores initial positions. Roadside recovery rejoins repair. Remove duplicate eight-stage workflow reference card.
6. Workflow: move the entire repair workflow to the right of chat. Persist item-level checklist state and optional inspection date in v2 SQLite. New advance endpoint validates completion of the active stage checklist before advancing. Normal business process still requires a separate manual confirmation of vehicle availability; step completion does not change status.

## Run

From repo root after extracting zip:

```powershell
python scripts/apply_vor_ui_workflow.py
python scripts/check_vor_ui_workflow.py
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location).Path '.tmp\backend-venv'
cd backend
uv run --no-sync python -m pytest tests/test_vor_checklist.py tests/test_vor_intake.py tests/test_vor_data_foundation.py tests/test_vor_v1_isolation.py -q
cd ../frontend
npm run typecheck
npm run build
```

Restart backend after adding new router. Check that demo data remains unchanged in archived v1.

## Limitations

- Workflow step labels in older seeded scenarios may differ from the eight approved stages. Checklists currently map by step position (index 0–7), not by the original step label. Verify on a new **Standard Defect** case.
- Completed historical stages remain read-only and may not have checklist records (they predate this feature).
- The previous general `/api/vor/advance` route is retained for compatibility; the new UI uses guarded `/api/vor/checklists/advance`.
- Process diagram card repositioning is a visual demonstration, not a saved BPMN editing system or BPMN 2.0 XML export.
- Do not use sensitive work information in this public demo.
