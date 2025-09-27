
SRS — Тексты звонков Bitrix24 (выгрузка за 60 дней)
Версия: v1.0.0 (синхронизировано с 00‑Core v1.3.1, API‑Contracts v1.1.3, ER Freeze v0.6.4)
Дата: 21.09.2025
Владелец: Интеграции / DataOps
Связанные документы: [PRD — Тексты звонков Bitrix24 v1.0.0 (19.09.2025)](docs/PRD — Тексты звонков Bitrix24.md), [ONE-PAGER — «Тексты всех звонков за 60 дней из Bitrix24»](docs/b24-transcribe/ONE-PAGER.md) (финал), [Runbook — Выгрузка реестра звонков](docs/runbooks/call_export.md), [Call Registry Schema](docs/specs/call_registry_schema.yaml)

1. Назначение
SRS фиксирует технические требования к батчевому пайплайну выгрузки аудиозаписей и текстов всех звонков Bitrix24 за последние 60 дней. Документ расширяет PRD за счёт детализации интеграций, хранения state в MW, форматов артефактов и уровней контроля качества, а также связывает решение с общими нормами 00‑Core (Core-API-Style, Retention, Metrics & Alerts, Security). Целевая аудитория: инженеры интеграций, DataOps, QA, on-call.

2. Цели и KPI
2.1. Цели v1 (производственный запуск в течение 2 недель)
- F-GOAL-01. Обеспечить сбор 100% звонков Bitrix24 за указанный период (по умолчанию `today-60d .. today`).
- F-GOAL-02. Получить читабельные транскрипты для ≥ 98% аудиофайлов, доступных в Bitrix24.
- F-GOAL-03. Сформировать полный пакет артефактов (`exports/<period>/`) и отчёт по длительности/стоимости без ручных шагов.

2.2. KPI / метрики успеха
| Метрика | Цель | Способ измерения |
| --- | --- | --- |
| Покрытие звонков | ≥ 99% записей с доступным аудио имеют транскрипт | сравнение `call_records.status = 'completed'` vs Bitrix24 registry |
| SLA пайплайна | ≤ 6 часов на обработку 60 дней при параллельности 10 | `call_export_duration_seconds` p95 |
| Расхождение длительности | ≤ 0,5% относительно отчёта Bitrix24 | отчёт `reports/summary_<period>.md` vs Bitrix24 API |
| Ошибки > 24 ч | ≤ 1% звонков в статусе `error` спустя 24 ч | мониторинг `call_transcripts_total{status="error"}` |
| Дубли транскриптов | 0 на 1000 звонков | уникальность `call_id + record_id + period` |
| Стоимость распознавания | ≤ прогноз +20% | `call_export_cost_total` + budget alert |

3. Scope, допущения и ограничения
3.1. Входит в релиз v1
- REST-интеграция с Bitrix24 телефонией для получения списка звонков и ссылок на записи.
- Автоматическое скачивание аудио (mp3/wav) с контролем размера и контрольных сумм.
- Передача аудио в сервис распознавания (Whisper или совместимый API) с нарезкой > 15 мин.
- Создание текстовых файлов (UTF-8) и CSV-реестра с обязательными полями, отчёта с агрегатами.
- Опциональное создание саммари/тегов при включённом флаге `EXPORT_SUMMARY_ENABLED`.
- Идемпотентность повторных запусков (по `period_from/to`, `call_id`, `record_id`).
- Мониторинг, алерты и отчётность по SLA/стоимости в соответствии с 00‑Core §2, §7, §9.

3.2. Не входит в v1
- Реалтайм распознавание или вебхуки по завершении звонка.
- BI-дашборды (поставка отдельными задачами), интеграция с ChatGPT beyond шаблонов.
- Очистка исторических периодов > 90 дней.
- Автоматическая классификация содержания (за пределами кратких саммари).

3.3. Допущения
- Доступ к Bitrix24 API с правами чтения звонков и скачивания записей (OAuth/webhook token, хранимый в Secret Manager).
- Whisper API доступен и выдерживает тарифные квоты; стоимость списывается на корпоративный аккаунт.
- Исходящие запросы к ChatGPT/Whisper выполняются строго через корпоративный прокси `http://user150107:dx4a5m@102.129.178.65:6517` (переменная `CHATGPT_PROXY_URL`).
- Storage (S3 с SSE или шифрованный диск) соответствует 00‑Core §9 (шифрование, retention, контроль доступа).
- Записи звонков Bitrix24 доступны минимум 90 дней.

3.4. Ограничения
- Бейч Bitrix24 ≤ 50, rate limit 2 rps/приложение — требуется бэкофф и очереди.
- Whisper: файл ≤ 25 МБ / 15 минут; длинные записи нарезаются, результаты агрегируются.
- Период выгрузки по умолчанию фиксирован в 60 дней; изменение требует CR.

4. Заинтересованные стороны и роли
| Роль | Ответственность | Участие |
| --- | --- | --- |
| Product Owner (Операции / Call Center) | Приоритизация, согласование периода, приёмка отчётов | Approve |
| DataOps / Интеграции (Owner SRS) | Разработка/поддержка пайплайна, мониторинг, внедрение runbook | Accountable |
| Backend (MW) | Поддержка API, очередей, интеграции с БД | Consult |
| QA Analyst | План тестирования, выборочный контроль качества текстов | Responsible |
| Security Officer | Контроль доступа к ПДн, аудит | Consult |
| On-call инженер | Реакция на алерты, следование runbook | Responsible |

5. Окружения
- DEV — интеграционные тесты с моками Bitrix24/Whisper, локальные шифрованные storage; обезличенные данные.
- TEST — подключение к Bitrix24 sandbox; проверка отказоустойчивости и ретраев.
- UAT — ограниченный период (7 дней), реальная интеграция, подтверждение KPI и отчёта.
- PROD — основная выгрузка 60 дней, расписание cron (еженедельно/ежемесячно). Конфиги (`.env`, feature flags) отделены по окружениям; секреты в Secret Manager, ротация ≤ 90 дней.

6. Архитектура и поток данных
6.1. Компоненты
- Scheduler (`cron`, ручной запуск) — инициирует задачу `call_export` c параметрами периода и флагов.
- MW Orchestrator (FastAPI + worker) — управляет заданиями, хранит state в PostgreSQL, публикует события в очередь.
- Bitrix24 Client — REST wrapper с экспоненциальным бэкоффом (5/15/30/60/120 c), уважает rate limit, пишет статистику лимитов.
- Storage Adapter — сохраняет файлы в `exports/<period>/raw|transcripts|summary|reports`, применяет контрольные суммы и шифрование.
- Speech-to-Text Adapter — интегрируется с Whisper; выполняет нарезку длинных файлов, параллельную отправку (до 10 потоков), обработку ошибок и повторов.
- Reporter — формирует CSV (`registry/calls_<from>_<to>.csv`) и отчёты (`reports/summary_<period>.md`/`.pdf`) на базе шаблонов.
- QA Module — выборочная проверка 50 файлов, сверка длительностей, формирует QA-отчёт в логах/дашборде.

6.2. Поток выполнения (пошагово)
1. Инициация run — пользователь/cron вызывает `/tasks/call_export` (или CLI), передавая `period_from`, `period_to`, `generate_summary`.
2. MW создаёт запись в `call_exports` со статусом `pending`, генерирует `run_id`, публикует задания загрузки.
3. Bitrix24 Client постранично получает звонки, фильтрует только с записями; каждую запись помещает в очередь скачивания.
4. Downloader загружает аудио в `raw/<YYYY/MM/DD>/call_<call_id>_<record_id>.mp3`, вычисляет `checksum_sha256`, обновляет `call_records`.
5. Speech-to-Text Adapter сегментирует аудио > 15 мин, отправляет в Whisper, собирает финальный текст, определяет `language`, рассчитывает стоимость (`minutes_rounded_up * price_per_minute`).
6. Готовые транскрипты пишутся в `transcripts/call_<call_id>.txt` (UTF-8, BOM отсутствует) с заголовком метаданных (call_id, direction, participants, duration, language).
7. При включённом `generate_summary` создаётся `summary/call_<call_id>.md` и теги, путь сохраняется в CSV.
8. Reporter ведёт потоковую запись CSV: каждая завершённая запись добавляет строку; при ошибках фиксируется `status`, `error_code`, `retry_count`.
9. По завершении очереди создаётся отчёт `summary_<period>.md`: агрегаты длительности/стоимости, список пропусков, прогноз расходов, время выполнения, QA-сводка.
10. Run закрывается: статус `completed` либо `error`; повторный запуск с тем же периодом обновляет только отсутствующие записи (идемпотентность по хэшу `period + call_id + record_id`).

6.3. Хранилище файлов
- `exports/<period>/raw/YYYY/MM/DD/call_<call_id>_<record_id>.mp3` — исходные аудио, retention 90 дней.
- `exports/<period>/transcripts/call_<call_id>.txt` — текст, retention 180 дней.
- `exports/<period>/summary/call_<call_id>.md` — опциональные саммари (feature flag).
- `exports/<period>/reports/summary_<period>.md` + `.pdf` (по требованию).
- `exports/<period>/registry/calls_<from>_<to>.csv` — реестр (UTF-8, `;` разделитель).
- `exports/<period>/logs/call_export_<timestamp>.jsonl` — пошаговые логи (JSONL, маскирование ПДн).

7. Артефакты и форматы
7.1. CSV-реестр `calls_<from>_<to>.csv`
| Поле | Тип | Обязательность | Описание |
| --- | --- | --- | --- |
| call_id | string | yes | ID звонка Bitrix24 |
| record_id | string | yes | ID записи аудио |
| datetime_start | datetime (RFC3339Z) | yes | Время начала звонка |
| direction | enum (`inbound`/`outbound`) | yes | Направление |
| from | string | yes | Номер инициатора (маскируется при экспорте) |
| to | string | yes | Номер адресата (маскируется) |
| duration_sec | integer | yes | Длительность по Bitrix24 |
| recording_url | string | yes | Источник аудио (masked) |
| transcript_path | string | yes | Относительный путь к тексту |
| transcription_cost | decimal(10,2) + currency_code | yes | Стоимость, currency по тарифу |
| language | string (ISO 639-1) | yes | Определённый язык |
| status | enum (`completed`, `error`, `missing_audio`) | yes | Статус обработки |
| error_code | string | no | Код ошибки (для `error`) |
| retry_count | integer | yes | Количество повторов |
| summary_path | string | no | Путь к саммари (если включено) |
| tags | string[] (serialized) | no | Теги, разделитель `|` |

7.2. Формат транскрипта `transcripts/call_<call_id>.txt`
```
CALL_ID: <call_id>
RECORD_ID: <record_id>
START: <datetime_start>
DIRECTION: <direction>
DURATION_SEC: <duration_sec>
LANGUAGE: <iso639-1>
---
<Диалог в формате>
[Оператор]: ...
[Клиент]: ...
```

7.3. Отчёт `summary_<period>.md`
- Заголовок: период, дата генерации, run_id, actor.
- Агрегаты: общее число звонков, успешных/ошибок, длительность (мин, часы), стоимость (RUB/USD), доля покрытия.
- Блок «Пропуски»: таблица с call_id, record_id, причиной ошибки.
- Блок «Расходы»: фактическая стоимость, прогноз следующего периода, бюджет, алерт при > 20% отклонении.
- Блок QA: результаты выборочной проверки 50 файлов (ok/issue), комментарии.

8. Модель данных MW
8.1. Таблица `call_exports`
| Поле | Тип | Ограничения | Описание |
| --- | --- | --- | --- |
| id | uuid | PK | Уникальный идентификатор запуска |
| period_from | timestamptz | not null | Начало периода (UTC) |
| period_to | timestamptz | not null | Конец периода (UTC) |
| status | enum (`pending`, `running`, `completed`, `error`, `cancelled`) | not null, индекс | Текущее состояние run |
| started_at | timestamptz | not null | Время старта |
| finished_at | timestamptz | null | Время завершения |
| actor | text | not null | Инициатор (user/service) |
| total_calls | integer | not null default 0 | Количество звонков в run |
| processed_calls | integer | not null default 0 | Завершённых записей |
| error_calls | integer | not null default 0 | Записей в ошибке |
| total_duration_sec | bigint | not null default 0 | Суммарная длительность |
| total_cost | numeric(12,2) | not null default 0 | Стоимость в основной валюте |
| cost_currency | char(3) | not null default 'USD' | Валюта стоимости |
| metadata | jsonb | not null default '{}' | Доп. параметры (флаги, concurrency) |
Индексы: `(status)`, `(period_from, period_to)`, `btree(period_from)` для выборок по периоду. Уникальный индекс `unique(period_from, period_to, actor)` предотвращает параллельный запуск идентичных задач.

8.2. Таблица `call_records`
| Поле | Тип | Ограничения | Описание |
| --- | --- | --- | --- |
| id | uuid | PK | Уникальный идентификатор записи |
| call_export_id | uuid | FK → call_exports(id) on delete cascade | Связанный run |
| call_id | text | not null | ID звонка Bitrix24 |
| record_id | text | not null | ID аудиозаписи |
| status | enum (`pending`, `downloading`, `transcribing`, `completed`, `error`, `missing_audio`) | not null | Статус обработки |
| direction | text | not null | Направление звонка |
| datetime_start | timestamptz | not null | Время начала |
| duration_sec | integer | not null | Длительность |
| recording_url | text | not null | Исходная ссылка (masked в выгрузке) |
| storage_path | text | not null | Путь к аудио в storage |
| checksum_sha256 | text | not null | Контрольная сумма |
| transcript_path | text | null | Путь к тексту |
| summary_path | text | null | Путь к саммари |
| tags | text | null | Сериализованные теги |
| language | char(2) | null | ISO 639-1 |
| cost_value | numeric(10,2) | null | Стоимость |
| cost_currency | char(3) | null default 'USD' | Валюта |
| retry_count | integer | not null default 0 | Повторные попытки |
| last_error_code | text | null | Код последней ошибки |
| last_error_message | text | null | Текст ошибки (PII-маскирование) |
| updated_at | timestamptz | not null default now() | Обновление статуса |
Уникальные ограничения: `unique(call_export_id, call_id, record_id)`. Индексы: `(status, updated_at)` для мониторинга, `(call_id, record_id)` для идемпотентности, `GIN(tags)` при включённых тегах.

8.3. Логи и DLQ
- `integration_log` используется для журналирования исходящих запросов (Bitrix24, Whisper) с `correlation_id = run_id`.
- Ошибки, превысившие окно ретраев, попадают в DLQ (`call_export_dlq`) с payload run_id + call_id + stage + error.

9. Интеграции и внешние зависимости
9.1. Bitrix24 телефония (API‑Contracts v1.1.3)
- Методы: `telephony.callList` (постранично), `telephony.recording.get` для получения ссылки.
- Авторизация: webhook token (stored in Secret Manager).
- Ограничения: batch ≤ 50, 2 rps; при `429` включается режим `low_rate` (0.5 rps) в течение 15 минут.
- Ответы валидируются по схемам 00‑Core §2 (JSON, UTF-8), все поля приводятся к нижнему регистру ключей.

9.2. Whisper / Speech-to-Text
- API совместим с OpenAI Whisper (`audio/transcriptions`). Ограничение файла — 25 МБ, 15 минут.
- Параллельность до 10 запросов, контролируется параметром `TRANSCRIBE_CONCURRENCY`.
- Ошибки 5xx/timeout → ретраи 10/30/60 секунд, далее DLQ.

9.3. Storage
- S3 с SSE (`AES-256`), приватный bucket; либо локальный каталог на шифрованном диске (LUKS) с ограниченным доступом.
- Права: роль `call-export-writer` (write), `call-export-reader` (read-only), `call-export-admin` (lifecycle).

10. Функциональные требования (FR)
- FR-INGEST-001. MW должен создавать run в `call_exports` с уникальным `run_id` и статусом `pending` при запуске задачи.
- FR-INGEST-010. Клиент Bitrix24 обязан выгружать все звонки за период, учитывая пагинацию и фильтры по `start_time`.
- FR-DOWNLOAD-001. Скачивание аудио сохраняет файл в storage, вычисляет `checksum_sha256`, обновляет `call_records.status = 'downloading' → 'transcribing'`.
- FR-DOWNLOAD-010. При 5 неудачных попытках загрузки запись переводится в `missing_audio`, фиксируется `last_error_code` и попадает в отчёт.
- FR-TRANSCRIBE-001. Транскрипция должна обеспечивать ≥ 98% успешных попыток; язык определяется автоматически и записывается в `call_records.language`.
- FR-TRANSCRIBE-010. Стоимость рассчитывается по тарифу сервиса с округлением минут вверх и сохраняется в `cost_value`, `cost_currency`.
- FR-CSV-001. Каждая завершённая запись добавляется в CSV; файл валиден (UTF-8, `;` разделитель) и открывается в Excel/Google Sheets без ошибок.
- FR-CSV-010. CSV содержит все обязательные поля (§7.1); отсутствующие транскрипты заполняются `status = error|missing_audio`.
- FR-REPORT-001. Отчёт `summary_<period>.md` формируется автоматически и включает агрегаты (§7.3), список пропусков, QA-выборку.
- FR-SUMMARY-001. При `generate_summary = true` создаются файлы саммари, пути записываются в `summary_path`; для ошибок саммари не создаются.
- FR-IDEMP-001. Повторный запуск с тем же периодом не создаёт дублей: существующие записи обновляются только если `status != completed` или отсутствует файл.
- FR-IDEMP-010. `Idempotency-Key` для API запуска = `hash(period_from + period_to + actor)`; повтор запроса возвращает текущий статус run.
- FR-OBS-001. Все этапы логируются в JSONL с `correlation_id = run_id`, `stage`, `duration_ms`.
- FR-QA-001. QA Module выбирает минимум 50 записей, проверяет читабельность, фиксирует результат в отчёте и метрике `call_export_qa_checked_total`.

11. Конфигурация и управление
- ENV переменные: `B24_TOKEN`, `WHISPER_API_KEY`, `EXPORT_SUMMARY_ENABLED`, `TRANSCRIBE_CONCURRENCY`, `CALL_EXPORT_CRON`.
- Feature flags: `EXPORT_SUMMARY_ENABLED` (вкл./выкл. саммари), `EXPORT_LOW_RATE_MODE` (принудительное ограничение rps).
- Scheduler хранится в `call_exports.metadata` с полем `trigger` (`cron`, `manual`).
- Идемпотентность — через таблицу `idempotency_key` (00‑Core §2.5), TTL 72 часа.

12. Нефункциональные требования (NFR)
- NFR-PERF-001. Параллельная обработка до 10 звонков; run 60 дней завершается ≤ 6 часов (p95) при объёме 9 000 минут.
- NFR-CAP-001. Система масштабируется до 20 000 минут/run без деградации (горизонтальное масштабирование воркеров).
- NFR-RETRY-001. Bitrix24 — 5 попыток (5/15/30/60/120 c), Whisper — 3 попытки (10/30/60 c), общий предел 24 часа.
- NFR-AVAIL-001. MW сервис доступен ≥ 99,5%; восстановление run после сбоя ≤ 5 минут (перезапуск воркера повторно обрабатывает `pending` записи).
- NFR-STORAGE-001. Retention: raw аудио 90 дней, транскрипты/отчёты 180 дней, CSV 365 дней; по истечении выполняется архивирование или удаление (см. 00‑Core §9).
- NFR-COST-001. Система считает фактическую стоимость и сравнивает с прогнозом; алерт при превышении > 20%.
- NFR-COMPLIANCE-001. Все таймстемпы в UTC, соответствуют ISO‑8601/RFC‑3339.

13. Наблюдаемость и алерты
- Метрики Prometheus: `call_export_runs_total{status}`, `call_export_duration_seconds`, `call_transcripts_total{status}`, `call_transcription_minutes_total`, `call_export_cost_total`, `call_export_retry_total`, `call_export_qa_checked_total`.
- Алерты:
  - `call_exports{status="error"}` > 0 в течение 15 минут → severity `critical`, уведомление on-call.
  - `call_transcripts_total{status="error"}` / processed > 1% за 30 минут → severity `warning`.
  - `call_export_cost_total` > budget_threshold → severity `warning`, канал #call-texts.
  - Bitrix24 429 > 10 за 15 минут → переключение в `low_rate` и уведомление.
- Логи: JSON (PII маскирована), хранение ≥ 30 дней, архив 180 дней; обязательные поля — `timestamp`, `run_id`, `call_id`, `stage`, `duration_ms`, `error_code`.
- Трейсы: OpenTelemetry (`http.client` Bitrix24/Whisper, `task.call_export`); retention 7 дней.
- Дашборды (Grafana): «Call Export Overview», «Cost & Budget», «Retry & Error Rates», «QA Sample».

14. Безопасность и ПДн
- Аутентификация запуска: сервисные аккаунты с ограниченным scope; токены хранятся в Secret Manager, ротация ≤ 90 дней (см. threat model).
- Каналы связи: HTTPS/TLS 1.2+; внутренний трафик к storage — приватная сеть/VPN.
- Шифрование: storage с SSE (`AES-256`), локальные диски — LUKS; транскрипты и отчёты содержат ПДн, доступ только ролям `Call Center Analyst`, `Operations`.
- Маскирование: номера телефонов и ссылки в CSV/log маскируются (`+7***`), доступ к немаскированным данным — по отдельному запросу через runbook.
- Журналы аудита: события доступа и скачивания файлов фиксируются, передаются в SIEM; retention ≥ 180 дней.
- DR/BCP: бэкап БД и storage ежедневно; RPO ≤ 24 ч, RTO ≤ 4 ч.

15. DoD / Acceptance
- Пайплайн обрабатывает 60-дневный период: coverage ≥ 99%, отчёт и CSV соответствуют схемам (§7.1).
- QA-выборка из 50 файлов подтверждена, дефекты < 2% критичных, задокументированы.
- Алерты и дашборды настроены, on-call ознакомлен с runbook `docs/runbooks/call_export.md`.
- Runbook и data dictionary (`docs/data/call_registry_dictionary.md`) актуализированы и содержат сценарии инцидентов/структуру данных.
- Повторный запуск не создаёт дублей; идемпотентность проверена интеграционными тестами.
- Стоимость и длительность в отчёте совпадают с Bitrix24 в пределах KPI.
- Все секреты и доступы оформлены, аудит завершён Security Officer.

16. Приложения и ссылки
- PRD — Тексты звонков Bitrix24 v1.0.0.
- ONE-PAGER — «Тексты всех звонков за 60 дней из Bitrix24».
- 00‑Core — Синхронизация документации v1.3.1.
- API‑Contracts v1.1.3 (Bitrix24 телефония).
- ER Freeze v0.6.4.
- Runbook: docs/runbooks/call_export.md.
- Data Dictionary: docs/data/call_registry_dictionary.md.
