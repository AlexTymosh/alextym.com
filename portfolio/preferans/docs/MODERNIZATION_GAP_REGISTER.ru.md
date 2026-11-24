# Modernization — реестр функциональных пробелов

База: main 2166e10, 24.11.2026. PR10 слит (CI по сообщению Owner); PR11 кандидат. Реестр не меняет правил. «Проверить» означает недостаточность доказательства полного workflow; не утверждение об отсутствии всех доменных функций.

| ID | Сценарий / evidence | Статус / этап |
|---|---|---|
| G01 | `online/router.py` create_room и host guard допускают Test; ТЗ требует создание назначенным администратором. | PR11 кандидат: API create требует Admin/Owner; unit/API regression и фактический CI ожидаются. |
| G02 | Лобби в `PreferansGame.ru.tsx`: код комнаты, join, старт; нет подтверждения полного каталога, readiness, выбора первого сдающего и перемены мест. | PR11 кандидат: ограниченный каталог, возобновление по коду, профили, согласие троих для новых комнат, выбор сдающего и размера пули. Перестановка занятых мест требует согласованного reconnect/reissue tickets; не реализована, остаётся G02b. Legacy lobby без marker сохраняет прежний старт. |
| G03 | `ActionPanel` запускает новую раздачу вручную; UX-06 требует 5 с после settlement и решений. | Подтверждённый gap, PR12; атомарный start, pause/restart, duplicate. |
| G04 | `game-model.ru.ts`, `views.py`: проверить сортировку по длине масти, persist, владение рукой, special bids, повтор widow и last trick. | PR12; server projection, тесты всех фаз. |
| G05 | `controls.py` прежде объединял network pause с восстановлением vote/counter; PR10 добавляет независимые причины и lease/checkpoint. | PR10 merged, CI green по Owner. Staging/real devices и квоты отдельно не подтверждены. |
| G06 | Shared overlay, last-trick close on valid move, unanimous break ready, score sheet, radio. | PR13, новые actions и durable state; не подменять сервер локальными флагами. |
| G07 | `online/router.py` allowlist Command не содержит полного sheet-discard / punch substitution / accidental reveal workflow. Проверить доменные функции и интеграцию. | PR12/13 по плану; terminal result immutable, pairwise rating, unanimous decisions. |
| G08 | Ruleset editor, immutable snapshots, Owner archive, history/reports. | Проверить PR11/13/14, не считать готовыми по наличию preset и history. |
| G09 | `online/media.py` и `PreferansMedia.ru.tsx`: отдельный polling и NAT/permission risks. | PR13 live only; no recording development. |
| G10 | HTTP 503 SDK repair, production IAM, full role matrix, 6/8h quotas and real devices. | PR10 integration + PR14 acceptance; старые runbooks сохраняются. |

Ранее открытые исторические edge cases (forced-suit fallback при отсутствии масти, timer cost на распасах, выбор первого сдающего при ничьей) проверять по уже утверждённым источникам и тестам; не вводить новые правила молча. Реестр уточняется по фактическим тестам, не по предположениям.
