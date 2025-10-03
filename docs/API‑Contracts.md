# API‑Contracts — MasterMobile API v1.0.0

Версия документа: v1.1.1
Дата обновления: 27.09.2025
Статус: draft
Связанные артефакты: `openapi.yaml` (info.version = 1.0.0)

> Примечание (27.09.2025). Аудит артефактов подтвердил, что актуальная целевая версия API‑Contracts — v1.1.1. Ссылки на v1.1.3
> считаются устаревшими до появления отдельного релиза контракта.

## 0. Обзор
- `openapi.yaml` публикует три прикладных домена: `returns`, `b24-calls`, `walking-warehouse`, а также служебные проверки `system` (`/health`, `/api/v1/system/ping`).
- `returns` и `walking-warehouse` используют `Authorization: Bearer <JWT>` с ролевой моделью из `x-roles`; допускаются только перечисленные роли (`1c`, `courier`, `admin` в зависимости от операции).
- Экспорт Bitrix24 (`b24-calls`) доступен без аутентификации, но требует валидных фильтров периода и поддерживает `X-Request-Id` для трассировки.
- Заголовок `X-Request-Id` опционален для всех операций; `Idempotency-Key` обязателен для всех небезопасных методов (`POST`, `PUT`, `PATCH`, `DELETE`) в доменах `returns` и `walking-warehouse`.
- Схемы ошибок и полезных нагрузок синхронизированы с `openapi.yaml`; дальнейшие изменения должны сопровождаться обновлением этого документа и changelog.

## 1. Общие требования
### 1.1 Content-Type и кодировки
- Все тела запросов и ответов — `application/json; charset=utf-8`, если явно не указано иное (например, `text/csv` для экспорта).
- Клиент явно указывает `Accept: application/json` либо `text/csv` для CSV-экспортов.

### 1.2 Аутентификация и безопасность
- Схема безопасности — `bearerAuth` (`JWT`). Токен обязан содержать роль, разрешённую для конкретной операции:
  - `returns`: см. раздел 3 (роли `1c`, `courier`, `admin`).
  - `walking-warehouse`: см. раздел 5 (роли `courier`, `admin`).
- Системные проверки и экспорт Bitrix24 (`b24-calls`) анонимны и не предъявляют требований к заголовку `Authorization`.

### 1.3 Корреляция и идемпотентность
- `X-Request-Id` — опциональный заголовок запроса. При отсутствии клиентского значения middleware генерирует его и возвращает в ответе.
- `Idempotency-Key` обязателен для всех модифицирующих операций (`POST`, `PUT`, `PATCH`, `DELETE`) в `returns` и `walking-warehouse`. Максимальная длина — 128 символов.

### 1.4 Формат ошибок
- Контракт использует `application/problem+json` со схемой `Error` (`type`, `title`, `status`, `detail`, `errors[]`, `request_id`).
- Таксономия кодов уточняется по мере развития; поле `code` и `instance` в v1.1.0 отсутствуют.

## 2. Сущности returns
### 2.1 Return
| Поле | Тип | Обязательность | Описание |
| --- | --- | --- | --- |
| `id` | string | Да | Уникальный идентификатор возврата. |
| `status` | string | Да | `pending`, `accepted`, `rejected`, `cancelled`. |
| `source` | string | Да | Канал: `widget`, `call_center`, `warehouse`. |
| `courier_id` | string | Да | Курьер, оформивший возврат. |
| `order_id_1c` | string/null | Нет | Ссылка на заказ в 1С. |
| `manager_id` | string/null | Нет | Менеджер, обработавший возврат. |
| `comment` | string/null | Нет | Дополнительные примечания. |
| `created_at` / `updated_at` | date-time | Да | Метки времени в UTC. |
| `items[]` | array | Да | Номенклатура возврата (см. ниже). |

Каждый элемент `items[]` содержит `line_id`, `sku`, `qty`, `quality (new|defect|unknown)`, `reason_code`, опционально `reason_note`, `photos[]`, `imei`, `serial`.

### 2.2 ReturnCreate
- Требует `source`, `courier_id`, `items[]`.
- Структура элемента массива совпадает с `items[]` в `Return`, но без `line_id` (генерируется системой).

### 2.3 ReturnRejectRequest
| Поле | Тип | Обязательность | Описание |
| --- | --- | --- | --- |
| `reason_code` | string | Да | Код причины отклонения: `no_defect_found`, `other`. |
| `reason_note` | string/null | Нет | Текстовое пояснение, обязательно при `reason_code = other`. |
| `items[]` | array | Да | Строки возврата к отклонению (см. структуру ниже). |
| `actor.id_1c` | string | Да | Идентификатор сотрудника в 1С, инициировавшего отклонение. |
| `actor.fio` | string | Да | ФИО инициатора (для аудита и уведомлений). |

Каждый элемент `items[]` включает `line_id` (string), `sku` (string), `qty` (number, >0). Частично принятые строки повторно отклонять нельзя.

## 3. Домен returns
### 3.1 GET /api/v1/returns
- Назначение: пагинированный список возвратов.
- Роли: `1c`, `admin`.
- Параметры запроса: `page` (>=1, по умолчанию 1), `page_size` (1..100, по умолчанию 20).
- Заголовки: опционально `X-Request-Id`.
- Ответ 200: `PaginatedReturns` (`items[]`, `page`, `page_size`, `total_items`, `total_pages`, `has_next`).
- Ошибки: 422 `Error` (валидация фильтров/пагинации).

### 3.2 POST /api/v1/returns
- Назначение: регистрация нового возврата (Bitrix24/курьер).
- Роли: `courier`, `admin`.
- Тело: `ReturnCreate`.
- Заголовки: `Authorization`, `Idempotency-Key`, опционально `X-Request-Id`.
- Ответ 201: `Return` + заголовки `Location` (URI созданного ресурса), `X-Request-Id`.
- Ошибки: 422 (валидация), 409 (повтор с другим телом по `Idempotency-Key`).

### 3.3 GET /api/v1/returns/{returnId}
- Назначение: получить возврат по идентификатору.
- Роли: `1c`, `courier`, `admin`.
- Заголовки: `Authorization`, опционально `X-Request-Id`.
- Ответ 200: `Return`.
- Ошибки: 404 `Error` (не найдено).

### 3.4 PUT /api/v1/returns/{returnId}
- Назначение: полное обновление возврата (1С/администратор).
- Роли: `1c`, `admin`.
- Тело: `ReturnCreate`.
- Заголовки: `Authorization`, `Idempotency-Key`, опционально `X-Request-Id`.
- Ответ 200: актуальный `Return`.
- Ошибки: 422 (валидация), 404 (не найдено), 409 (конфликт идемпотентности).

### 3.5 DELETE /api/v1/returns/{returnId}
- Назначение: логическое удаление/отмена возврата.
- Роли: `admin`.
- Заголовки: `Authorization`, `Idempotency-Key`, опционально `X-Request-Id`.
- Ответ 204 без тела.
- Ошибки: 422 (валидация идентификатора), 404 `Error`.

### 3.6 POST /api/v1/returns/{returnId}/reject
- Назначение: отклонение возврата после проверки качества.
- Роли: `1c`, `admin`.
- Тело: `ReturnRejectRequest`.
- Заголовки: `Authorization`, `Idempotency-Key`, опционально `X-Request-Id`.
- Ответ 200: актуальный `Return` со статусом `rejected` и заполненным блоком аудита.
- Ошибки: 400 (отсутствует тело или нарушена бизнес-логика), 404 (`Error`, возврат не найден), 409 (повтор с иным телом по `Idempotency-Key` или возврат уже закрыт), 422 (валидация элементов `items[]`).

## 4. Домен b24-calls
### 4.1 GET /api/v1/b24-calls/export.csv
- Назначение: выгрузка звонков Bitrix24 в CSV.
- Аутентификация: не требуется (анонимный доступ).
- Параметры запроса: `employee_id`, `date_from`, `date_to`, `has_text`.
- Заголовки: опционально `X-Request-Id`.
- Ответ 200: поток `text/csv` (UTF-8) с отфильтрованными звонками.
- Ошибки: 400 (некорректный диапазон дат), 422 (валидация параметров).

### 4.2 GET /api/v1/b24-calls/export.json
- Назначение: выгрузка звонков Bitrix24 в JSON-массив.
- Аутентификация: не требуется.
- Параметры запроса: `employee_id`, `date_from`, `date_to`, `has_text`.
- Заголовки: опционально `X-Request-Id`.
- Ответ 200: массив `B24CallRecord`.
- Ошибки: 400 (некорректный диапазон дат), 422 (валидация параметров).

## 5. Домен walking-warehouse
- Общие требования: `Authorization: Bearer <JWT>`; допустимые роли зависят от операции (см. ниже). Все модифицирующие запросы требуют `Idempotency-Key` и возвращают `Order`/`Courier`.

### 5.1 GET /api/v1/ww/couriers
- Роли: `courier`, `admin`.
- Параметры: `q` (поиск по id/имени/телефону).
- Ответ 200: `CouriersResponse`.
- Ошибки: 401, 403, 422.

### 5.2 POST /api/v1/ww/couriers
- Роли: `admin`.
- Заголовки: `Authorization`, `Idempotency-Key`, `X-Request-Id` (опц.).
- Тело: `CourierCreate`.
- Ответ 201: `Courier` + `Location`.
- Ошибки: 401, 403, 409 (дубликат), 422.

### 5.3 GET /api/v1/ww/orders
- Роли: `courier`, `admin`.
- Параметры: `status[]`, `q`.
- Ответ 200: `OrderListResponse`.
- Ошибки: 401, 403, 422.

### 5.4 POST /api/v1/ww/orders
- Роли: `courier`, `admin`.
- Заголовки: `Authorization`, `Idempotency-Key`, `X-Request-Id` (опц.).
- Тело: `OrderCreate`.
- Ответ 201: `Order` + `Location`.
- Ошибки: 401, 403, 404 (курьер не найден), 409, 422.

### 5.5 PATCH /api/v1/ww/orders/{orderId}
- Назначение: частичное обновление заказа.
- Роли: `courier`, `admin`.
- Заголовки: `Authorization`, `Idempotency-Key`, `X-Request-Id` (опц.).
- Тело: `OrderUpdate`.
- Ответ 200: `Order`.
- Ошибки: 401, 403, 404, 422.

### 5.6 POST /api/v1/ww/orders/{orderId}/assign
- Назначение: назначение/снятие курьера.
- Роли: `courier`, `admin`.
- Заголовки: `Authorization`, `Idempotency-Key`, `X-Request-Id` (опц.).
- Тело: `OrderAssign`.
- Ответ 200: `Order`.
- Ошибки: 401, 403, 404 (заказ или курьер), 422.

### 5.7 POST /api/v1/ww/orders/{orderId}/status
- Назначение: смена статуса заказа.
- Роли: `courier`, `admin`.
- Заголовки: `Authorization`, `Idempotency-Key`, `X-Request-Id` (опц.).
- Тело: `OrderStatusUpdate`.
- Ответ 200: `Order`.
- Ошибки: 401, 403, 404, 422.

### 5.8 GET /api/v1/ww/report/deliveries
- Роли: `courier`, `admin`.
- Параметры: `status[]`, `courier_id`, `created_from`, `created_to`, `format` (`json`/`csv`).
- Заголовки: опционально `X-Request-Id`.
- Ответ 200: `DeliveryReportResponse` или поток CSV.
- Ошибки: 401, 403, 422.

### 5.9 GET /api/v1/ww/export/kmp4
- Роли: `courier`, `admin`.
- Параметры: `status[]`, `courier_id`, `created_from`, `created_to`.
- Заголовки: опционально `X-Request-Id`.
- Ответ 200: `KMP4ExportResponse`.
- Ошибки: 401, 403, 422, 500 (внутренняя ошибка сериализации).

### 5.10 Матрица переходов статусов Walking Warehouse
Матрица используется эндпоинтом `POST /api/v1/ww/orders/{orderId}/status` и справочником `status_dict`. Нарушение правил приводит
к ответу `422 Error` с указанием некорректного перехода.

| Текущий статус | Разрешённые переходы | Допустимые инициаторы | Примечания |
| --- | --- | --- | --- |
| `NEW` | `PICKING`, `READY`, `REFUSED` | MW (`admin`), 1С интеграция | Системная инициализация заказа или отмена на старте. |
| `PICKING` | `READY`, `REFUSED` | MW (`admin`), 1С интеграция | Курьер в этом статусе недоступен к смене. |
| `READY` | `PICKED_UP`, `REFUSED` | MW (`admin`), менеджер | `REFUSED` фиксирует отказ клиента/менеджера. |
| `PICKED_UP` | `ON_ROUTE`, `FAILED` | Курьер, MW (`admin`) | `FAILED` доступен только при подтверждённом выезде. |
| `ON_ROUTE` | `DELIVERED`, `FAILED` | Курьер | `FAILED` — нарушение SLA или возврат заказа. |
| `DELIVERED` | `CASH_RETURNED`, `DONE`, `FAILED` | Курьер, MW (`admin`) | `DONE` доступен при безнале; `FAILED` — спор по оплате. |
| `CASH_RETURNED` | `DONE` | Курьер | Закрывает наличный расчёт. |
| `DONE` | — | — | Финальное состояние. Переходы запрещены. |
| `REFUSED` | — | — | Финальное состояние, заказ возвращён в 1С. |
| `FAILED` | `READY`, `DONE` | MW (`admin`), 1С интеграция | Повторная отправка допускается только после ручной проверки. |

Правила:
- Курьерские роли (`courier`) не могут возвращать заказ в статусы `NEW`/`PICKING`/`READY`.
- Возврат из `FAILED` в рабочую цепочку (`READY`) требует явного запроса 1С и сопровождается записью в `integration_log`.
- Все статусы помечаются временной меткой в `task_events`; повторный переход в то же значение блокируется бизнес-логикой.

## 6. Системные эндпоинты
- `GET /health` — проверка живости сервиса; возвращает `{ "status": "ok" }` и `X-Request-Id`.
- `GET /api/v1/system/ping` — диагностический ответ `Ping` (статус + timestamp), может вернуть `503` c `Error`.

## 7. Changelog
- 26.09.2025 — Подтверждено, что действующая версия контракта — v1.1.0; сопутствующие документы выровнены на корректные ссылки.
- 25.09.2025 — v1.1.0: Синхронизирован список доменов с `openapi.yaml`, обновлены роли и ошибки для returns, добавлены разделы `b24-calls` и `walking-warehouse`.
- 20.09.2025 — v1.0.0: Обновлено описание до фактического контракта v1.0.0, убрано требование `X-Api-Version`, зафиксированы только эндпоинты returns и системные проверки.
