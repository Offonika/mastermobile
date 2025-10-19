# MasterMobile Assistant Backend

FastAPI-микросервис для ONE-PAGER — Ассистент сотрудников MasterMobile.

## Основные эндпоинты (MVP v1)
- `POST /api/chatkit/session` — выдаёт временный `client_secret` для фронтенда.
- `POST /api/vector-store/upload` — загружает PDF/DOCX в Vector Store с метаданными.

⚙️ В следующих итерациях добавим Guardrails, метрики и интеграцию с Bitrix24 OAuth.
