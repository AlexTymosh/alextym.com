# Website release verification runbook — Stage 17

**Scope:** main website only. Fleet VOR Hub is verified via compatibility CI, not refactored here. All commands are intended for the repository root unless stated otherwise.

## A. Preflight: record the release candidate

```powershell
git switch main
git pull --ff-only origin main
git rev-parse HEAD
git status --short
```

Record the candidate SHA and check that GitHub Actions CI (**project, backend, frontend, rag, docker**) and CodeQL (**actions, JavaScript/TypeScript, Python**) completed successfully for that exact SHA. A workflow passing on an older SHA is not sufficient.

## B. Local deterministic gates

From the **Stage 17 audit branch** after applying the package:

```powershell
python -m unittest discover -s scripts -p test_site_release_probe.py -v
task ci
task rag:eval:free
```

These commands run the release-probe tests, `task ci` and free RAG evals. Record the observed results in `SESSION_NOTES.md`; do not mark the release DONE. The optional Stage 17 verifier stays outside tracked source (use the downloaded package). Keep generated evidence in ignored `.tmp/release-evidence/`. None of these commands posts to public forms or requires paid network calls.

For a security dependency check, in `frontend/` run separately:

```powershell
npm audit --omit=dev --audit-level=high
```

Review output and remediate high/critical alerts; the result depends on registry connectivity. Review the backend `uv.lock` with the repository's approved advisory-scanning process and GitHub Dependabot/CodeQL alerts. CodeQL workflow success does not mean no alerts.

## C. Live read-only transport probe

This probe makes only GET requests. It never sends Chat prompts, contact forms, Telegram messages, Redis writes or tokens.

```powershell
python scripts/site_release_probe.py --site-base https://alextym.com --output .tmp/release-evidence/site-http.json
```

For a **separate, verified Render origin**, add `--backend-base https://YOUR-AUTHORIZED-RENDER-SERVICE.onrender.com` (use the actual host confirmed in Render, not an example value). Direct backend checks matter because the Vercel rewrite could fail independently.

Read the result JSON. To pass the public RAG readiness criteria, the response must show `status=ready`, `vector_db=ready`, `llm_config=configured`. HTTP 200 on `/api/health/live` alone is not enough. Record response header findings separately; missing headers require review but are not proof of exploitability.

**If network resolution fails:** record `BLOCKED` and retry from a machine with actual Internet access. Do not call a connection error a production outage.

## D. Opt-in integrated verification (credentials/cost/side effects)

Do not run these tests automatically in CI or before confirming the target and cost.

1. **Stage 11 / Upstash:** configure `RUN_UPSTASH_INTEGRATION=1`, `UPSTASH_TEST_ACK_NONPRODUCTION=YES`, and `UPSTASH_TEST_REST_URL`/`UPSTASH_TEST_REST_TOKEN` for a **dedicated non-production** Redis instance. Run `uv run --extra dev python -m pytest -q -rs tests/test_upstash_real_integration.py` from `backend/`. Never use production credentials or paste them into Chat/Git.
2. **Stage 12 / proxy:** obtain Render proxy topology, then compare observed client identity/limit isolation from two controlled clients (e.g. distinct networks), with low request counts. Do not assume `X-Forwarded-For` is trustworthy or run a rate-limit stress test on visitors.
3. **RAG:** follow `docs/rag-evals.md`: `task rag:release:predeploy`, then `task rag:release:postdeploy -- --base-url https://alextym.com` and protected metrics verification. These can call paid OpenAI/Qdrant providers; use committed public canaries and an authorized test budget. Compare before/after JSON reports with `task rag:eval:compare`; retain metadata and do not create a fabricated baseline.
4. **Contact/Telegram/Handoff:** only conduct test submissions with explicit consent and a permitted destination. Verify session creation, timeout, close/reset, delivery and non-disclosure of tokens/PII. Do not run automated live POST smoke tests to real recipients by default.
5. **Frontend:** manually verify Chat UX desktop/mobile, keyboard submit, SSE fallback, reconnect, reset and focus. A Vercel `READY` deployment does not prove browser flows work.

## E. Production provider record and sign-off

Capture `Vercel deployment ID`, `Render service ID / deploy ID`, source SHA, backend liveness/readiness, CI/CodeQL job IDs, security audits, RAG comparison and accepted risks. Render workspace selection must be explicitly confirmed by the authorized account owner before using connected account tools. Do not include provider secrets, message content or private visitor data in repo artifacts.

Only then update `docs/architecture/site-release-audit-2026-11-09.md` and `SESSION_NOTES.md` with **DONE — RELEASE SIGNED OFF**. If any gate cannot be performed, keep Stage 17 **IN PROGRESS / BLOCKED** with a named follow-up; do not report success by inference.
