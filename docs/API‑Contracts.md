
# API‑Contracts — Returns API v1.0.0

Версия документа: v1.0.0  
Дата обновления: 20.09.2025  
Статус: draft  
Связанные артефакты: `openapi.yaml` (info.version = 1.0.0)

## 0. Обзор
- Скелет FastAPI сейчас обслуживает только `GET /health` с жёстко заданным ответом `{"status": "ok"}` (см. `apps/mw/src/app.py`, `apps/mw/src/health.py`).
- Версионированный контракт v1.0.0 охватывает только блок returns (`/api/v1/returns` и `/api/v1/returns/{returnId}`) и публикуется через `openapi.yaml`.
- Дальнейшие секции фиксируют обязательные заголовки, форматы и ответы для возвратов.

## 1. Общие требования
### 1.1 Content-Type и кодировки
- Все тела запросов и ответов — `application/json; charset=utf-8`.
- Клиент явно указывает `Accept: application/json`.

### 1.2 Аутентификация и безопасность
- Все эндпоинты под `/api/v1/returns` требуют `Authorization: Bearer <JWT>` с ролями `1c`, `courier` или `admin`.
- `GET /health` и инфраструктурный `/api/v1/system/ping` остаются без аутентификации и служат для мониторинга.

### 1.3 Корреляция и идемпотентность
- `X-Request-Id` — опциональный заголовок запроса. При отсутствии клиентского значения middleware генерирует его и возвращает в ответе.
- `Idempotency-Key` обязателен для всех модифицирующих операций (`POST`, `PUT`, `DELETE`) и ограничен 128 символами.

### 1.4 Формат ошибок
- Контракт использует `application/problem+json` со схемой `Error` (`type`, `title`, `status`, `detail`, `errors[]`, `request_id`).
- Таксономия кодов уточняется по мере развития; поле `code` и `instance` в v1.0.0 отсутствуют.

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

## 3. Эндпоинты блока returns
### 3.1 GET /api/v1/returns
- Назначение: пагинированный список возвратов.
- Параметры запроса: `page` (>=1, по умолчанию 1), `page_size` (1..100, по умолчанию 20), опциональный `X-Request-Id`.
- Ответ 200: объект `PaginatedReturns` (`items[]`, `page`, `page_size`, `total_items`, `total_pages`, `has_next`).
- Ошибки: 400 `Error` (некорректные параметры).

### 3.2 POST /api/v1/returns
- Назначение: регистрация нового возврата (Bitrix24/курьер).
- Тело: `ReturnCreate`.
- Заголовки: `Authorization`, `Idempotency-Key`, опционально `X-Request-Id`.
- Ответ 201: `Return` + заголовки `Location` (URI созданного ресурса), `X-Request-Id`.
- Ошибки: 400 (валидация), 409 (повтор с другим телом).

### 3.3 GET /api/v1/returns/{returnId}
- Назначение: получить возврат по идентификатору.
- Заголовки: `Authorization`, опционально `X-Request-Id`.
- Ответ 200: `Return`.
- Ошибки: 404, `Error`.

### 3.4 PUT /api/v1/returns/{returnId}
- Назначение: полное обновление возврата (1С/администратор).
- Тело: `ReturnCreate`.
- Заголовки: `Authorization`, `Idempotency-Key`, `X-Request-Id` (опц.).
- Ответ 200: актуальный `Return`.
- Ошибки: 400 (валидация), 404 (не найдено), 409 (конфликт идемпотентности).

### 3.5 DELETE /api/v1/returns/{returnId}
- Назначение: логическое удаление/отмена возврата.
- Заголовки: `Authorization`, `Idempotency-Key`, `X-Request-Id` (опц.).
- Ответ 204 без тела.
- Ошибки: 404 `Error`.

## 4. Системные эндпоинты
- `GET /health` — проверка живости сервиса; возвращает `{ "status": "ok" }`.
- `GET /api/v1/system/ping` — диагностический ответ `Ping` (статус + timestamp), может вернуть `503` c `Error`.

## 5. Changelog
- 20.09.2025 — Обновлено описание до фактического контракта v1.0.0, убрано требование `X-Api-Version`, зафиксированы только эндпоинты returns и системные проверки.
