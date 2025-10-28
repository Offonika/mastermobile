# MasterMobile Assistant Frontend

Страница локального приложения Bitrix24, которая отображает виджет ChatKit c русской локализацией, стартовыми подсказками и запросом client_secret через backend MasterMobile.

## 🚀 Быстрый старт

```bash
cd frontend
npm install
npm run dev
```

Приложение доступно по адресу <http://localhost:5173> и проксирует вызовы `/api` к backend (<http://localhost:8000>).

## 🧩 Структура

- `src/App.tsx` — контейнер страницы Bitrix24 и оформление.
- `src/components/B24Assistant.tsx` — интеграция ChatKit (получение `client_secret`, приветствие, подсказки).
- `src/main.tsx` — точка входа React/Vite.

Стили оформлены в тёмной теме для встраивания во фрейм Bitrix24.
