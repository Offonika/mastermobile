API‑Contracts v1.1.3 — Unified (Walking Warehouse + Core Sync)
Статус: финал для v1 (единый для обоих проектов)
 Основание: выровнено с 00‑Core v1.3; PRD «Ходячий склад» v1.3.2; SRS «Рюкзак» v0.3.1; PRD Core Sync v1.1.2; SRS Core Sync v1.0.1; ER Freeze v0.6.4
 Примечание по совместимости: контракт согласован с ER Freeze v0.6.4 и совместим с инсталляциями, мигрированными с v0.6.1 посредством актуальных SQL‑миграций (`db/migrations`).
Изменения в v1.1.3 против v1.1.2
Добавлены единые Pagination & Filtering параметры (limit/offset/page/sort/filter[*]) и правила валидации


Формула ETag: W/"<sha256(normalized_json)>", примеры 304 и кеш‑валидации


Webhook retries: 1м → 5м → 15м → 1ч → 3ч → 12ч, далее DLQ (см. §0c)


Явно закреплено: PATCH тоже идемпотентный (требует Idempotency-Key)


Расширены примеры ошибок (auth.*, forbidden, rate_limit.exceeded, integration.timeout)


Uploads: лимит 15 МБ → 413, требуемые Content-Type/Accept; опциональный checksum для дедупа


Уточнены обязательные заголовки версии: запросы к API v1 передают заголовок X-Api-Version: 1.1.3 (актуальная минорная версия контракта). Ответы middleware возвращают заголовок API-Version: 1.1.3.



0) Конвенции (обязательно)
Базовое
 Content-Type: application/json; charset=utf-8
 Accept: application/json
 Дата/время: ISO‑8601 / RFC 3339Z (UTC), напр. 2025-09-13T10:15:30Z
 Деньги: number (2 знака), валюта currency_code: "RUB" (ISO‑4217)
 Округление: банковское (round‑half‑to‑even) на 2 знака
Идентификаторы и форматы
 uuid — UUIDv4 (Idempotency-Key, X-Correlation-Id)
 Телефоны клиентов: +7XXXXXXXXXX (строка, 12 символов)
Безопасность (JWT & Scopes)
 Authorization: Bearer <JWT>; роли/скоупы: 1c, courier, admin
 Рекомендуемые клеймы: sub, role, scope, exp, iat, iss, aud; clock‑skew ≤ 30 с; JWKS‑ротация ≤ 90 дн
Идемпотентность и трассировка
 Idempotency-Key: <uuid4> — обязателен для модифицирующих; TTL 72 ч; UNIQUE (key, endpoint, actor_id)
 Повтор с тем же ключом и телом → 200/201 + Idempotent-Replayed: true и прежний Location
 Повтор с тем же ключом и иным телом → 409 conflict.duplicate (type /idempotency)
 PATCH‑методы также требуют Idempotency-Key; при повторе возвращают ту же репрезентацию/ETag
 X-Correlation-Id: <uuid> — во всех ответах и в integration_log
 Поддержка W3C Trace Context: traceparent, tracestate
Rate limiting / Исходящие в Bitrix24
 Квоты по умолчанию: 600 rpm / 30 rps; бурст 2×/10 c; ответы: X-RateLimit-Limit/Remaining/Reset
 При 429 — Retry-After (сек/дата). Исходящие в B24: backoff 5s→15s→30s→… до 15 мин; максимум 20 попыток или 24 ч
Коды ответов (правило)
 Создание — 201 Created + Location
 Изменение/частичное — 200 OK / 204 No Content
 Асинхронная постановка — 202 Accepted (status_url в теле)
Совместимость
 Запросы к API v1 передают заголовок X-Api-Version: 1.1.3 (актуальная минорная версия контракта). Ответы middleware возвращают заголовок API-Version: 1.1.3.
 При отсутствии Idempotency-Key допускается запасной X-Request-Id (UUIDv4), но приоритет за Idempotency-Key
 POST /api/v1/tasks/{id}/status — Deprecated (см. §9)
Нефункциональные лимиты
 lines.maxItems=100, qty >= 0.001
 Фото ≤ 15 МБ (или 4096×4096), image/jpeg|png|heic
 Гео: −90 ≤ lat ≤ 90, −180 ≤ lon ≤ 180
0a) Pagination & Filtering (унифицировано)
Query‑параметры для всех GET со списками:
limit (1..100, по умолчанию 50)


offset (≥0) или page (≥1, взаимно исключительны)


sort=field:asc|desc (несколько полей через запятую)


filter[field]=value (повторяемый; для диапазонов: filter[date_from], filter[date_to])
 Ошибки: неверный формат → 400 validation.format (поле/причина в errors[]). Ответы списков возвращают X-Total-Count и Link для пагинации.


0b) ETag & Cache Validation
ETag: W/"<sha256(normalized_json)>", где normalized_json — JSON без пробелов, с отсортированными ключами.
 If-None-Match → 304 Not Modified при совпадении. Применимо к GET /couriers/{id}/stock и другим GET‑ресурсам.
0c) Webhook Security — retries & DLQ
X-Webhook-Signature: sha256=HEX(HMAC_SHA256(body, secret)), X-Timestamp (окно ±5 мин).


Расписание ретраев: 1м → 5м → 15м → 1ч → 3ч → 12ч; затем помещаем в DLQ с возможностью ручного реплея.


Все попытки логируются в integration_log с correlation_id.



1) 1С → Middleware (REST)
Метод
Путь
Назначение
Тело (ключевые поля)
Успех
Ошибки
Идемп.
POST
/api/v1/orders/{id}/ready
Создать задачу в Bitrix24 по заказу
address, phone, delivery_price, cod_amount, comment, courier_b24_id, currency_code
201 {"task_id_b24":123456} + Location: /api/v1/tasks/123456
400, 404, 409, 5xx
Да
POST
/api/v1/couriers/{id}/stock
Массовое обновление рюкзака
items:[{sku, qty, price_type_id}]
200 {"ok":true}
400, 404, 409, 5xx
Да
GET
/api/v1/couriers/{id}/stock
Получить рюкзак (ETag/кеш)
— (If-None-Match опц.)
200 {items:[{sku, qty, price}]}, ETag; 304 при If‑None‑Match
404, 5xx
—
PATCH
/api/v1/instant-orders/{io_id}
Подтвердить/отклонить мгновенный заказ
status, total, lines[{sku, qty, price, vat_rate?, vat_included?}], currency_code, reject_reason?
200 {"ok":true,"id_1c":"000123"}
400, 404, 409, 5xx
Да
POST
/api/v1/payments/{order_id}/cash
Зафиксировать наличку (ПКО‑черновик)
amount, breakdown:{goods, delivery}, currency_code
201 {"pkodraft_id":"PKO-001"} + Location
400, 404, 409, 5xx
Да

Примечания: phone валидируется как +7XXXXXXXXXX; currency_code обязателен; проверка суммы: round(total,2) == round(sum(lines.price*qty),2); vat_rate ∈ {0,10,20}, vat_included: boolean.

2) Курьер (Bitrix24/виджет) → Middleware
Метод
Путь
Назначение
Тело
Успех
Ошибки
Идемп.
POST
/api/v1/instant-orders
Создать мгновенный заказ
courier_id, client_phone, lines[{sku, qty}], source_task_id
201 {"id":4321,"draft_order_id_1c":"000123","total":990} + Location
400, 404, 409, 5xx
Да
PATCH
/api/v1/tasks/{id}
Обновить статус задачи
{ status: PICKED_UP|ON_ROUTE|DELIVERED|CASH_RETURNED|FAILED, reason_code?, reason_note? }
200 {"ok":true}/204
400, 404, 409, 5xx
Да
POST
/api/v1/tasks/{id}/photos
Привязать фото
Режим A: { type:pickup|handout|cash, b24_file_id }; Режим B: multipart/form-data (fallback) + checksum (опц., sha256)
201 {"photo_id":"ph_123"} + Location
400, 404, 409, 413, 415, 5xx
Да
POST
/api/v1/tasks/{id}/checkins
Гео‑чек‑ин
{ type:start|delivered, lat, lon, ts }
201 {"checkin_id":"ci_789"} + Location
400, 404, 409, 5xx
Да


3) Возвраты → Middleware
Метод
Путь
Назначение
Тело
Успех
Ошибки
Идемп.
POST
/api/v1/returns
Инициировать возврат (return_ready)
{ source:widget, courier_id, order_id_1c?, items:[{sku, qty, quality:new|defect, reason_code, reason_note?, photos:[b24_file_id], imei?, serial?}] }
201 {"return_id":501} + Location
400, 401, 404, 409
Да
PATCH
/api/v1/returns/{id}
Принять возврат (менеджер)
{ status: accepted }
200 {"ok":true}
400, 401, 404, 409
Да
POST
/api/v1/returns/{id}/reject
Отклонить («брак не подтвердился»)
{ reason_code: no_defect_found|other, reason_note?, items:[{line_id?, sku, qty}], actor:{id_1c, fio} }
200 {"ok":true}
400, 401, 404, 409
Да

Процессные примечания: при reject MW ставит return_rejected, создаёт подзадачу B24 «Вернуть товар клиенту», отправляет уведомление. В 1С движений нет до accepted.

4) Middleware ↔ Bitrix24 (исходящие вызовы MW)
Минимальный набор и поведение остаются как в v1.1.2. Идемпотентность обеспечивается на стороне MW (хэш/ключи файлов, повтор task.add по ключу не создаёт дубль). UF‑поля минимум: UF_DELIVERY_ADDRESS, UF_DELIVERY_PHONE, UF_DELIVERY_SUM_COD, UF_DELIVERY_PRICE, UF_PHOTO_PICKUP, UF_PHOTO_HANDOUT, UF_PHOTO_CASH, UF_GEO_START, UF_GEO_DONE.

5) JSON‑схемы (фрагменты)
Без изменений по сравнению с v1.1.2, см. раздел 5 исходника. Дополнение: во всех денежных схемах — currency_code обязателен; для фото допускается heic.

6) Ошибки — application/problem+json
{
  "type": "https://api.example.com/errors/validation",
  "title": "Validation failed",
  "status": 400,
  "detail": "client_phone: must match +7XXXXXXXXXX",
  "instance": "/api/v1/instant-orders",
  "code": "validation.format",
  "errors": [{"field":"client_phone","reason":"pattern"}]
}

Примеры:
Auth (401)


{ "type":"/auth", "title":"Unauthorized", "status":401, "code":"auth.invalid_token", "detail":"JWT expired", "instance":"/api/v1/tasks/1" }

Forbidden (403)


{ "type":"/forbidden", "title":"Forbidden", "status":403, "code":"auth.forbidden", "detail":"Not owner of the task" }

Rate limit (429)


{ "type":"/rate-limit", "title":"Too Many Requests", "status":429, "code":"rate_limit.exceeded", "detail":"Retry later" }

Integration timeout (504)


{
  "type":"/timeout",
  "title":"Upstream Timeout",
  "status":504,
  "code":"integration.timeout_1c",
  "detail":"1C did not respond in 10s"
}

Таксономия (симметрично Error Code Registry): validation.*, auth.*, forbidden, not_found.*, conflict.duplicate, rate_limit.exceeded, integration.*, timeout.*.

7) Статусы и маппинг (Status‑Dictionary v1)
Единый словарь состояний (Order/Task/B24‑канбан):
 NEW → PICKING → READY → PICKED_UP → ON_ROUTE → DELIVERED → CASH_RETURNED → DONE (+ ветки FAILED, REFUSED).
 Курьер может отправлять: PICKED_UP, ON_ROUTE, DELIVERED, CASH_RETURNED, FAILED.
 READY/DONE/REFUSED выставляются системой/MW/менеджером. Переходы валидируются по матрице (см. 00‑Core §3).

8) Примеры cURL
(см. версию v1.1.2 — без изменений, дополнены заголовки X-Api-Version и Idempotency-Key).

9) Совместимость и депрекейшены
POST /api/v1/tasks/{id}/status — Deprecated в 1.1.x. Возвращать заголовки:
 Deprecation: true
 Sunset: 2026-03-31T00:00:00Z
 Link: </api/v1/tasks/{id}>; rel="successor-version"
X-Request-Id поддерживается как запасной ключ; при повторе — Idempotent-Replayed: true и прежний Location.

10) RBAC/Scopes (матрица ролей)
Таблица ролей/эндпоинтов совпадает с v1.1.2. Дополнено ограничение "только свои" по courier_id/владению задачей (проверка на MW) и обязательные scopes (nsi.read|write, orders.write, returns.write, tasks.read, webhooks.sign).

11) Идемпотентность: детали по платежам
POST /payments/{order_id}/cash — дедуп по (order_id, Idempotency-Key, actor_id).
 Повтор с тем же ключом → 201/200, тот же pkodraft_id и Location.
 Повтор с иным телом → 409 conflict.duplicate.

12) Версионирование API
Версия — в пути /api/v1/...; минорная фиксируется заголовками.
Запросы к API v1 передают заголовок X-Api-Version: 1.1.3 (актуальная минорная версия контракта). Ответы middleware возвращают заголовок API-Version: 1.1.3.
 Любые ломающие изменения → /api/v2/....
 Совместимость: minor‑изменения только additive (новые поля опциональны, новые эндпоинты не ломают старые). В примерах ответов показываем API-Version.