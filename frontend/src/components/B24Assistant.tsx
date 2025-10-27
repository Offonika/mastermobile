import { useCallback, useEffect, useState } from 'react';
import { ChatKit, useChatKit, type StartScreenPrompt } from '@openai/chatkit-react';

import { assistantDebug } from '../utils/debug';
import styles from './B24Assistant.module.css';

const prompts: StartScreenPrompt[] = [
  {
    label: 'Возвраты',
    prompt: 'Найди в документах раздел про возвраты',
    icon: 'search',
  },
  {
    label: 'Гарантия',
    prompt: 'Покажи пункты гарантийных обязательств',
    icon: 'circle-question',
  },
  {
    label: 'Инструкции',
    prompt: 'Собери чек-лист действий при проблемах с доставкой',
    icon: 'document',
  },
];

function normaliseError(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'string') {
    return error;
  }

  return 'Не удалось загрузить чат. Попробуйте обновить страницу.';
}

function extractExistingSecret(candidate?: unknown) {
  if (typeof candidate === 'string' && candidate.length > 0) {
    return candidate;
  }

  if (
    candidate &&
    typeof candidate === 'object' &&
    'client_secret' in candidate &&
    typeof (candidate as { client_secret?: unknown }).client_secret === 'string'
  ) {
    return (candidate as { client_secret: string }).client_secret;
  }

  return null;
}

function parseClientSecret(payload: unknown) {
  if (
    payload &&
    typeof payload === 'object' &&
    'client_secret' in payload &&
    typeof (payload as { client_secret?: unknown }).client_secret === 'string'
  ) {
    return (payload as { client_secret: string }).client_secret;
  }

  throw new Error('Некорректный ответ при получении client_secret');
}

export default function B24Assistant() {
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    assistantDebug('Инициализация ChatKit для Bitrix24 ассистента');
  }, []);

  const chat = useChatKit({
    api: {
      async getClientSecret(existing?: unknown) {
        const existingSecret = extractExistingSecret(existing);

        if (existingSecret) {
          assistantDebug('Используем уже имеющийся client_secret');
          setLoadError(null);
          return existingSecret;
        }

        assistantDebug('Запрашиваем client_secret у API /api/v1/chatkit/session');
        try {
          const response = await fetch('/api/v1/chatkit/session', {
            method: 'POST',
          });

          assistantDebug('Ответ от /api/v1/chatkit/session получен', {
            ok: response.ok,
            status: response.status,
          });

          if (!response.ok) {
            throw new Error('Не удалось получить клиентский токен');
          }

          const payload: unknown = await response.json();
          const secret = parseClientSecret(payload);
          assistantDebug('client_secret успешно получен от API');
          setLoadError(null);
          return secret;
        } catch (error) {
          assistantDebug('Ошибка при запросе client_secret', error instanceof Error ? error.message : error);
          setLoadError(normaliseError(error));
          throw error;
        }
      },
    },
    locale: 'ru-RU',
    startScreen: {
      greeting: 'Здравствуйте! Задайте вопрос или загрузите документ.',
      prompts,
    },
    theme: {
      colorScheme: 'dark',
      radius: 'round',
      density: 'compact',
    },
    widgets: {
      async onAction(action) {
        const payload = action?.payload && typeof action.payload === 'object' ? action.payload : {};

        try {
          assistantDebug('Отправляем событие виджета', {
            type: action?.type,
            hasPayload: Object.keys(payload).length > 0,
          });
          const response = await fetch('/api/v1/chatkit/widget-action', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              ...action,
              payload,
            }),
          });

          assistantDebug('Ответ от /api/v1/chatkit/widget-action получен', {
            ok: response.ok,
            status: response.status,
          });

          if (!response.ok) {
            throw new Error('Не удалось обработать действие виджета');
          }

          setLoadError(null);
        } catch (error) {
          assistantDebug('Ошибка при обработке события виджета', error instanceof Error ? error.message : error);
          console.error('Не удалось обработать действие виджета', error);
          setLoadError('Не удалось обработать действие виджета. Попробуйте обновить страницу.');
          throw error;
        }
      },
    },
  });

  const handleRetry = useCallback(() => {
    setLoadError(null);
    window.location.reload();
  }, []);

  return (
    <div className={styles.wrapper}>
      <ChatKit control={chat.control} className={styles.chat} />
      {loadError && (
        <div className={styles.errorOverlay}>
          <div>{loadError}</div>
          <button type="button" className={styles.retryButton} onClick={handleRetry}>
            Попробовать снова
          </button>
        </div>
      )}
    </div>
  );
}
