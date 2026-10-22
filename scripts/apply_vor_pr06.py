"""Wire v2 reconciliation into Fleet VOR Hub's existing in-place navigation.

Run from any folder: python scripts/apply_vor_pr06.py
Checks all anchors before writing, supports safe re-run, does not edit frozen v1.
"""
from __future__ import annotations
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SHELL=ROOT/'frontend/app/fleet-vor-hub/FleetApp.tsx'
MAIN=ROOT/'backend/app/main.py'
NOTES=ROOT/'Session_Notes.md'
TAG='// PR06_RECONCILIATION'


def replace_one(contents: str, original: str, updated: str, description: str) -> str:
    if updated in contents:
        return contents
    if contents.count(original)!=1:
        raise RuntimeError(f'{description}: integration anchor not unique or absent ({contents.count(original)})')
    return contents.replace(original,updated,1)


def apply() -> None:
    required=[SHELL,MAIN,
        ROOT/'frontend/app/fleet-vor-hub/reconciliation/Panel.tsx',
        ROOT/'frontend/app/fleet-vor-hub/reconciliation/reconciliation.module.css',
        ROOT/'backend/app/services/vor_reconciliation.py',
        ROOT/'backend/app/api/vor_reconciliation.py',
        ROOT/'backend/app/services/vor_store_v1.py']
    for path in required:
        if not path.is_file():
            raise RuntimeError(f'Missing prerequisite: {path.relative_to(ROOT)}')
    shell=SHELL.read_text(encoding='utf-8')
    main=MAIN.read_text(encoding='utf-8')
    if TAG not in shell:
        shell=replace_one(shell, 'import styles from "./fleet-app.module.css";',
                          'import ReconciliationPanel from "./reconciliation/Panel";\nimport styles from "./fleet-app.module.css";', 'Import')
        # Extend the union without relying on exact ordering of earlier PRs.
        import re
        m=re.search(r'^type Section\s*=([^;]+);', shell,re.M)
        if not m:
            raise RuntimeError('Section type not found in FleetApp')
        shell=shell[:m.start()]+m.group(0)[:-1]+'|"reconciliation";'+shell[m.end():]
        # Reuse existing history icon for simple/reliable markup.
        anchor='{id:"process",label:"Process Design",icon:"process"},'
        shell=replace_one(shell,anchor,anchor+'\n    {id:"reconciliation",label:"Reconciliation",icon:"history"},','Menu item')
        labels_anchor='process:"Process Design",'
        shell=replace_one(shell, labels_anchor, labels_anchor+'reconciliation:"Reconciliation",','Page label')
        view_anchor='{section==="process"&&<ProcessPanel/>}'
        shell=replace_one(shell,view_anchor,view_anchor+'\n          {section==="reconciliation"&&<ReconciliationPanel/>}','Panel render')
        shell=TAG+'\n'+shell
    if 'vor_reconciliation_router' not in main:
        main=replace_one(main,'from app.api.vor import router as vor_router',
                         'from app.api.vor import router as vor_router\nfrom app.api.vor_reconciliation import router as vor_reconciliation_router',
                         'Backend router import')
        main=replace_one(main,'    app.include_router(vor_router, prefix="/api")',
                         '    app.include_router(vor_router, prefix="/api")\n    app.include_router(vor_reconciliation_router, prefix="/api")',
                         'Backend mount')
    # Writing only after every required anchor was validated.
    for path,content in [(SHELL,shell),(MAIN,main)]:
        if path.read_text(encoding='utf-8')!=content:
            path.write_text(content,encoding='utf-8',newline='\n')
            print('Updated:',path.relative_to(ROOT))
        else:
            print('Already integrated:',path.relative_to(ROOT))
    heading='### PR-06 — Reconciliation (22 October 2026)'
    if NOTES.is_file() and heading not in NOTES.read_text(encoding='utf-8'):
        with NOTES.open('a',encoding='utf-8',newline='\n') as f:
            f.write('\n'+heading+'\n\n- V2-only synthetic HOTH and Fleet snapshot imports and discrepancy queue; no external system integration.\n- Comparison runs preserve source batches and historical evidence; reviewed differences remain auditable.\n- Differences never automatically change vehicle status. Separate explicit Fleet confirmation remains authoritative.\n- CSV snapshot import, demonstration seed, optional source selection, review decisions, audit and Excel export.\n- UI remains within /fleet-vor-hub (no separate Next.js route); no visible NHS/KEY2 branding.\n- Local build/tests and browser verification required before committing.\n')
    print('PR-06 integrated. Frozen v1 not modified. Run local tests and typecheck.')


if __name__=='__main__':
    apply()
