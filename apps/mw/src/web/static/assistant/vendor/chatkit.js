(function (global) {
  'use strict';

  const DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };

  async function requestSession() {
    const response = await fetch('/api/v1/chatkit/session', {
      method: 'POST',
      headers: DEFAULT_HEADERS,
      body: JSON.stringify({}),
    });

    if (!response.ok) {
      throw new Error(`Failed to request chatkit session: ${response.status}`);
    }

    return response.json();
  }

  function isPlainObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function normaliseWidgetAction(raw) {
    if (isPlainObject(raw) && typeof raw.type === 'string') {
      const result = {
        type: raw.type,
        payload: isPlainObject(raw.payload) ? raw.payload : {},
      };

      if (typeof raw.name === 'string' && raw.name.trim()) {
        result.name = raw.name.trim();
      }

      return result;
    }

    if (isPlainObject(raw) && typeof raw.action === 'string') {
      const actionName = raw.action.trim();
      if (!actionName) {
        return {
          type: 'tool.unknown',
          name: 'unknown',
          payload: {},
        };
      }

      const type = actionName.includes('.') ? actionName : `tool.${actionName}`;
      const [, suffix = actionName] = type.split('.', 2);

      return {
        type,
        name: suffix,
        payload: isPlainObject(raw.data) ? raw.data : {},
      };
    }

    return {
      type: 'tool.unknown',
      name: 'unknown',
      payload: {},
    };
  }

  async function sendWidgetAction(payload) {
    const normalisedPayload = normaliseWidgetAction(payload);

    const response = await fetch('/api/v1/chatkit/widget-action', {
      method: 'POST',
      headers: {
        ...DEFAULT_HEADERS,
        'x-chatkit-widget-action': 'open',
      },
      body: JSON.stringify(normalisedPayload),
    });

    if (!response.ok) {
      throw new Error(`Failed to send widget action: ${response.status}`);
    }

    return response.json();
  }

  class ChatKitWidget {
    constructor(options) {
      this.container = options?.container ?? null;
      this.onReady = options?.onReady ?? (() => {});
      this.onError = options?.onError ?? (() => {});
      this.session = null;
    }

    async initialize() {
      try {
        this.session = await requestSession();
        await sendWidgetAction({ action: 'widget_opened' });
        this.render();
        this.onReady(this.session);
      } catch (error) {
        this.onError(error);
        throw error;
      }
    }

    render() {
      if (!this.container) {
        throw new Error('ChatKitWidget requires a container element');
      }

      this.container.innerHTML = '';

      const frame = document.createElement('iframe');
      frame.src = 'about:blank';
      frame.title = 'MasterMobile Assistant';
      frame.setAttribute('aria-live', 'polite');
      frame.style.width = '100%';
      frame.style.height = '100%';
      frame.style.border = '0';
      frame.style.background = 'transparent';

      const doc = frame.contentDocument;
      if (doc) {
        doc.open();
        doc.write(`
          <!DOCTYPE html>
          <html lang="ru">
            <head>
              <meta charset="utf-8" />
              <style>
                body {
                  margin: 0;
                  font-family: 'Inter', system-ui, sans-serif;
                  background: #0f172a;
                  color: #e2e8f0;
                }
                .frame {
                  display: flex;
                  flex-direction: column;
                  height: 100vh;
                  padding: 20px;
                }
                header {
                  font-weight: 600;
                  margin-bottom: 12px;
                }
                section {
                  flex: 1 1 auto;
                  border-radius: 12px;
                  background: rgba(30, 41, 59, 0.65);
                  border: 1px solid rgba(148, 163, 184, 0.2);
                  padding: 16px;
                  overflow-y: auto;
                }
                footer {
                  margin-top: 16px;
                  display: flex;
                  gap: 12px;
                }
                footer input {
                  flex: 1;
                  background: rgba(15, 23, 42, 0.95);
                  border: 1px solid rgba(148, 163, 184, 0.2);
                  border-radius: 999px;
                  padding: 12px 16px;
                  color: inherit;
                }
                footer button {
                  background: linear-gradient(135deg, #22d3ee, #6366f1);
                  border: none;
                  border-radius: 999px;
                  padding: 12px 24px;
                  color: #0f172a;
                  font-weight: 600;
                  cursor: pointer;
                }
                footer button:disabled {
                  opacity: 0.5;
                  cursor: not-allowed;
                }
              </style>
            </head>
            <body>
              <div class="frame">
                <header>Чат ассистента</header>
                <section id="chat-log">
                  <p>Сессия: ${this.session?.client_secret ? 'получена' : 'нет данных'}</p>
                </section>
                <footer>
                  <input id="chat-input" placeholder="Напишите сообщение" />
                  <button id="chat-send">Отправить</button>
                </footer>
              </div>
              <script>
                const sendButton = document.getElementById('chat-send');
                const input = document.getElementById('chat-input');
                const log = document.getElementById('chat-log');

                async function sendMessage() {
                  if (!input.value.trim()) {
                    return;
                  }

                  const message = input.value.trim();
                  input.value = '';
                  input.focus();

                  const entry = document.createElement('p');
                  entry.textContent = 'Вы: ' + message;
                  log.appendChild(entry);

                  try {
                    const response = await fetch('/api/v1/chatkit/messages', {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json',
                        Accept: 'application/json',
                      },
                      body: JSON.stringify({ message }),
                    });

                    const reply = document.createElement('p');
                    if (response.ok) {
                      const data = await response.json();
                      reply.textContent = 'Ассистент: ' + (data.reply || '[пусто]');
                    } else {
                      reply.textContent = 'Ошибка: ' + response.status;
                    }
                    log.appendChild(reply);
                  } catch (err) {
                    const fail = document.createElement('p');
                    fail.textContent = 'Ошибка отправки: ' + err.message;
                    log.appendChild(fail);
                  }
                }

                sendButton?.addEventListener('click', sendMessage);
                input?.addEventListener('keydown', (event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage();
                  }
                });
              </script>
            </body>
          </html>
        `);
        doc.close();
      }

      this.container.appendChild(frame);
    }
  }

  global.ChatKitWidget = ChatKitWidget;
})(typeof window !== 'undefined' ? window : globalThis);
