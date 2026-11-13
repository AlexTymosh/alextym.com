# Portfolio Lab — Owner-only initial-password provisioning

**Stage:** PR #244, Firebase Identity. Development-only operator workflow. This is not the Owner dashboard, a public API, or an end-to-end invitation service.

## Why this exists

The admission gate requires a durable Firebase UID-bound identity document. Creating Firebase accounts from email alone would not grant project access and must not automatically join an existing account. This command provisions **new** email/password users with an initial credential and an expiry of 1–90 days, backed by Firestore identity metadata.

## Security boundaries

- No HTTP endpoint, signup API, automatic email, or project grant.
- An existing Firebase account causes the command to fail without changing that account.
- The Firebase user starts **disabled**. Firestore first records `status: invited`, then Auth is enabled, and finally an atomic Firestore batch activates the identity and writes an audit event.
- If a step fails, admission remains `invited`/denied, except an ambiguous network response to the final Firestore commit may have completed activation. **Do not distribute credentials until the operator reconciles this state.**
- Firestore batches atomically pair identity state changes with `portfolio_lab_invitation_events` documents. Both collections are Admin SDK only and subject to the deny-all client rules.
- No password, password hash, or reset link is stored in Firestore or printed by the CLI. The initial password is entered interactively without echo and should be delivered using a separate secure channel.
- A provisioned identity may enter the disabled-by-default Lab identity preview when enabled in a controlled test environment. **It receives zero project grants.** Project RBAC is in PR 3.

## Local test workflow

Run from the backend directory against an isolated **development** Firebase project. Keep production `PORTFOLIO_LAB_ENABLED=false`.

```powershell
$env:FIREBASE_PROJECT_ID = "<development-project-id>"
$env:PORTFOLIO_LAB_OWNER_UID = "<pinned-development-owner-uid>"
# Configure FIREBASE_SERVICE_ACCOUNT_JSON securely in ignored backend/.env,
# or use an approved Application Default Credential for this environment.

uv run python -m scripts.provision_lab_identity `
  --email test-recipient@example.test `
  --project-id $env:FIREBASE_PROJECT_ID `
  --days 30
```

Dry-run validates input and makes no Firebase calls. To explicitly execute, first set the operator gate only in this shell:

```powershell
$env:PORTFOLIO_LAB_PROVISIONING_ENABLED = "true"

uv run --env-file .env python -m scripts.provision_lab_identity `
  --email <actual-test-address> `
  --project-id $env:FIREBASE_PROJECT_ID `
  --days 30 `
  --apply

Remove-Item Env:\PORTFOLIO_LAB_PROVISIONING_ENABLED
```

The example address is a placeholder and must be replaced by an address controlled in the development environment. Never paste the password into the command line, repository, issue, or chat. The script does **not** send an invitation, create an email template, or authorize an existing social identity.

## Failure recovery

If Firestore cannot be written after account creation, the script attempts to delete the newly created, disabled Firebase user. A failed delete can leave a disabled orphan requiring manual investigation. A failure after Auth enablement can leave the durable identity `invited`; an ambiguous last Firestore commit requires a manual UID and audit check **before** giving the password to the user. Never rerun the command to overwrite an existing Firebase email/UID.

Before production release, implement self-service setup links, trusted password-change completion, idempotent reconciliation, Owner dashboard, invitation status and notification choices, comprehensive Firebase emulator tests, and real-provider smoke. This development CLI is not a substitute for those features.
