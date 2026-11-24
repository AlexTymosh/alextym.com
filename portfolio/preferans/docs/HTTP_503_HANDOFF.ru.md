# Передача исправления HTTP 503

Ветка: `feat/preferans-release`. Commit, push и PR не выполнялись.
Диагноз, доказательства, точные IAM-права и post-deploy проверки:
[HTTP_503_FIRESTORE.ru.md](HTTP_503_FIRESTORE.ru.md).

Локально исправлено SDK-чтение и добавлены безопасные diagnostics/regressions.
Известный Render principal проверен read-only. Пользователь не уверен, какой
аккаунт в текущем Render secret: production-причина history/rankings пока не
доказана окончательно. Сначала сопоставить `client_email` либо получить новые
безопасные logs после развёртывания; IAM не менять по предположению.
Текущий статус: владелец подтвердил зелёные проверки после повторного запуска;
новые логи агент отдельно не просматривал. Прежний сетевой отказ mobile Resume
сохранён в истории расследования. Проверено агентом: backend — 1327 passed,
frontend отдельно — 444 passed; real emulators — 4 passed, local BFF — 17 checks.

## PowerShell: проверки

Из корня репозитория:

```powershell
task repo:check
task backend:check
task frontend:check
task ci
```

В отдельном терминале:

```powershell
firebase emulators:start --only auth,firestore --project demo-preferans-503 --config infra/firebase/firebase.json
```

Во втором, предназначенном только для теста терминале:

```powershell
task backend:sync
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.tmp/uv-cache'
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) '.tmp/backend-venv'
$env:PREFERANS_EMULATOR_TESTS = 'true'
$env:FIREBASE_PROJECT_ID = 'demo-preferans-503'
$env:FIREBASE_AUTH_EMULATOR_HOST = '127.0.0.1:19099'
$env:FIRESTORE_EMULATOR_HOST = '127.0.0.1:18080'
uv run --project backend python -m pytest backend/tests/test_preferans_firestore_emulators.py -q
```

Закрыть тестовый терминал после завершения. Не использовать настоящий project ID
или credentials. Эмулятор не проверяет Google Cloud IAM.

## Два тематических коммита

Команды подготовлены для владельца; агент их не выполнял.

```powershell
git add -- portfolio/preferans/backend/src/preferans/online/store.py `
  portfolio/preferans/backend/src/preferans/online/router.py `
  portfolio/preferans/tests/test_secure_rooms.py `
  portfolio/preferans/tests/test_storage_diagnostics.py `
  backend/tests/test_preferans_firestore_emulators.py
git commit -m "🐛 fix(preferans): correct Firestore transaction reads" `
  -m "Read a DocumentSnapshot through DocumentReference.get inside the transaction. Preserve atomic receipts and version checks; correct Fake semantics and cover real Auth/Firestore emulators." `
  -m "Log only safe operation, stage, exception class and request ID metadata for storage failures."

git add -- docs/deployment.md portfolio/preferans/README.md `
  portfolio/preferans/SESSION_NOTES.md portfolio/preferans/backend/README.md `
  portfolio/preferans/tests/README.md `
  portfolio/preferans/docs/HTTP_503_FIRESTORE.ru.md `
  portfolio/preferans/docs/HTTP_503_HANDOFF.ru.md
git commit -m "📝 docs(preferans): record IAM repair and verification evidence" `
  -m "Document the checked runtime account's missing query, transaction and write permissions, live read-only evidence, regression coverage and deployment acceptance steps." `
  -m "Record the Owner-confirmed green checks while preserving earlier verification evidence. Keep confirmation of the active Render principal and authenticated production recovery as deployment follow-ups."
```

## Pull Request — English

Title:

```text
🐛 Fix Preferans Firestore transaction reads
```

Body:

```markdown
Room creation treated Python Transaction.get() as a single document snapshot,
causing an AttributeError because the SDK returns an iterator. Read the document
through DocumentReference.get(transaction=..., timeout=5.0), preserving atomic
idempotency receipts, version checks and reads before writes.

Correct Fake Firestore transaction/query semantics, add real Auth/Firestore
Emulator regressions, and log only safe operation, stage, exception class and
request ID metadata. Authentication, project grants, client rules, stored data
and other portfolio modules are unchanged.

Validation:

- The Owner confirms the latest checks are green.
- Repository checks and backend checks passed: 1327 tests passed, 8 optional skips.
- Separate frontend check passed: production build and 444 tests, 50 conditional skips.
- Real Auth/Firestore Emulator integration: 4 passed; real local Next.js BFF: 17 HTTP checks.
- Guest history/ranking requests returned 401 on both production hosts.

Deployment follow-up: live read-only checks of the known Render service account
returned PermissionDenied for history/ranking queries and showed missing
query, transaction and write permissions. Confirm the account used by the
current Render secret before changing IAM. Apply only verified missing permissions
to its existing role, then verify authenticated room creation, history and rankings
after deployment. Production recovery remains unverified; this patch applies no
IAM changes or production writes. Emulators do not validate Google Cloud IAM.
```

## Squash Commit — English

```text
🐛 fix(preferans): correct Firestore reads and document required IAM permissions

Read a single document snapshot within Firestore transactions instead of
treating Transaction.get()'s iterator as a snapshot. Preserve version checks
and atomic idempotency, align Fake semantics with the SDK, and add real
Auth/Firestore Emulator coverage and privacy-safe storage diagnostics.

Document live PermissionDenied evidence, conditional Render IAM requirements
and post-deployment checks. Confirm the active Render principal before applying
IAM changes; authenticated production recovery remains a deployment follow-up.
```
