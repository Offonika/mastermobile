# Bitrix REST Integration — «Ассистент мастера» v0.1

> Настройки интеграции для v0.1. Основано на требованиях PRD ([ссылка](../../docs/PRD%20%E2%80%94%20%C2%AB%D0%90%D1%81%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BD%D1%82%20%D0%BC%D0%B0%D1%81%D1%82%D0%B5%D1%80%D0%B0%C2%BB.md)) и One-Pager ([ссылка](../../docs/ONE-PAGER%20%E2%80%94%20%D0%90%D1%81%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BD%D1%82%20%D0%BC%D0%B0%D1%81%D1%82%D0%B5%D1%80%D0%B0%20v0.1.md)).

## 1. Аутентификация и окружения
- **Метод:** OAuth 2.0 Bitrix (client credentials) или webhook key — уточнить с владельцем портала; бекенд хранит токен в Secret Manager.
- **Scopes:** `catalog`, `sale`, `rpa`, `crm.order`. Минимально требуется чтение/создание заказов, корзины, возвратов, каталога.
- **Обновление токена:** фоновые задачи с буфером 5 минут до истечения. Ошибки авторизации → алерт + фолбэк сообщение пользователю.
- **Base URL:** `https://<portal>.bitrix24.ru/rest/`.
- **Idempotency:** все модифицирующие вызовы сопровождаются заголовком `Idempotency-Key` (UUID v4, TTL ≥ 72 часа).

## 2. Основные REST-вызовы
| Назначение | Метод/endpoint | Обязательные параметры | Важные ответы | Нефункциональные требования |
| --- | --- | --- | --- | --- |
| Поиск товаров | `POST rest/catalog.product.list` | `filter[q]`, `select[]=ID,NAME,PRICE,DETAIL_PICTURE`, `start` | `result.items[]` с SKU и ценой | Таймаут 3 с, p95 < 250 мс, до 2 ретраев (250/500 мс + jitter) |
| Цены/остатки батч | `POST rest/crm.product.batch` или `rest/catalog.price.list` + `rest/catalog.storeproduct.list` | `cmd[sku_{n}]` (батч ≤ 50 SKU) | `result.result.sku_{n}` с `PRICE`, `CURRENCY`, `STORE_AMOUNT[]` | Параллель до 3 батчей; повтор при 5xx |
| Добавление в корзину | `POST rest/sale.basketitem.add` | `fields[PRODUCT_ID]`, `fields[QUANTITY]`, `fields[FUSER_ID]` | `result` = basket item id | Подтверждение цены/остатка перед заказом |
| Создание заказа | `POST rest/sale.order.add` | `fields[USER_ID]`, `fields[PAYMENT][0][PAY_SYSTEM_ID]`, `fields[SHIPMENT][0][DELIVERY_SERVICE_ID]`, `fields[PROPERTY_VALUES]` (адрес) | `result` = `ORDER_ID`, `result_data.payment_url?` | Payment system выбирается по типу `prepaid`/`cod`; проверка статуса после ответа |
| Получение заказа | `GET rest/sale.order.get` | `id` | `result` с `STATUS_ID`, `PAYMENT`/`SHIPMENT` | Используется для `/track` и `/myorders` |
| Регистрация возврата | `POST rest/sale.orderreserves.add` или кастомный `rest/app.rma.add` | `order_id`, `items[]`, `photos[]` (ссылки) | `result` = `RMA_ID`, `STATUS` | Требуется сохранение ссылок на медиа до 30 дней |
| Вебхуки событий | `POST /webhook/bitrix` | Подпись `X-Webhook-Signature` (HMAC-SHA256) | `event`, `data` | Проверка `event_id` на повтор, TTL 5 мин |

> Если портал не поддерживает перечисленные методы, требуется настроить прокси/приложение Bitrix, но контракты для бота остаются неизменными.

## 3. Маппинг статусов
| Bitrix статус | Назначение | Telegram текст | Категория | Комментарии |
| --- | --- | --- | --- | --- |
| `NEW` | Заказ создан | «Заказ принят, ждём оплату» | Prepaid/COD | Ответ сразу после `order.add` |
| `PAYED` | Оплата подтверждена | «Оплата получена» | Prepaid | Приходит по `payment.status.changed` |
| `WAITING_FOR_DELIVERY` | Готов к отгрузке | «Собираем заказ, готовим к отправке» | Prepaid/COD | Дополнительно отображаем ETA |
| `SHIPPED` | Передан курьеру | «Курьер уже в пути» | Prepaid/COD | Уточняем дату/номер отслеживания |
| `DELIVERED` | Доставлен | «Заказ доставлен» | Prepaid/COD | Для COD инициирует запрос подтверждения оплаты |
| `FINISHED` | Завершён | «Заказ закрыт» | Prepaid/COD | После подтверждения оплаты/возврата |
| `CANCELED` | Отменён | «Заказ отменён. Причина: …» | Любой | Включает подпись причины |
| `RETURN_IN_PROGRESS` | Возврат проверяется | «Возврат на рассмотрении» | RMA | Вебхук `rma.status.changed` |
| `RETURN_COMPLETED` | Возврат завершён | «Возврат принят, средства будут возвращены» | RMA | Отражается в `/return` |
| `RETURN_REJECTED` | Возврат отклонён | «Возврат отклонён: …» | RMA | Требует указания причины |

Статусы синхронизируются с [словарём статусов](../../docs/00%E2%80%91Core%20%E2%80%94%20%D0%A1%D0%B8%D0%BD%D1%85%D1%80%D0%BE%D0%BD%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F%20%D0%B4%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D0%B8.md#3-status-dictionary-v1).

## 4. Вебхуки
- **Эндпоинт:** `POST /webhook/bitrix` (FastAPI). Проверяет `X-Webhook-Signature` (секрет из ENV `WEBHOOK_SECRET`).
- **Поддерживаемые события:**
  - `ONSALEORDERPAYMENT_PAID` → обновление статуса оплаты.
  - `ONSALEORDERDELIVERY_SHPMENTSETMARKED` → изменение доставки/ETA.
  - `ONSALEORDER_ENTITY_SAVED` → общее обновление заказа.
  - Кастомные события приложения: `RMA_STATUS_CHANGED`.
- **Идемпотентность:** каждое событие содержит `event_id`, сохраняемый в таблице/кеше на 10 минут. Повторы → HTTP 200 без повторной обработки.
- **Ретраи:** при 5xx Bitrix повторяет отправку. Бекенд должен обрабатывать повторную доставку события.

## 5. Ограничения и оптимизации
- **Rate limits Bitrix:** по умолчанию 2 запроса/секунда. Реализовать локальный лимитер (token bucket) на уровне FastAPI.
- **Batching:** использовать `batch`-метод Bitrix для объединения до 50 подзапросов (цен/остатков) в один HTTP-вызов.
- **Кеширование:** допускать короткий кеш (TTL ≤ 60 с) для поисковых подсказок. Цены/остатки кэшировать запрещено (см. PRD §8).
- **Медиа:** фотографии для RMA загружать через `disk.folder.uploadfile` с временными ссылками; ссылка на объект хранится до 30 дней.
- **Локализация:** все тексты вебхуков и ответов должны быть на ru-RU; поля Bitrix (enum) приводим к человекочитаемому виду в боте.

## 6. Проверки до запуска
1. Настроить Bitrix webhook-приложение и whitelisting IP бота.
2. Синхронизировать статусные справочники между Bitrix и ботом (таблица выше).
3. Протестировать happy-pathы на stage-портале: поиск → заказ prepaid → заказ COD → RMA.
4. Включить мониторинг HTTP 4xx/5xx, latency и количество ретраев.
5. Обновить Version Map в `docs/00‑Core — Синхронизация документации.md` после зеркалирования Spec Kit.
