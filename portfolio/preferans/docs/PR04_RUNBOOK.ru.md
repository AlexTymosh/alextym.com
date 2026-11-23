# PR 4 — runbook и проверка безопасности

1. Создать `feat/preferans-secure-rooms` из свежего `main`, на котором слит #270. Применить ZIP только после безопасного preflight.
2. В `backend/` выполнить `uv lock`, `uv sync --extra dev`; закоммитить новый `uv.lock` вместе с `pyproject.toml`, package и Dockerfile.
3. Запустить `task backend:check`, `task frontend:check`, `task ci`, проверить все пять GitHub jobs.
4. Не включать `PREFERANS_ROOMS_ENABLED` в Render/Vercel до независимого Firebase Emulator прогона и ручного UAT с тремя браузерами.
5. Проверить на прямом Render-origin: без credential → 401 или 404 при выключенном флаге; с Firebase user без гранта → 403; пользователь с View → запрещены POST; Test не читает чужую комнату; project Admin без места → не читает чужие карты; Owner без места → только публичная проекция.
6. Проверить повтор одного POST с тем же `idempotency_key`, конфликт с другим body, конкурирующие версии; отключение Render между командами; скрытый снос не появляется в `/events` или другой `/view`.
7. В PR 5 добавить UI, поллинг с экспоненциальным backoff, UX для 401/403/409/503 и три независимых контекста Playwright.

Флаги по умолчанию отключены. Тесты с FakeDB подтверждают только сериализацию, основные guards, обработку идемпотентности и projection, **не** поведение настоящего Firebase SDK в транзакционных конфликтах.
