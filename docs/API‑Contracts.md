# API Contracts — MasterMobile MW v1

Документ описывает фактический контракт API, опубликованный в `openapi.yaml`, и связывает его с текущей схемой БД (`apps/mw/migrations/versions/0001_init.py`).

## Общие конвенции
- Формат данных: `application/json; charset=utf-8`.
- Временные значения — `RFC 3339` (UTC).
- Числовые поля количеств — `integer` или `number` с точностью до 3 знаков после запятой (см. `return_lines.qty`).
- Денежные суммы — `number` (2 знака) + `currency_code` (ISO‑4217), когда поле присутствует.
- Все UUID передаются в текстовом виде (`Idempotency-Key`, `return_id`, `correlation_id`).

## Заголовки и аутентификация
- `Authorization: Bearer <JWT>` — обязателен для всех эндпоинтов, кроме `/health`. Поддерживаемые роли: `1c`, `courier`, `admin`.
- `X-Request-Id` — опциональный идентификатор корреляции. Если не передан, MW генерирует значение и возвращает его в заголовке ответа и поле `request_id` ошибок.
- `Idempotency-Key` обязателен для `POST`, `PUT`, `DELETE` под `/api/v1/returns`. Повтор с тем же ключом и телом возвращает исходный ответ; расхождение payload приводит к `409 Conflict`.
- Заголовок `X-Api-Version` не используется. Версионирование обеспечивается префиксом `/api/v1` и семантикой OpenAPI.

## Пагинация
`GET /api/v1/returns` поддерживает параметры `page` (≥ 1, по умолчанию 1) и `page_size` (1..100, по умолчанию 20). Ответ — объект `PaginatedReturns` (`items`, `page`, `page_size`, `total_items`, `total_pages`, `has_next`).

## Схемы
### Return
- Поля: `id`, `status`, `source`, `courier_id`, `order_id_1c?`, `manager_id?`, `comment?`, `items[]`, `created_at`, `updated_at`.
- Допустимые `status` по контракту: `pending`, `accepted`, `rejected`, `cancelled`. В БД хранится `return_ready`/`accepted`/`return_rejected`; конверсия фиксируется в приложении при записи/чтении.
- `source` ∈ {`widget`, `call_center`, `warehouse`} (проверяется ограничением `chk_returns_source`).
- `items[]` повторяет структуру строк возврата, включая `line_id`, `sku`, `qty`, `quality`, `reason_code`, `reason_note?`, `photos[]`, `imei?`, `serial?`.

### ReturnCreate
- Используется для `POST` и `PUT` операций.
- Обязательные поля: `source`, `courier_id`, `items[]`.
- `items[].quality` ∈ {`new`, `defect`, `unknown`} по контракту; в БД допустимы `new`, `defect`. Значение `unknown` нормализуется до `defect` или отклоняется — см. требования бизнес-логики.
- `reason_code` — строковый идентификатор причины, `reason_note` — человекочитаемый комментарий.

### PaginatedReturns
- Коллекция возвратов + метаданные страницы (`page`, `page_size`, `total_items`, `total_pages`, `has_next`).

## Эндпоинты
### GET `/health`
- Назначение: простая проверка готовности сервиса.
- Ответ: `200 OK`, схема `Health` (статус, версия, аптайм). Без авторизации.

### GET `/api/v1/system/ping`
- Назначение: системный пинг.
- Ответы: `200 OK` (схема `Ping`), `503` для недоступности. Заголовок `X-Request-Id` возвращается всегда.

### `/api/v1/returns`
#### GET `listReturns`
- Роли: `1c`, `admin`.
- Параметры: `page`, `page_size`.
- Ответ `200`: `PaginatedReturns`.
- Ошибка `400`: некорректные параметры пагинации.

#### POST `createReturn`
- Роли: `courier`, `admin`.
- Заголовки: `Idempotency-Key` обязателен, `X-Request-Id` опционален.
- Тело: `ReturnCreate`.
- Успех `201`: тело `Return`, заголовок `Location` на созданный ресурс.
- Ошибки: `400` (валидация), `409` (расхождение по `Idempotency-Key`).

### `/api/v1/returns/{returnId}`
Параметр пути `returnId` — UUID возврата (см. `returns.return_id`).

#### GET `getReturn`
- Роли: `1c`, `courier`, `admin`.
- Ответ `200`: `Return`.
- Ошибка `404`: возврат не найден.

#### PUT `updateReturn`
- Роли: `1c`, `admin`.
- Заголовок `Idempotency-Key` обязателен.
- Тело: `ReturnCreate` (полностью заменяет запись).
- Ответ `200`: обновлённый `Return`.
- Ошибки: `400` (валидация), `404`, `409` (расхождение по `Idempotency-Key`).

#### DELETE `deleteReturn`
- Роли: `admin`.
- Заголовок `Idempotency-Key` обязателен.
- Ответ `204 No Content`.
- Ошибки: `404` (не найден).

## Наблюдаемость и идемпотентность
- Все запросы логируются в `integration_log` с `correlation_id`, совпадающим с `Idempotency-Key` для входящих модифицирующих операций.
- Уникальность событий Bitrix24 обеспечивается `task_event.correlation_id` (уникальный индекс).
- Ошибки возвращаются в формате `application/problem+json`, поле `request_id` помогает связать ответ с логами и записями в `integration_log`.

## Версионные примечания
- 2024-05-09: обновлены требования к заголовкам (`Idempotency-Key`, `X-Request-Id`), удалён `X-Api-Version`, описание эндпоинтов приведено в соответствие с `openapi.yaml` и миграцией `0001_init`.
