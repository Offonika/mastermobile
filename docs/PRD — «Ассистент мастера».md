PRD — «Ассистент мастера» v0.1 (интеграция через сайт, готово к запуску)
Версия: 0.1.1 (Final) • Дата: 30.09.2025
Владелец продукта: {имя/контакт} • Техлид (бот): {имя/контакт} • Техлид (сайт/API): {имя/контакт}
Ссылки на 00‑Core v1.3.3: [§2 Core‑API‑Style](00%E2%80%91Core%20%E2%80%94%20%D0%A1%D0%B8%D0%BD%D1%85%D1%80%D0%BE%D0%BD%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F%20%D0%B4%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D0%B8.md#2-core-api-style-v1), [§3 Status‑Dictionary](00%E2%80%91Core%20%E2%80%94%20%D0%A1%D0%B8%D0%BD%D1%85%D1%80%D0%BE%D0%BD%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F%20%D0%B4%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D0%B8.md#3-status-dictionary-v1), [§5 SoT‑Matrix](00%E2%80%91Core%20%E2%80%94%20%D0%A1%D0%B8%D0%BD%D1%85%D1%80%D0%BE%D0%BD%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F%20%D0%B4%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D0%B8.md#5-sot-matrix-v1-source-of-truth).

## 1. Обзор и цели
Telegram-бот (голос/текст) для B2B-мастеров: быстрый поиск запчастей, оформление заказов (prepaid и COD/«Неси»), статусы/трекинг, возвраты (RMA), короткие техподсказки.
Интеграция v0.1: напрямую с интернет-магазином 1С-Битрикс (API сайта). 1С не используется в этом релизе.

Цели пилота (первые 6–8 недель):
- Время от запроса до оформленного заказа ≤ 1 мин.
- CTR из выдачи ≥ 35–40%, конверсия «поиск → заказ» ≥ 5–7%.
- Стабильность API сайта и экономическая целесообразность канала COD.

## 2. Пользователи и сценарии (Top 5)
- Find → Prepaid: «Найди экран на iPhone 11 оригинал» → карточки → «Заказать» → оплата.
- Find → COD («Неси»): «Неси 2 аккумулятора на A52, чёрные» → подтверждение адреса/суммы → заказ COD.
- Трекинг: «/track 24581» → статус/ETA.
- RMA: «/return 1789 — дисплей брак» → фото/причина → RMA №/QR.
- HowTo: «/howto замена стекла камеры A52» → чек-лист + [Заказать комплект].

## 3. Scope / Out of Scope
**In scope v0.1:** бот (голос/текст), NLU (prompt + словари), поиск/цены/остатки/заказы через API сайта, корзина, трекинг, минимальный RMA, техподсказки (prompt-only), логи/метрики/алерты, аутентификация, отказоустойчивость.
**Out of scope:** персонализация, веб-виджет, внешние поисковые движки/RAG, синк с 1С, сложная курьерка с маршрутами.

## 4. Функциональные требования (FR)
- **FR-01 Поиск.** Вход: текст/голос; извлечь brand/model/model_code?, part_type, quality, color, qty, city?. Выход: 3–5 карточек по Card schema (Приложение A). Правила: 1 авто-уточнение максимум; при неоднозначности — топ-3 «возможно имелось в виду» + быстрые кнопки (A52/A52s, Original/Copy…).
- **FR-02 Заказ (prepaid).** Из карточки → «Заказать» → POST /api/v1/order (payment=prepaid) → order_id, payment_url (истекает через 30 мин). Статус оплаты — по вебхуку.
- **FR-03 «Неси» (COD).** Из карточки → «Неси» → подтверждение адреса/суммы → POST /api/v1/order (payment=cod) → статусы доставки/оплаты курьером — по вебхукам.
- **FR-04 Корзина.** /cart показать/очистить; cart/add из карточки.
- **FR-05 Заказы/трекинг.** /myorders, /track {id} — статусы/ETA из API сайта.
- **FR-06 RMA (минимум).** /return {order_id} → регистрация RMA, загрузка фото, выдача RMA №/QR, статусы: pending|approved|rejected|need_more_info.
- **FR-07 Техподсказки (prompt-only).** /howto, /compat — 4–6 шагов, инструменты/расходники, риски (ESD/герметик/датчики), кнопка [Заказать комплект].
- **FR-08 Аутентификация.** Бот маппит пользователя на сайт через Telegram Login Widget → backend → JWT (X-User-Token), см. §7.

## 5. Нефункциональные требования (NFR)
**Производительность (SLI/SLO):**
- /api/v1/search — p95 ≤ 2.0 c, p99 ≤ 3.5 c, availability ≥ 99.5%/мес.
- /api/v1/order — p95 ≤ 3.0 c, p99 ≤ 5.0 c, availability ≥ 99.0%/мес.
- Общий ответ бота (со STT): p95 ≤ 5 c, p99 ≤ 8 c.

**Надёжность:** таймаут API сайта 3 c, до 2 ретраев (exponential backoff 250/500 мс + jitter), без ретрая на 4xx; Circuit Breaker 60 c на платёж/поиск.

**Degraded mode:** если /api/v1/search недоступен > 30 с:
- показываем выдачу из кэша (TTL 60 c), скрываем «Заказать/Неси»;
- уведомляем пользователя и предлагаем «сообщить, когда восстановится»;
- метрика degraded_mode_on (true/false).

**Безопасность:** маскирование PII в логах; X-Request-Id в каждом запросе; рейт-лимиты; HMAC вебхуков; хранение медиа 7–30 дней (конфиг).

**Соответствие:** 152-ФЗ, минимум GDPR (цели/срок хранения/удаление по запросу).

**Наблюдаемость:** трассировка (опц. OpenTelemetry), метрики latency/error/no-result/clarifications/CTR/conversion/COD share.

## 6. API и интерфейсы (сайт) — версионирование /api/v1
Бот обращается к API сайта (или к тонкому MW-прокси с теми же контрактами):
- POST /api/v1/search { q, filters? } → {items:[Card...]}
- GET /api/v1/price-stock?sku[]=... (batch ≤100) → {by_sku:{SKU:{price,stock_short,warehouses[]}}}
- POST /api/v1/cart/add { sku, qty, user_id } → { cart_id, items_count }
- POST /api/v1/order { items[], payment:"prepaid"|"cod", address, user_id } → { order_id, payment_url?, status }
- GET /api/v1/orders?user_id → { orders:[{id,status,eta,amount}] }
- POST /api/v1/rma { order_id, items[], photos[], user_id } → { rma_id, status }

Вебхуки (подпись HMAC-SHA256, заголовок X-Webhook-Signature, окно реплея ±5 мин):
- order.status.changed, payment.status.changed, delivery.tracking.update (+ idempotency).

Единый формат ошибок:
```json
{"code":"STRING","message":"STRING","hint":"STRING?","retryable":true|false,"correlation_id":"UUID"}
```
Семейства кодов: PAYMENT_UNAVAILABLE, OUT_OF_STOCK, ADDRESS_INVALID, API_TIMEOUT, AUTH_REQUIRED, RATE_LIMITED, THROTTLED, VALIDATION_ERROR, STT_UNCLEAR, AUDIO_TOO_LONG.

## 7. Аутентификация/идентификация
- Onboarding: Telegram Login Widget → backend сайта → выдаётся JWT (RS256, 15 мин) + refresh до 7 дней.
- Бот хранит только X-User-Token (JWT); пароли/логины не храним.
- Привязка: user_id в API = site_user_id из JWT.
- Rate Limit (per user): 60 req/hour (burst 10); /api/v1/order ≤ 5/min; /api/v1/rma ≤ 3/day.
- Scopes: search, cart, order, rma, orders:read.

## 8. Бизнес-правила
- SoT v0.1 — Сайт (Bitrix): каталог/карточки, цены/остатки, заказы, трекинг, RMA. Синонимы/нормализация — в боте (тех-справочник).
- Уточнения: один параметр из {модель/ревизия, качество, qty, цвет}; тайм-аут ответа пользователя 45 сек, затем дефолтная выдача.
- Цены/остатки/статусы: не кэшируем (кроме UI-кэша 30–60 c). Idempotency-Key 72 ч на cart/add и order.

**COD «Неси»:**
- Зоны: Москва/НМО, Санкт-Петербург/ЛО (v0.1).
- Лимиты: сумма COD ≤ 150 000 ₽, масса/объём — в рамках стандартной курьерки.
- Окна доставки: 09:00–19:00, попытки: 2; повторная доставка — платно (тариф курьера).
- Фискализация: чек формирует сайт/курьер (подтвердить исполнителя); статус paid_cod по вебхуку «оплачено».
- Адрес: по умолчанию последний подтверждённый; при изменении — валидация (DaData/КЛАДР). Храним address_hash и историю последних 3 адресов.
- Оплата prepaid: payment_url истекает через 30 мин; при истечении доступна одноразовая регенерация ссылки.

## 9. Метрики успеха и включение RAG-lite
**KPI пилота:** CTR ≥ 35–40% • конверсия поиск→заказ ≥ 5–7% • p95 ≤ 5 c, p99 ≤ 8 c • F1 извлечения сущностей ≥ 80% (golden-set 100 запросов) • no_result ≤ 10%, clarifications ≤ 25%, corrections ≤ 10%.

**Формулы (24h rolling):**
- no_result = пустые выдачи / все запросы
- clarifications = запросы с follow-up / все запросы
- corrections = клики "Похожие/фильтры" / сессии выдачи

**Гейты RAG-lite (только /api/v1/search):** включаем, если нарушены любые 2 из 3 метрик выше. Поток: вектор + BM25 поверх выгрузки сайта → 20 кандидатов → верификация цен/остатков через /api/v1/price-stock → 3–5 карточек. Цены/остатки не индексируем.

## 10. UX-потоки (кратко)
- Find → Prepaid: карточки → «Заказать» → POST /api/v1/order → payment_url → оплата → статус по вебхуку.
- Find → COD: карточки → «Неси» → подтверждение адреса/суммы → POST /api/v1/order (cod) → курьер → «оплачено» по вебхуку.
- RMA: /return 1789 → фото → POST /api/v1/rma → RMA №/QR → статусы pending/approved/rejected/need_more_info.
- HowTo: чек-лист + [Заказать комплект].

## 11. Конфигурация и секреты
- ENV: BOT_TOKEN, SITE_API_BASE_URL, WEBHOOK_SECRET, JWT_PUBLIC_KEY, TELEMETRY_DSN.
- Секреты — в secret-manager; ротация 90 дней; аудит доступа.
- Логи: query-hash, sku, duration, codes, без PII/полных адресов.

## 12. Мониторинг и алерты
**Дашборд:** latency p50/p95/p99, availability per endpoint, error rate, no-result, clarifications, CTR, conversion, COD-share, degraded_mode_on.

**Алерты (Pager/чат):**
- /api/v1/search p95 > 2.0 c (15 мин) или availability < 99.5%/мес.
- /api/v1/order error rate > 3% (15 мин).
- no_result > 12% (24 ч).
- degraded_mode_on = true > 10 мин.

## 13. UAT — критерии приёмки
- Команды /find /order /bring /cart /myorders /track /return /howto /compat работают на stage.
- 100 реальных запросов (≈30 голос / 70 текст) — F1 ≥ 80% по извлечению сущностей.
- 500 нагрузочных запросов: p95 ≤ 5 c (со STT), p99 ≤ 8 c.
- ≥ 90% карточек содержат корректные deeplink/цену/наличие; успешный COD-заказ: верный адрес, статус «в доставке», «оплачено» по вебхуку.

## 14. Риски и смягчение
- Слабый поиск сайта → нормализация/уточнения; при провале метрик — включаем RAG-lite.
- COD/фискализация → заранее утверждённый процесс и ответственный за чек.
- Нестабильность API → ретраи, circuit breaker, версия /api/v1, fallback на degraded mode.
- Голосовая неразборчивость → 1 короткий follow-up + кнопки; STT лимиты: аудио ≤ 75 сек, ≤ 20 МБ, RU/EN авто-детект; при превышении — AUDIO_TOO_LONG.

## 15. Трассируемость (FR → тесты / план работ)

| FR | Покрытие на текущий момент | План работ / пометки |
|----|----------------------------|-----------------------|
| FR-01 Поиск | Автотестов для поиска ассистента нет. | Требуется разработать `tests/test_assistant_search.py` (параметризация из `docs/NLU/golden_set.csv`, smoke по Card schema). |
| FR-02 Order prepaid | Не покрыто существующими тестами. | Добавить сценарий оформления предоплаченного заказа (`tests/test_assistant_order_prepaid.py`) с проверкой webhook оплаты. |
| FR-03 Order COD | Не покрыто. | Разработать тест `tests/test_assistant_order_cod.py` (коридорные значения суммы COD, happy-path + отказ). |
| FR-04 Корзина | Не покрыто. | Нужен тест `tests/test_assistant_cart.py` на добавление/очистку корзины и идемпотентность. |
| FR-05 Orders/Track | Не покрыто. | Завести `tests/test_assistant_orders_track.py`, проверять статусы заказов и трекинг. |
| FR-06 RMA | Не покрыто. | Создать `tests/test_assistant_rma.py` (регистрация, загрузка фото, статусы). |
| FR-07 HowTo/Compat | Не покрыто. | Добавить `tests/test_assistant_howto_compat.py` для чек-листов и CTA «Заказать комплект». |

## 16. Приложения
**A. Card schema (канон ответа поиска, расширенный)**
```json
{
  "sku":"STRING","title":"STRING",
  "quality":"Original|Copy|Grade","color":"STRING?",
  "price_from":0,"stock_short":"в наличии|мало|под заказ",
  "warehouses":["MSK:7","SPB:3"],
  "uom":"pcs","pack_multiplier":1,"moq":1,
  "lead_time":"0-2d","vat_included":true,"reserve_ttl_min":120,
  "url":"https://...","image":"https://...",
  "actions":["open","add_to_cart","order_prepaid","order_cod"]
}
```

**B. System Prompt (сокращённая рабочая версия)**
«Коммерция: намерение → извлечь модель/деталь/qty/качество/цвет/город; 1 уточнение; показать 3–5 карточек (цена «от», наличие, действия); “Закажи”=prepaid, “Неси”=COD. Техподсказки: 4–6 шагов + инструменты/риски. Русский, просто.»

**C. Ошибки → пользовательские тексты**
- PAYMENT_UNAVAILABLE — «Оплата временно недоступна. Оформить “Неси”?»
- OUT_OF_STOCK — «Нет в наличии. Показать аналоги или уведомить о поступлении?»
- ADDRESS_INVALID — «Уточните улицу и номер дома.»
- AUTH_REQUIRED — «Нужно войти. Нажмите “Войти” и подтвердите через Telegram.»
- RATE_LIMITED|THROTTLED — «Слишком много запросов. Попробуйте позже.»
- API_TIMEOUT — «Сервис отвечает медленно. Пробую ещё…»
- STT_UNCLEAR — «Не разобрал запрос. Повторите или напишите текстом.»
- AUDIO_TOO_LONG — «Голос слишком длинный. Отправьте короче (до 75 сек).»

**D. Метрики (формулы)**
См. §9 (включая окна агрегации).
