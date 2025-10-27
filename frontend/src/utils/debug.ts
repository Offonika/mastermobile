const TRUE_VALUES = new Set(['1', 'true', 'yes', 'on']);
const FALSE_VALUES = new Set(['0', 'false', 'no', 'off']);

function normaliseCandidate(candidate: unknown): string | null {
  if (typeof candidate === 'boolean') {
    return candidate ? 'true' : 'false';
  }

  if (typeof candidate === 'number') {
    if (Number.isNaN(candidate)) {
      return null;
    }

    return candidate === 0 ? '0' : '1';
  }

  if (typeof candidate === 'string') {
    const trimmed = candidate.trim();

    if (!trimmed) {
      return null;
    }

    return trimmed;
  }

  return null;
}

function parseBoolean(candidate: unknown): boolean | null {
  const normalised = normaliseCandidate(candidate);

  if (!normalised) {
    return null;
  }

  const lowered = normalised.toLowerCase();

  if (TRUE_VALUES.has(lowered)) {
    return true;
  }

  if (FALSE_VALUES.has(lowered)) {
    return false;
  }

  return null;
}

function resolveDebugFlag(): boolean {
  const queryValue = new URLSearchParams(window.location.search).get('debug');
  const parsedQuery = parseBoolean(queryValue);

  if (parsedQuery !== null) {
    return parsedQuery;
  }

  const globalValue = window.__ASSISTANT_DEBUG__;
  const parsedGlobal = parseBoolean(globalValue);

  if (parsedGlobal !== null) {
    return parsedGlobal;
  }

  const envValue =
    typeof import.meta !== 'undefined'
      ? import.meta.env.VITE_ASSISTANT_DEBUG ?? import.meta.env.ASSISTANT_DEBUG
      : undefined;
  const parsedEnv = parseBoolean(envValue);

  if (parsedEnv !== null) {
    return parsedEnv;
  }

  return false;
}

const isDebugEnabled = resolveDebugFlag();

export function isAssistantDebugEnabled() {
  return isDebugEnabled;
}

export function assistantDebug(message: string, ...optionalParams: unknown[]) {
  if (!isDebugEnabled) {
    return;
  }

  console.debug(`[assistant] ${message}`, ...optionalParams);
}
