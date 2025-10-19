import { useCallback, useState } from 'react';
import { ChatKit, useChatKit, type StartScreenPrompt } from '@openai/chatkit-react';

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

  const chat = useChatKit({
    api: {
      async getClientSecret(existing?: unknown) {
        const existingSecret = extractExistingSecret(existing);

        if (existingSecret) {
          setLoadError(null);
          return existingSecret;
        }

        try {
          const response = await fetch('/api/chatkit/session', {
            method: 'POST',
          });

          if (!response.ok) {
            throw new Error('Не удалось получить клиентский токен');
          }

          const payload: unknown = await response.json();
          const secret = parseClientSecret(payload);
          setLoadError(null);
          return secret;
        } catch (error) {
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
