"""One-time safe integration for Fleet VOR Hub PR-02 (from repo root)."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
main=root/'backend/app/main.py'
store=root/'backend/app/services/vor_store.py'
ui=root/'frontend/app/fleet-vor-hub/VorHub.tsx'


def edit_once(path: Path,old: str,new: str):
    text=path.read_text(encoding='utf-8')
    if new in text:
        print(f'Already patched: {path.relative_to(root)}')
        return
    count=text.count(old)
    if count!=1:
        raise RuntimeError(f'Expected exactly one insertion point in {path.relative_to(root)}; found {count}')
    path.write_text(text.replace(old,new,1),encoding='utf-8',newline='\n')
    print(f'Updated: {path.relative_to(root)}')


def preflight():
    checks={
        main:['from app.api.vor import router as vor_router','    app.include_router(vor_router, prefix="/api")'],
        store:['SELECT * FROM vehicles ORDER BY (availability_status = \'VOR\') DESC, vor_days DESC, id'],
        ui:['<span className={styles.demoBadge}>Demo v1</span>'],
    }
    for path,items in checks.items():
        txt=path.read_text(encoding='utf-8')
        for marker in items:
            if marker not in txt and not (path==main and 'from app.api.vor_data import router as vor_data_router' in txt) and not (path==store and 'WHERE COALESCE(is_archived,0)=0' in txt) and not (path==ui and '/fleet-vor-hub/register' in txt):
                raise RuntimeError(f'Unsupported version; missing marker {marker!r} in {path}')


def main_run():
    preflight()
    edit_once(main,'from app.api.vor import router as vor_router\n',
              'from app.api.vor import router as vor_router\nfrom app.api.vor_data import router as vor_data_router\n')
    edit_once(main,'    app.include_router(vor_router, prefix="/api")\n',
              '    app.include_router(vor_router, prefix="/api")\n    app.include_router(vor_data_router, prefix="/api")\n')
    # Archived assets stay in SQLite but stop appearing in the operational workspace.
    edit_once(store,"SELECT * FROM vehicles ORDER BY (availability_status = 'VOR') DESC, vor_days DESC, id",
              "SELECT * FROM vehicles WHERE COALESCE(is_archived,0)=0 ORDER BY (availability_status = 'VOR') DESC, vor_days DESC, id")
    # Safe dashboard/backward compatibility: v2 schema must be applied before bootstrap runs.
    edit_once(store,'def snapshot() -> dict[str, Any]:\n    with connection() as db:\n',
              'def snapshot() -> dict[str, Any]:\n    from app.services import vor_data\n    with vor_data.database() as db:\n')
    edit_once(ui,'<span className={styles.demoBadge}>Demo v1</span>',
              '<a className={styles.exportButton} href="/fleet-vor-hub/register" title="Vehicle register and imports">Vehicle Register</a><span className={styles.demoBadge}>Demo v2</span>')
    notes=root/'Session_Notes.md'
    if notes.exists():
        marker='### Session 2026-10-20 — PR-02 Data Foundation'
        content=notes.read_text(encoding='utf-8')
        if marker not in content:
            with notes.open('a',encoding='utf-8',newline='\n') as f:
                f.write('\n'+marker+'\n\n')
                f.write('- **Scope:** additive v2 case/status model, CSV/XLSX import, manual asset register, archive/restore.\n')
                f.write('- **Isolation:** PR-01 frozen v1 files and SQLite remain unchanged.\n')
                f.write('- **Verification gate G1:** targeted pytest, frontend build and browser v1/v2 smoke test pending.\n')
                f.write('- **Next:** PR-03 Process Design and New Defect.\n')
            print('Updated Session_Notes.md (appended, not overwritten)')
    print('PR-02 integration complete. Frozen v1 source files were not edited.')


if __name__=='__main__':
    main_run()
