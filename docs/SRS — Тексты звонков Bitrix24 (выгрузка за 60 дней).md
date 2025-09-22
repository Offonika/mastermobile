SRS — «Тексты звонков Bitrix24 (выгрузка за 60 дней)»

Версия: v1.0.0 (синхронизировано с 00-Core v1.3.1, API-Contracts v1.1.3)
Дата: 19.09.2025
Владелец продукта: Операции / Call Center
Основано на: ONE-PAGER — «Тексты всех звонков за 60 дней из Bitrix24», 00-Core v1.3.1 (Core-API-Style, Metrics & Alerts, Retention, Envs/Flags), API-Contracts v1.1.3 (Bitrix24 интеграции), ER Freeze v0.6.4

1) Резюме

Регулярная выгрузка всех звонков Bitrix24 за последние 60 дней, автоматическое распознавание речи и выпуск артефактов: 1) папка текстов (.txt по звонку), 2) CSV-реестр, 3) отчёт по длительности/стоимости. Поддерживается идемпотентность, контроль качества и прозрачные затраты. Пайплайн в MW-контуре: список звонков → скачивание аудио → распознавание (Whisper) → тексты/CSV → отчёт/метрики.

2) Цели и KPI
2.1 Цели v1 (2 недели)

100% звонков за выбранный период (по умолчанию T-60…T0) попадают в обработку.

Читабельные тексты для ≥ 98% успешно скачанных аудио.

CSV-реестр с полями: datetime_start, direction, from, to, duration_sec, recording_url, transcript_path, transcription_cost, language, status.

Отчёт с суммарной длительностью (мин) и стоимостью (RUB/USD).

2.2 KPI

Покрытие транскриптов: ≥ 99% звонков с доступным аудио.

Ошибки > 24 ч: ≤ 1% (алерт).

Расхождение длительности (CSV vs Bitrix24): ≤ 0,5%.

Дубли транскриптов: 0 на 1000.

SLA: период 60 дней обрабатывается ≤ 6 ч при параллелизме 10 и ~9 000 мин.

3) Scope, допущения и ограничения

In scope (v1): B24 Telephony REST; скачивание mp3/wav; STT Whisper (или эквивалент); тексты UTF-8; CSV; отчёт (md/pdf); опц. саммари/теги; идемпотентность (call_id, record_id, period).

Out of scope (v1): real-time поток; углублённая аналитика контента; BI/ChatGPT-интеграция (будут шаблоны); очистка > 90 дней.

Допущения: доступ к B24 (read); квоты STT; storage соответствует 00-Core §9; записи в B24 доступны ≥ 90 дней.

Ограничения: rate-limit B24 (нужен backoff); ограничения Whisper (размер/длительность — сегментация); базовый период 60 дней.

4) Управление изменениями

Decision owner: Product (Операции/Call Center), SLA решений — 1 рд.

CR обязателен при смене периода, STT, отклонении бюджета > ±10%, смене storage.

Go/No-Go: доступы B24, успешный тест на 5 звонков, подтверждённый отчёт/retention.

Конфигурация пайплайна — в git (YAML), изменения через PR.

5) Архитектура и поток

Компоненты: Scheduler → MW Orchestrator (FastAPI+worker; PG: call_exports, call_records) → B24 Client (429/5xx backoff) → Storage Adapter (S3 SSE / локально) → STT Adapter (Whisper; чанкинг > 15 мин) → Reporter (CSV+md/pdf) → QA Module (выборка, сверка длительностей).

Шаги:

Период (default today-60d…today), флаги (generate_summary).

Запрос звонков (батчи, start_time desc), state сохранён.

Скачивание record_url (≤ 5 ретраев).

Сохранение raw/…/call_<id>.mp3, checksum в БД.

STT → transcripts/call_<id>.txt (UTF-8, без BOM), language.

Подсчёт transcription_cost = minutes_rounded_up × rate.

Потоковая запись CSV registry/calls_<from>_<to>.csv.

Итоговый отчёт (минуты, стоимость, ошибки, прогноз).

(Опц.) Саммари/теги → summary/call_<id>.md + поля в CSV.

Run = completed; повтор по тому же периоду без дублей.

6) Артефакты и данные

Каталоги: exports/<period>/{raw,transcripts,summary,reports,registry,logs}.
CSV (UTF-8, ;):
datetime_start;direction;from;to;duration_sec;recording_url;transcript_path;transcription_cost;language;status;summary_path;error_code;retry_count
Отчёт: reports/summary_<period>.md (+ PDF).
Логи: logs/call_export_<ts>.jsonl (JSON: event, call_id, stage, duration_ms, error_code, correlation_id).
PG:

call_exports(run_id, period_from, period_to, status, started_at, finished_at, actor)

call_records(run_id, call_id, record_id, duration_sec, recording_url, transcript_path, checksum, cost, language, status, error_message, attempts)

7) Функциональные требования (эпики → DoD)

F1 Импорт B24: пагинация/фильтры корректны; повтор без дублей; лог лимитов.
F2 Скачивание/хранение: 100% файлов доступны; checksum стабилен; битые ссылки → missing_audio.
F3 STT: ≥ 98% успешных транскриптов; language заполнен; ошибки ретраятся и попадают в отчёт.
F4 Тексты/CSV: .txt с шапкой-метаданными и телом; CSV валиден и открывается в Excel/GS.
F5 Отчёт/стоимость: минуты/стоимость; расхождение длительностей ≤ 0,5%; список исключений.
F6 Саммари/теги (опц.): при флаге — файлы саммари + поля summary_path/tags в CSV.
F7 Идемпотентность: повтор периода не создаёт дублей; догрузка пропусков; Idempotency-Key = hash(period + call_id + record_id).

8) Нефункциональные требования

Объём: 60 дней ≈ 9 000 мин; допуск до 20 000 мин/run.

Производительность: ≤ 6 ч (p95) при concurrency=10.

Ретраи: B24 — 5 (5/15/30/60/120 c); STT — 3 (10/30/60 c).

Retention: raw 90д, transcripts/reports 180д, CSV 365д (00-Core §9).

Стоимость: rate Whisper $0.006/мин; 9 000 мин → ~$54; бюджет-алерт > 20%.

Доступность: MW ≥ 99,5%; восстановление с чекпоинта ≤ 5 мин.

Масштабирование: конфигами (concurrency, feature-flags).

9) Наблюдаемость и алерты

Метрики (Prometheus):
call_export_runs_total{status}, call_transcripts_total{status}, call_export_duration_seconds, call_transcription_minutes_total, call_export_cost_total, call_export_retry_total.

Алерты:

run_status=error > 15 мин — crit.

error_rate > 1%/30 мин — warn.

cost_total > budget_threshold — warn.

b24_429 > 10/15 мин — warn, включить low-rate.

Логи: JSON с correlation_id; ПДн маскируются.
Дашборды: Grafana — статусы, длительность, стоимость; QA-панель.

10) Безопасность и ПДн (00-Core)

Auth: сервисные учётки, токены в Secret Manager, ротация ≤ 90 дн.

Сеть: исходящие только к B24 и STT; storage в приватной сети.

Шифрование: TLS 1.2+; SSE (AES-256) на storage.

ПДн: доступ к транскриптам — Call Center Analyst, Operations; аудит скачиваний.

Retention: raw 90д / transcripts 180д / CSV 365д — затем удаление.

DR/BCP: бэкап storage/БД ежедневно; RPO ≤ 24 ч, RTO ≤ 4 ч.

11) Тестирование и QA

Unit/Integration: моки B24/STT; идемпотентность; ретраи; timeouts.

Smoke: 5 звонков — артефакты/отчёт ок.

Regression: 2 дня (~300 звонков) — покрытие ≥ 99%, время измерено.

QA-выборка: 50 файлов — читабельность/язык ок.

Сверка длительности: CSV vs B24 ≤ 0,5%.

Саммари (если включены): 10 звонков — адекватность, без лишних ПДн.

Negative: 404 запись → missing_audio; timeout STT → повтор; повторный run — без дублей.

Acceptance: все тесты зелёные; отчёт доставлен; алерты и дашборды включены; playbook готов.

12) План запуска и эксплуатации

Подготовка доступов (B24/STT/storage) → Dry-run 7 дней (QA 50 файлов) → Prod-run 60 дней (отчёт ≤ 24 ч после старта) → регулярный cron (еженед./ежемес.). Комм-канал: #call-texts.

13) Роли и доступы

PO (Операции/Call Center), Data Engineer, QA Analyst, Security Officer; Stakeholders: Продажи, Аналитики, Операторы. Доступы: B24 API (read), STT key, S3, логи (RO), Grafana.

14) Риски и меры

401/403 B24 (ротация токена), 429 (адаптивный rate-limit), утечки ПДн (RBAC, шифр., аудит), перерасход (предварительный расчёт, бюджет-алерт), длинные звонки (чанкинг), шум (альт. модели), переполнение диска (мониторинг, авто-очистка).

15) Критерии приёмки (DoD)

Run 60 дней завершён; coverage ≥ 99%; CSV валиден; расхождение длительностей ≤ 0,5%; стоимость корректна; дублей нет; QA-выборка (50) подтверждена; алерты/дашборды активны; документация обновлена.

16) Приложения и ссылки

A1. Шаблон промпта ChatGPT (будет в runbook).
A2. Якоря OpenAPI B24 Telephony — см. /openapi.yaml (b24.telephony.calls.*).
A3. Runbook: docs/runbooks/call_export.md (добавить при реализации).
A4. CSV Data Dictionary: docs/specs/call_registry_schema.yaml (добавить при реализации).

Changelog: v1.0.0 (19.09.2025) — первый релиз SRS; синхрон с 00-Core v1.3.1, API-Contracts v1.1.3, ER v0.6.4.
