"""One-time, idempotent integration patch for AlexTymosh/alextym.com."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'backend' / 'app' / 'main.py'
IMPORT = 'from app.api.vor import router as vor_router'
REGISTER = '    app.include_router(vor_router, prefix="/api")'


def main() -> None:
    required = [ROOT/'frontend'/'package.json', ROOT/'backend'/'pyproject.toml',
                ROOT/'frontend'/'app'/'fleet-vor-hub'/'page.tsx',
                ROOT/'backend'/'app'/'api'/'vor.py', ROOT/'backend'/'app'/'services'/'vor_store.py']
    missing = [str(p.relative_to(ROOT)) for p in required if not p.is_file()]
    if missing:
        raise SystemExit('Files missing: '+', '.join(missing) + '\nExtract the ZIP into your alextym repository root first.')
    source = APP.read_text(encoding='utf-8')
    if IMPORT in source and REGISTER in source:
        print('Fleet VOR API already installed; nothing changed.')
        return
    marker_import='from app.api.telegram import router as telegram_router'
    marker_route='    app.include_router(telegram_router, prefix="/api")'
    if marker_import not in source or marker_route not in source:
        raise SystemExit('backend/app/main.py differs from the checked repository. No file changed. Inspect manually.')
    backup_dir = ROOT / 'backend' / '_local' / 'vor_install_backup'
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / 'main.py.before_vor'
    if not backup_file.exists():
        backup_file.write_text(source,encoding='utf-8')
    if IMPORT not in source:
        source=source.replace(marker_import,marker_import+'\n'+IMPORT,1)
    if REGISTER not in source:
        source=source.replace(marker_route,marker_route+'\n'+REGISTER,1)
    APP.write_text(source,encoding='utf-8')
    print('Installed Fleet VOR route: /api/vor/*')
    print('Backup: backend/_local/vor_install_backup/main.py.before_vor')


if __name__ == '__main__':
    main()
