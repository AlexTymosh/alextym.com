# Modernization — реестр функциональных пробелов

База: main 8ad0e39, 24.11.2026. PR10–12 и PR13 A–C слиты, CI green по Owner; PR13.D и PR14.A слиты (CI green по Owner). PR14.B1 — кандидат. Реестр не меняет правил. «Проверить» означает недостаточность доказательства полного workflow; не утверждение об отсутствии всех доменных функций.

| ID | Сценарий / evidence | Статус / этап |
|---|---|---|
| G01 | `online/router.py` create_room и host guard допускают Test; ТЗ требует создание назначенным администратором. | PR11 merged: API create требует Admin/Owner; unit/API regression и фактический CI ожидаются. |
| G02 | Лобби в `PreferansGame.ru.tsx`: код комнаты, join, старт; нет подтверждения полного каталога, readiness, выбора первого сдающего и перемены мест. | PR11 merged: ограниченный каталог, возобновление по коду, профили, согласие троих для новых комнат, выбор сдающего и размера пули. PR14.B1 candidate: перестановка двух мест до старта по согласию всех троих, сброс готовности, отзыв старых seat tickets/leases, обновление профилей. Integration/UAT ожидаются. Legacy lobby без marker сохраняет прежний старт. |
| G03 | `ActionPanel` запускает новую раздачу вручную; UX-06 требует 5 с после settlement и решений. | PR12 merged: серверный deadline, freeze/resume/restart, coalesced transactional start; integration/CI/UAT ожидаются. Legacy manual start сохранён. |
| G04 | `game-model.ru.ts`, `views.py`: проверить сортировку по длине масти, persist, владение рукой, special bids, повтор widow и last trick. | PR12 merged: legal bid groups, сортировка, public-only widow/replay, winner animation. Shared replay PR13; live 3-seat UAT ожидается. |
| G05 | `controls.py` прежде объединял network pause с восстановлением vote/counter; PR10 добавляет независимые причины и lease/checkpoint. | PR10 merged, CI green по Owner. Staging/real devices и квоты отдельно не подтверждены. |
| G06 | Shared overlay, last-trick close on valid move, unanimous break ready, score sheet, radio. | PR13 A–C merged: общие объекты, независимый перерыв, пулька с текущими суммами, музыка на собственных тестовых WAV. Полный CI и real-device UAT ожидаются. |
| G07 | `online/router.py` allowlist Command не содержит полного sheet-discard / punch substitution / accidental reveal workflow. Проверить доменные функции и интеграцию. | PR12/13 по плану; terminal result immutable, pairwise rating, unanimous decisions. |
| G08 | Ruleset editor, immutable snapshots, Owner archive, history/reports. | Проверить PR11/13/14, не считать готовыми по наличию preset и history. |
| G09 | `online/media.py` и `PreferansMedia.ru.tsx`: отдельный polling и NAT/permission risks. | PR13.D candidate: адресный временный WS relay, добровольный звонок, видео у мест, ноль Firestore signalling операций в новом пути; без WS звонок отключён. CI, три устройства, NAT/браузеры и квоты требуют проверки. No recording development. |
| G10 | HTTP 503 SDK repair, production IAM, full role matrix, 6/8h quotas and real devices. | PR10 integration + PR14 acceptance; старые runbooks сохраняются. |

Ранее открытые исторические edge cases (forced-suit fallback при отсутствии масти, timer cost на распасах, выбор первого сдающего при ничьей) проверять по уже утверждённым источникам и тестам; не вводить новые правила молча. Реестр уточняется по фактическим тестам, не по предположениям.


## PR14.A — checkpoint, main eab5354

PR13.D слит; Owner сообщил о зелёном CI. G07: добавлено добровольное завершение «выбросить листик» / адресное предложение / явное принятие или отказ; технический исход фиксируется атомарно с immutable результатом и рейтингом, без расчёта незакрытой пули. Замена условных ударов и единогласное решение о раскрытии карты ещё не реализованы. G02b и G08 открыты. G10: добавлены проверяемые процедуры и offline evaluator; actual 6/8h, Firebase Emulator, hosted checks candidate и three-device UAT ожидаются.

## 2026-11-25 — final workflows candidate

- G07: disclosure and post-game choice implementation candidate; full CI and multi-client acceptance pending.
- G08: numeric versioned templates and Owner archive candidate; acceptance pending.
- G10: real provider/load evidence, CI and Owner release decision still open. See `PR14_FINAL_WORKFLOWS.ru.md`.

## PR15 — проверка обновлённого интерфейса

См. [PR15_IMMERSIVE_TABLE.ru.md](PR15_IMMERSIVE_TABLE.ru.md) — новый интерфейс, контракты и критерии приёмки. Исторические этапы сохранены. PR14.C / G10 не считаются закрытыми без фактической проверки.

### PR16 — открытые критерии приёмки

Кандидат реализации: визуальная доводка и ускорение доставки, атласная колода, темы, таймеры и вязки. Не считать закрытыми реальную проверку drag-and-drop, импорт всех 32 изображений, точность таймеров при переподключении, нагрузочные замеры и приёмку внешнего вида до подтверждения на полном checkout. Предыдущие G10 и PR14.C остаются открытыми.

## Дополнение PR17 — уточнение интерфейса стола

См. `PR17_TABLE_REFINEMENTS.ru.md`: свёрнутое меню, FAQ из правил, глобальная последняя взятка, оформление игроков и раздачи, увеличение элементов в пределах доступного экрана, компактная пулька и событийное пробуждение WebSocket. Требования по приватности, расчётам и приёмке сохраняются; визуальная и нагрузочная приёмка ещё не подтверждены.
