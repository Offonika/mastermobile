const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  Accept: 'application/json',
};

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

async function sendWidgetAction(payload, options = {}) {
  const normalisedPayload = normaliseWidgetAction(payload);
  const headers = { ...DEFAULT_HEADERS, ...(options.headers ?? {}) };

  const response = await fetch('/api/v1/chatkit/widget-action', {
    method: 'POST',
    headers,
    body: JSON.stringify(normalisedPayload),
  });

  if (!response.ok) {
    throw new Error(`Failed to send widget action: ${response.status}`);
  }

  return response.json();
}

class ChatKitWidget {
  constructor({ onReady, onError } = {}) {
    this.container = null;
    this.frame = null;
    this.frameDocument = null;
    this.session = {};
    this.elements = {
      input: null,
      sendButton: null,
      log: null,
      status: null,
    };
    this.boundSendHandler = null;
    this.boundKeyHandler = null;
    this.onReady = typeof onReady === 'function' ? onReady : () => {};
    this.onError = typeof onError === 'function' ? onError : (error) => {
      console.error('[ChatKitWidget] render error', error);
    };
  }

  mount(container) {
    if (!(container instanceof HTMLElement)) {
      throw new TypeError('ChatKitWidget requires a valid container element');
    }

    this.container = container;

    try {
      this.render();
      void sendWidgetAction({ action: 'widget_opened' }).catch((error) => {
        console.warn('[ChatKitWidget] widget_opened action failed', error);
      });
      this.onReady(this.session);
    } catch (error) {
      this.onError(error);
      throw error;
    }
  }

  destroy() {
    if (this.elements.sendButton && this.boundSendHandler) {
      this.elements.sendButton.removeEventListener('click', this.boundSendHandler);
    }
    if (this.elements.input && this.boundKeyHandler) {
      this.elements.input.removeEventListener('keydown', this.boundKeyHandler);
    }
    if (this.container) {
      this.container.innerHTML = '';
    }
    this.frame = null;
    this.frameDocument = null;
    this.elements = {
      input: null,
      sendButton: null,
      log: null,
      status: null,
    };
  }

  setOptions(options = {}) {
    if (!isPlainObject(options)) {
      return;
    }

    this.session = { ...this.session, ...options };
    this.updateStatus();
  }

  render() {
    if (!this.container) {
      throw new Error('ChatKitWidget cannot render without a container');
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

    this.container.appendChild(frame);
    this.frame = frame;

    const doc = frame.contentDocument;
    if (!doc) {
      throw new Error('Unable to access iframe document');
    }

    doc.open();
    doc.write('<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Чат ассистента</title></head><body></body></html>');
    doc.close();

    this.frameDocument = doc;
    this.injectStyles();
    this.buildLayout();
    this.updateStatus();
  }

  injectStyles() {
    if (!this.frameDocument) {
      return;
    }

    const style = this.frameDocument.createElement('style');
    style.textContent = `
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
        gap: 16px;
      }
      header {
        font-weight: 600;
      }
      section {
        flex: 1 1 auto;
        border-radius: 12px;
        background: rgba(30, 41, 59, 0.65);
        border: 1px solid rgba(148, 163, 184, 0.2);
        padding: 16px;
        overflow-y: auto;
      }
      section p {
        margin: 0 0 12px;
      }
      footer {
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
    `;

    this.frameDocument.head.appendChild(style);
  }

  buildLayout() {
    if (!this.frameDocument) {
      return;
    }

    const frameRoot = this.frameDocument.createElement('div');
    frameRoot.className = 'frame';

    const header = this.frameDocument.createElement('header');
    header.textContent = 'Чат ассистента';

    const section = this.frameDocument.createElement('section');
    section.id = 'chat-log';

    const status = this.frameDocument.createElement('p');
    status.id = 'chat-status';
    section.appendChild(status);

    const footer = this.frameDocument.createElement('footer');
    const input = this.frameDocument.createElement('input');
    input.id = 'chat-input';
    input.placeholder = 'Напишите сообщение';

    const sendButton = this.frameDocument.createElement('button');
    sendButton.id = 'chat-send';
    sendButton.type = 'button';
    sendButton.textContent = 'Отправить';

    footer.appendChild(input);
    footer.appendChild(sendButton);

    frameRoot.appendChild(header);
    frameRoot.appendChild(section);
    frameRoot.appendChild(footer);

    this.frameDocument.body.appendChild(frameRoot);

    this.elements = {
      input,
      sendButton,
      log: section,
      status,
    };

    this.bindEvents();
  }

  bindEvents() {
    const { sendButton, input } = this.elements;
    if (!sendButton || !input) {
      return;
    }

    this.boundSendHandler = () => {
      void this.handleSendMessage();
    };
    this.boundKeyHandler = (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        void this.handleSendMessage();
      }
    };

    sendButton.addEventListener('click', this.boundSendHandler);
    input.addEventListener('keydown', this.boundKeyHandler);
  }

  updateStatus() {
    if (!this.elements.status) {
      return;
    }

    const secret = this.session?.client_secret;
    this.elements.status.textContent = secret
      ? 'Сессия: получена'
      : 'Сессия: нет данных';
  }

  appendMessage(prefix, text) {
    if (!this.frameDocument || !this.elements.log) {
      return;
    }

    const paragraph = this.frameDocument.createElement('p');
    paragraph.textContent = `${prefix}: ${text}`;
    this.elements.log.appendChild(paragraph);
    this.elements.log.scrollTop = this.elements.log.scrollHeight;
  }

  async handleSendMessage() {
    if (!this.elements.input) {
      return;
    }

    const value = this.elements.input.value.trim();
    if (!value) {
      return;
    }

    this.elements.input.value = '';
    this.elements.input.focus();
    this.appendMessage('Вы', value);

    try {
      const response = await sendWidgetAction({
        action: 'handbook',
        data: {
          message: value,
          session_id: this.session?.client_secret,
        },
      });

      const replyText = typeof response.message === 'string' ? response.message.trim() : '';
      if (replyText) {
        this.appendMessage('Ассистент', replyText);
      } else if (response.awaiting_query) {
        this.appendMessage('Ассистент', 'Ожидает уточнения запроса…');
      } else {
        this.appendMessage('Ассистент', 'Сообщение принято.');
      }
    } catch (error) {
      this.appendMessage('Ошибка', error instanceof Error ? error.message : String(error));
    }
  }
}

function mount(container, options = {}) {
  const widget = new ChatKitWidget({
    onReady: options.onReady,
    onError: options.onError,
  });

  widget.mount(container);

  return {
    setOptions(update) {
      widget.setOptions(update);
    },
    destroy() {
      widget.destroy();
    },
  };
}

const ChatKit = {
  mount,
  requestSession,
  sendWidgetAction,
};

if (typeof window !== 'undefined') {
  window.ChatKit = ChatKit;
}

export { mount, requestSession, sendWidgetAction };
export default ChatKit;
