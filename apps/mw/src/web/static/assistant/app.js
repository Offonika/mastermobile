import * as ChatKit from './vendor/chatkit.js';

const LOG_PREFIX = '[assistant]';

function logInfo(message, details) {
  if (details !== undefined) {
    console.info(`${LOG_PREFIX} ${message}`, details);
    return;
  }
  console.info(`${LOG_PREFIX} ${message}`);
}

function logError(message, error) {
  if (error) {
    console.error(`${LOG_PREFIX} ${message}`, error);
    return;
  }
  console.error(`${LOG_PREFIX} ${message}`);
}

function showFallback(message, element, container) {
  if (element) {
    element.textContent = message;
    element.classList.add('error');
    return element;
  }

  const fallback = document.createElement('div');
  fallback.id = 'chat-loading';
  fallback.className = 'loading error';
  fallback.textContent = message;
  if (container) {
    container.appendChild(fallback);
  }
  return fallback;
}

async function initialiseAssistant() {
  const container = document.getElementById('my-chat');
  const loading = document.getElementById('chat-loading');

  if (!container) {
    logError('Не найден контейнер для ассистента');
    return;
  }

  let fallback = loading;
  let control;

  try {
    logInfo('Монтируем ChatKit виджет');
    control = ChatKit.mount(container, {
      onReady: () => {
        logInfo('Виджет отрисован, получаем client_secret');
        if (fallback) {
          fallback.textContent = 'Получаем доступ к ассистенту…';
          fallback.classList.remove('error');
        }
      },
      onError: (error) => {
        logError('Ошибка внутри виджета', error);
        fallback = showFallback('Ошибка инициализации ассистента', fallback, container);
      },
    });
  } catch (error) {
    logError('Не удалось подключить ChatKit', error);
    showFallback('Ошибка инициализации ассистента', fallback, container);
    return;
  }

  if (!control) {
    logError('Контроллер ассистента не инициализирован');
    showFallback('Ошибка инициализации ассистента', fallback, container);
    return;
  }

  try {
    logInfo('Запрашиваем сессию через /api/v1/chatkit/session');
    const response = await fetch('/api/v1/chatkit/session', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({}),
    });

    if (!response.ok) {
      throw new Error(`Unexpected status ${response.status}`);
    }

    const payload = await response.json();
    const clientSecret = payload?.client_secret;

    if (typeof clientSecret !== 'string' || clientSecret.length === 0) {
      throw new Error('Пустой client_secret в ответе');
    }

    logInfo('client_secret получен, настраиваем виджет');
    control.setOptions({ client_secret: clientSecret });
    if (fallback) {
      fallback.remove();
    }
  } catch (error) {
    logError('Ошибка получения client_secret', error);
    showFallback('Ошибка инициализации ассистента', fallback, container);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  logInfo('Инициализация ассистента');
  void initialiseAssistant();
});
