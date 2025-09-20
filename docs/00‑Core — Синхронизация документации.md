00‑Core — Синхронизация документации (v1.3.1)
Назначение. Единая «шина» правил и ссылочный пакет для двух проектов — «Ходячий рюкзак» (мобильная доставка и возвраты) и «Обмен между конфигурациями» (Core Sync 1С УТ 10.3↔11). Документ фиксирует общий стиль API, словари статусов, версионирование, источники истины (SoT), цельную ER‑модель и ворота релизов. Все продуктовые PRD/SRS ссылаются на данный документ и не дублируют его содержимое.

1. Ссылочные документы
Core‑API‑Style v1 (раздел 2 ниже)


Status‑Dictionary v1 (раздел 3)


ER Freeze v0.6.4 (раздел 4)


SoT‑Matrix v1 (раздел 5)


Release & Change Policy v1 (раздел 6)


Traceability & UAT v1 (раздел 7)



2. Core‑API‑Style v1
2.1. Базовые заголовки
- `Idempotency-Key: <uuid>` — обязателен для небезопасных операций `/api/v1/returns*` (POST/PUT/DELETE); повтор с тем же ключом возвращает исходный ответ.
- `X-Request-Id: <uuid>` — опциональный корреляционный идентификатор. При отсутствии MW генерирует значение и возвращает его в ответе.
- `Authorization: Bearer <JWT>` — обязательный заголовок авторизации; поддерживаемые роли: `1c`, `courier`, `admin`.
- `Content-Type: application/json; charset=utf-8`, `Accept: application/json`.
- Заголовок `X-Api-Version` не используется. Версионирование обеспечивается префиксом пути `/api/v1` (см. `openapi.yaml`).


2.2. Версионирование API
Семантика: v1 в URL; минорные изменения — через расширение схем (не ломающие).


Брейкинг‑изменения → v2. Депрекейт: заголовок Sunset, поле deprecation и дата снятия.


Пример deprecation‑ответа:
{
  "deprecation": {
    "sunset": "2026-03-31T00:00:00Z",
    "alternate": "/v2/instant-orders",
    "notes": "Field `payment_type` will be removed; use `tenders[]`."
  }
}

2.3. Формат ошибок
Ответы об ошибках возвращаются с `Content-Type: application/problem+json` и соответствуют RFC 7807.
Минимальный набор полей:
{
  "type": "https://api.example.com/errors/validation",
  "title": "Validation failed",
  "status": 400,
  "detail": "client_phone: must match +7XXXXXXXXXX",
  "instance": "/api/v1/instant-orders",
  "code": "validation.format",
  "errors": [{"field": "client_phone", "reason": "pattern"}]
}

`type`, `title`, `status`, `detail`, `instance` и `code` присутствуют всегда; `errors[]` используется для структурированных деталей (валидация полей, ограничения и т. п.). Корреляция ответа обеспечивается заголовком `X-Request-Id` и полем `request_id` в теле ошибки.

Таксономия кодов: `validation.*`, `auth.*`, `forbidden`, `not_found.*`, `conflict.duplicate`, `rate_limit.exceeded`, `integration.*`, `timeout.*` (см. Error Code Registry).
2.4. Пагинация и фильтры
`/api/v1/returns` поддерживает пагинацию параметрами `page` (≥ 1, по умолчанию 1) и `page_size` (1..100, по умолчанию 20). Ответ возвращает объект `PaginatedReturns` (`page`, `page_size`, `total_items`, `total_pages`, `has_next`). Дополнительные фильтры пока не реализованы.


2.5. Идемпотентность и ретраи
Повтор запроса с тем же Idempotency-Key возвращает тот же результат.


Ретраи на стороне клиента разрешены при 5xx, timeout, integration.* с экспоненциальной паузой (до 24 ч); рекомендованный график: 1 мин → 5 мин → 15 мин → 1 ч → 3 ч → 12 ч, после чего задача уходит в DLQ/ручной перезапуск.


На стороне сервера — журналирование входящих запросов в `integration_log` (поле `correlation_id`) и уникальные ключи событий в `task_event.correlation_id`. Специальная таблица `idempotency_key` пока не заведена.


2.6. Безопасность (JWT & Scopes)
Authorization: Bearer <JWT>; роли: 1c, courier, admin; скоупы: nsi.read, orders.write, returns.write, tasks.read, webhooks.sign.


Срок жизни access‑JWT: 15 мин; refresh: 7 дней; JWKS‑ротация не реже 90 дней.


Clock‑skew ≤ 30 сек.


Маскирование ПДн (телефон, адрес) в логах и integration_log.


2.7. NFR/SLA
Цель p95 ≤ 400 ms на чтение; модификации p95 ≤ 700 ms.


Доступность ≥ 99.5%/месяц.


Таймауты исходящих интеграций: 5–10 сек, с тремя ретраями.


2.8. Rate limiting & Circuit breaker
Квоты по ключу и роли: по умолчанию 600 rpm / 30 rps; бурст 2× в течение 10 сек.


При превышении: 429 Too Many Requests + заголовки X-RateLimit-*.


Circuit breaker для интеграций: порог отказов 50% за 60 сек → полуоткрытое состояние 30 сек.


2.9. Webhook Security
Подпись: X-Webhook-Signature: sha256=HEX(HMAC_SHA256(body, secret)).


Повтор доставки: до 6 попыток с backoff; дедуп по Idempotency-Key/Event-Id.


Требование времени: X-Timestamp и проверка окна ±5 мин.


2.10. Временные зоны
Все таймстемпы — UTC (RFC3339Z); клиенты передают локаль отдельно.


Среды обязаны иметь NTP‑синхронизацию.



3. Status‑Dictionary v1
Status‑Dictionary v1
 Единый словарь статусов и допустимых переходов для обоих проектов. Хранится в справочнике status_dict и используется фронтом/интеграциями.
3.1. Доставка (task / delivery_order)
 Основная цепочка: NEW → PICKING → READY → PICKED_UP → ON_ROUTE → DELIVERED → CASH_RETURNED → DONE.
 Курьер может выставлять: PICKED_UP, ON_ROUTE, DELIVERED, CASH_RETURNED, FAILED (при невыполнении SLA).
 READY/DONE/REFUSED проставляются MW/менеджером; переходы валидируются по матрице (см. API‑Contracts §7).
 Ветви:
 - FAILED — допускается из ON_ROUTE или DELIVERED (нарушение SLA, требуется ручная обработка).
 - REFUSED — допускается из READY (отказ клиента/менеджера, заказ возвращается в 1С).
 Устаревшие статусы:
 - CANCELLED — заменён на REFUSED; в status_dict помечается deprecated=true, новые интеграции его не используют.
 - NON_CASH_CONFIRMED — сверка безналичных оплат закрывается статусом DONE; значение выводится из справочника.
 - CLOSED — финальный статус объединён с DONE, исторические записи мигрируют на новый код.
 Статусы и переходы согласованы с владельцами API‑Contracts v1.1.3 (docs/API‑Contracts.md).
3.2. Instant Orders (быстрые продажи курьера)
 DRAFT → PENDING_APPROVAL → APPROVED → (DELIVERED|CANCELLED)
 Отказы: REJECTED, эскалация тайм‑аута: TIMEOUT_ESCALATED.
3.3. Возвраты (return / return_line)
 Подпроцесс: return_ready → accepted | return_rejected.
При accepted — формируется/проводится в 1С «Возврат товаров от покупателя».


При return_rejected — создаётся подзадача «Вернуть клиенту»; уведомление менеджеру и курьеру.


Для каждого статуса хранится: code, title, role_visible (courier/manager), allowed_prev, allowed_next, webhook_out (куда отправлять события), ui_chip.

4. ER Snapshot (инициализация MW)
Ключевые сущности начального релиза:
 returns, return_lines, integration_log, task_event.
 Технические нормы:
Домены/валидации: телефон +7XXXXXXXXXX; email RFC; денежные суммы numeric(12,2) + currency_code ISO‑4217.


Индексы наблюдаемости: частичные по «активным» статусам, task_events(ts) для очередей.


Внешние ключи обязательны; ON UPDATE/DELETE — по сущности.


Freeze: схема и DDL зафиксированы; изменения — только через RFC и миграции.

5. SoT‑Matrix v1 (Source of Truth)
Объект
Источник истины
Репликация/обмен
НСИ (товары, SKU, цены, совместимость)
1С
Пуш/пул через Core Sync → MW
Заказы на доставку
1С → MW
Создание в 1С, исполнение в MW/B24
Задачи курьера / события
MW
Вебхуки в B24/1С
Мгновенные продажи (рюкзак)
MW
Проведение в 1С по событию
Возвраты
MW → 1С
Мастер‑обработка в 1С по событию из MW
Денежные операции (касса/ДВП)
1С
Сверка в MW (read‑only)

Примечание: любые новые справочники сначала добавляются в SoT, затем в ER и API.

6. Release & Change Policy v1
6.1. RFC‑процесс (обязателен для Core)
 Шаблон: Problem → Change → Impact → Migration → Rollback → Owners → Timeline → Links.
 SLA рассмотрения: 2 рабочих дня.
6.2. Ворота релизов
Design‑gate: ссылка на разделы этого документа (2–5), актуальный ER Freeze, SoT‑Matrix.


Dev‑gate: OpenAPI‑контракты /v1/..., тест‑кейсы AC (Given/When/Then), миграции.


UAT‑gate: трассируемость PRD→SRS→UAT, p95 метрики, алерты, журнал интеграций.


Cutover‑gate: чек‑лист отката, readiness review, контактная карта.


6.3. Миграции и откаты
Формат MR миграции: DDL → backfill → проверки → idempotent‑скрипты → rollback‑plan.


Пример rollback: ALTER TABLE ... DROP COLUMN ... недопустим без сохранения в *_backup и плана возврата данных.


Все миграции помечаются тегом релиза и входят в ER Freeze.



7. Traceability & UAT v1
Таблица покрытия: PRD → SRS → API → UAT кейсы (по айдишникам требований).


Для каждого API‑метода — минимум 1 UAT‑кейс и 1 негативный кейс.


Логи интеграций и X-Request-Id обязательны для приёмки инцидентов.



8. Metrics & Alerts (SLO)
Ключевые метрики: p50/p95 latency по методам, error‑rate (5xx/4xx), success‑rate вебхуков, задержка интеграций (1С/B24), очередь task_events, доля ретраев.
 SLO: p95 чтение ≤ 400 ms, модификации ≤ 700 ms; error‑rate ≤ 1%; webhook delivery ≥ 99% за 15 мин.
 Алерты: превышение SLO 3× за 10 мин; рост 429 > 5% трафика; circuit‑breaker открыт > 60 сек; лаг интеграции > 5 мин.

9. Data Retention & ПДн
ПДн в логах маскируются; integration_log хранится 90 дней (агрегаты — 365).


task_event — 180 дней; integration_log — 30 дней; status_dict — бессрочно.


Экспорт/удаление ПДн по запросу — через сервисный эндпоинт (админ‑роль).


Анонимизация для аналитики: обезличивание телефонов/адресов (hash+salt).


Соответствие 152‑ФЗ: хранение ПДн в РФ, учёт согласий, назначение ответственного.



10. Environments & Feature Flags
Среда
Цель
Деплой
Данные
Фичи/флаги
DEV
разработка
auto (main)
синтетические
все флаги ON
TEST
интеграционные тесты
manual
анонимизированные
по задаче
STAGE
предпрод
manual + UAT
выборка прод‑данных (аноним.)
= PROD, кроме новых фич
PROD
боевая
manual + CAB
реальные
только разрешённые

Фичи включаются через флаг‑сервис (перекат по средам). Все тайные значения — из Secret Manager; доступ по принципу least privilege.

11. DR/BCP (Continuity)
RTO: 2 часа; RPO: 15 минут.


Резервные бэкапы БД: каждые 15 мин (WAL), ежедневные полные; еженедельные восстановительные учения.


Active monitoring: алерты по недоступности API, росту error‑rate, увеличению latency.



12. Примеры и шаблоны
12.1. cURL — подписанный вебхук
X_TS=$(date -u +%s)
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -binary | xxd -p -c 256)
curl -X POST https://mw.example.com/v1/webhooks \
  -H "X-Timestamp: $X_TS" -H "X-Webhook-Signature: sha256=$SIG" \
  -H "Idempotency-Key: $UUID" -d "$BODY"

12.2. Retry‑расписание вебхуков: 1м → 5м → 15м → 1ч → 3ч → 12ч (далее DLQ).
 12.3. Нейминг метрик Prometheus: mw_http_request_duration_seconds{route,method}, mw_http_requests_total{status}, mw_webhook_delivery_latency_seconds{system}, mw_integration_failures_total{system,code}.

13. Глоссарий
SoT (Source of Truth) — система, где хранится «истина» по объекту.


DLQ (Dead Letter Queue) — очередь недоставленных событий для ручной обработки.


ER Freeze — замороженная версия схемы БД, обязательная для всех команд.


Cutover — момент переключения на новый контур/схему.



14. Обязательные правки в текущих документах (to‑do)
SRS «Рюкзак»: актуализировать использование `Idempotency-Key` и `X-Request-Id`; сослаться на Status‑Dictionary v1, ER Snapshot (инициализация) и разделы Environments/DR/Retention; удалить локальные дубли NFR; описать webhook signature и rate limits.


PRD/ONE‑PAGER «Рюкзак»: явная ссылка на политику возвратов (accepted/return_rejected) и уведомления; указать тайминги SLA уведомлений; добавить примечание о включении фич через флаги.


SRS Core Sync: ссылка на SoT‑Matrix v1, Status‑Dictionary v1, DR/BCP; синхронизировать коды ошибок по Core‑API‑Style; зафиксировать использование `integration_log.correlation_id` для идемпотентности.


ER/DDL репозиторий: выпустить тег `schema-init` на основе миграции `0001_init`; миграции DEV; описать expand‑migrate‑contract стратегию без отдельной таблицы idempotency.



15. Чек‑лист «Перед стартом разработки»
Заголовки/версии выровнены (2.1–2.2), политика депрекейта добавлена


Ошибки/пагинация/ретраи/идемпотентность с TTL (2.3–2.5)


JWT/Scopes + ротация ключей (2.6)


Rate limiting и circuit breaker (2.8)


Webhook Security (2.9) + расписание ретраев и DLQ


Временные зоны и NTP (2.10)


Статусы/переходы из Status‑Dictionary (3)


ER Snapshot (инициализация MW) и миграции/rollback‑plan (4, 6.3)


SoT‑Matrix принят владельцами 1С/MW (5)


Metrics & Alerts (8) и Retention (9) согласованы


Environments & Feature Flags (10) согласованы


DR/BCP (11) подтверждены (RTO/RPO/учения)


RACI/Contacts актуальны (10)


To‑do из раздела 14 закрыто


Error Code Registry оформлен и согласован


OpenAPI‑скелеты по ключевым доменам готовы


Маппинг 1С↔MW утверждён Product/1С Lead



16. Error Code Registry (v1)
code
http
message (ru)
Компонент
Кто чинит
Runbook
validation.required
400
Обязательное поле отсутствует
API
Team MW
RB‑VAL‑01
validation.format
400
Неверный формат поля
API
Team MW
RB‑VAL‑02
auth.invalid_token
401
Недействительный токен
Security
DevOps
RB‑AUTH‑01
auth.forbidden
403
Недостаточно прав
API
Team MW
RB‑AUTH‑02
not_found.order
404
Заказ не найден
Orders
Team MW
RB‑NF‑01
conflict.duplicate
409
Конфликт идемпотентности
Core
Team MW
RB‑CFL‑01
rate_limit.exceeded
429
Превышен лимит запросов
Gateway
DevOps
RB‑RL‑01
integration.timeout_1c
504
Таймаут интеграции с 1С
Integrations
1С Lead
RB‑INT‑01
integration.b24_unavailable
503
Недоступен Bitrix24
Integrations
DevOps
RB‑INT‑02

Примечания:
 — «Компонент» = подсистема владельца; «Runbook» = код карточки оперативных действий.
 — Расширение реестра — через RFC; коды стабильны и версионируются.

17. OpenAPI‑скелеты (якоря контрактов)
Опубликованные пути `openapi.yaml`:
- `/health` — технический health-check (без авторизации).
- `/api/v1/system/ping` — пинг для наблюдаемости.
- `/api/v1/returns` — CRUD операций над возвратами (GET list, POST create).
- `/api/v1/returns/{returnId}` — чтение/обновление/удаление возврата.
 Ответы: 200/201/204, 4xx по Error Registry, 429 по rate‑limit, 5xx/504 для интеграций.
 Заголовки: обязательны `Idempotency-Key` для небезопасных операций; `X-Request-Id` опционален.

18. 1С ↔ MW Mapping (v1)
| Объект 1С | MW сущность | Ключ совпадения | Трансформация полей | Статусы (1С ↔ MW) |
| --- | --- | --- | --- | --- |
| Возврат товаров от покупателя | `returns` / `return_lines` | Номер документа + `order_id_1c` | UUID MW, источники (`widget`, `call_center`, `warehouse`); строки — `line_id`, `sku`, `qty`, `quality`, `reason_id`, `photos` | «На проверке» ↔ `return_ready`; «Проведён» ↔ `accepted`; «Отклонён» ↔ `return_rejected` |

Правила:
 — Преобразования фиксируются в миграциях и OpenAPI‑схемах.
 — Статус‑маппинги должны ссылаться на Status‑Dictionary v1.
 — Любое изменение маппинга — через RFC и версионирование API.

Версионные примечания Core Sync:
- 2024-05-09: актуализированы обязательные заголовки (Idempotency-Key, X-Request-Id), убран `X-Api-Version`, зафиксирован стартовый срез схемы (`returns`, `return_lines`, `integration_log`, `task_event`) по миграции `0001_init`.

