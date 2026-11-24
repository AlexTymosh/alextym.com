# PR13.D — живая связь, отдельный PR после A–C

База `8ad0e39421ae68194fd225240b4b9936b6df54a7`. Owner подтвердил green CI и merge A–C. Ветка `feat/preferans-live-media`. Видеозапись исключена по ранее утверждённому решению. Не менять правила игры, расчёты, общие объекты, профили, Firebase IAM, billing, общий сайт.

## Решение и границы

Новый live-only mesh использует тот же аутентифицированный WebSocket комнаты, одноразовые tickets, existing Origin/grant/seat checks и periodic revalidation. HTTP остается единственным каналом игровых мутаций. `live_relay.py` хранится в process-local `Room` existing hub; нет второго backend service, SDK, Firestore document, media operation, дополнительного HTTP polling или записи аудио/видео. Видеопотоки и звук — direct browser WebRTC; используется тот же public STUN, что в legacy. NAT, корпоративные сети, браузер/разрешения могут не позволить соединение без TURN. Это добровольная опция, игра независимо доступна. Не подключать платный TURN, не обещать доступность во всех сетях. WebRTC может раскрывать IP-адрес собеседнику; UI сообщает об этом. В новой сцене не запускается legacy recorder; в новом server mode legacy HTTP media endpoints отклоняются до SDK. Старые данные/исходники не удаляются.

### Сигнализация

| Направление | Команда | Поля (помимо type/protocol) |
|---|---|---|
| S→C | snapshot | `live_media` capability; extra field, protocol 1 unchanged |
| C→S | media_join / media_leave | none; join explicit, новый opaque session ID; leave доступен и при rate limit |
| C→S | media_presence | audio/video: strict bool, только фактическое изменение устройств |
| C→S | media_signal | to (0..2), to_session, kind (offer/answer/ice), data |
| S→C | media_state | participants: exactly three slots, null or session/audio/video |
| S→C | media_signal | from, from_session, to_session, kind, data |
| S→C | media_error | fixed safe error, no provider payload |

Все S→C frames имеют protocol=1 и server_now_ms. `media_state` отправляется только явно присоединившимся клиентам при изменении; не меняет игровую/ledger/presentation version. SDP/ICE доставляются только выбранному действующему месту и поколению media session; from определяется из ticket, room из URL и ticket, connection из hub. Клиент не выбирает sender, UID или room в frame. Неподключившийся игрок не получает сигналы. Очереди bounded (64 на получателя, доставка до 8 за tick, TTL 15 секунд); 100 non-leave сообщений за 10 секунд на connection, frame до 16 KiB chars, SDP до 12000 chars и serialized payload bound, ICE candidate до 2048 chars. Replacement/expiry/leave prunes state and queued signals. Session IDs не credentials, не account IDs. Только protocol allowlist; no payload logging. Медиакоманды не обновляют heartbeat — он остаётся прежним, 15 секунд. Malformed media commands within size limit receive coalesced safe error; oversized/malformed transport frames may disconnect offending socket. Rate/memory limits — не гарантия против произвольного DDoS.

### Браузер

Явный вход в звонок receive-only; отдельно вручную включаются audio/video. Нижнее seat ID пары инициирует offer; два sendrecv transceiver (audio/video), attach/replaceTrack without renegotiation, serial signal/ICE processing. Incoming ICE буферизуется до remote description. До принятия нового generation старые peer/signal игнорируются. Камера запрашивает небольшое разрешение (ideal 320×240, 15 fps, max 20); браузер выбирает actual track. У аватаров реальные peer streams, когда видео включено, otherwise avatar остаётся. Собственный preview без звука; remote audio воспроизводится через отдельный элемент, при autoplay denial явная кнопка. Вызов независим от drawer, shared overlay, игры и музыки. При закрытии/замене сокета, выходе, offline/pagehide устройства прекращаются, peer connections закрываются; reconnect требует ручного join, камера/микрофон не включаются автоматически. Кнопка выхода из звонка вне landscape-only контейнера. Browser/OS suspend может задерживать обработку событий; не обещать мгновенный remote stop или невозможность сторонней записи. Auth revocation ограничена существующим 60s revalidation. При неудаче ICE — ручной leave/join, не бесконечные retries. Не использовать HTTP signalling fallback: degradation to game-only сознательно выбран для строгого £0 и исключения legacy recording path.

## Флаги и rollout (только после приёмки Owner)

Backend Render: уже существующие `PORTFOLIO_LAB_ENABLED=true`, `PREFERANS_ROOMS_ENABLED=true`, `PREFERANS_REALTIME_ENABLED=true`, `PREFERANS_REALTIME_SINGLE_WORKER=true`, точный `PREFERANS_REALTIME_ORIGINS`; подтвердить topology. Дополнительно `PREFERANS_MEDIA_ENABLED=true` и `PREFERANS_LIVE_MEDIA_WS_ENABLED=true`.
Frontend Vercel: existing realtime flags; `NEXT_PUBLIC_PREFERANS_MEDIA_ENABLED=true` и `NEXT_PUBLIC_PREFERANS_LIVE_MEDIA_WS_ENABLED=true`. Public flags требуют rebuild. Не менять flags в этом PR; по умолчанию звонок отключён. Сервер capability согласует версии: старый сервер не рекламирует, новый клиент не шлёт media frames; старый клиент игнорирует дополнительное поле и играет. Новая сцена не импортирует legacy media даже при выключенном новом flag. При rollback выключить public live flag и backend media flag (не включать старый recording path), оставить realtime игры и durable shared pauses нетронутыми. Не удалять Firestore metadata; cleanup отдельный ранее согласованный процесс. Никакого paid TTL.

## Бюджет и тесты

Предыдущий steady-state HTTP media polling при 3 участниках и интервале 6 секунд — около 10800 GET за 6 часов, минимум 21600 Firestore reads только room+media documents, без grant checks и presence writes. Новый signalling не обращается к DB сам по себе (game sync/auth reads остаются), не пересылает media bytes через Render. Это расчёт и архитектурное свойство, а не замер production. Direct mesh для 3 игроков означает по два исходящих/входящих peer streams на браузер; реальный bitrate/CPU, мобильный нагрев, quota общей системы и free-tier topology измерить отдельно.

В изолированной среде: 9 pure relay tests; ASGI test three sockets on copied exact realtime_api source plus patched local hub and stub storage; ES5/strict model and session compile. Полный checkout/CI, реальный auth/Firebase, интеграция JSX не выполнены в этой среде. Chromium blocked by local navigation policy, передача настоящих потоков не проверена. New test legacy route guard и frontend Playwright suite запустить в repo. Реальные сценарии на трёх устройствах: join without permission prompts, all pairs audio-only, video each, denial camera/mic, toggle and track ended, third leave, reconnect without automatic capture, switch room, existing game command during call, overlay/break, autoplay unlock, portrait disconnect safety, NAT failure with game continued, unauthorized access and revoked grant. Сверить actual Firestore reads/writes до/после, 6–8h PR14; не утверждать £0 UAT до измерений. G07/G08 и остальные gaps сохраняются, не объявлять полную готовность релиза.
