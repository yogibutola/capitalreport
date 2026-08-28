import { HttpErrorResponse } from '@angular/common/http';

/**
 * Normalized form of any backend/network failure.
 *
 * - `message` is always safe to show to a person: a full sentence, no codes or
 *   stack traces, phrased as guidance rather than blame.
 * - `fieldErrors` maps a form field name to its message when the backend told us
 *   which field was wrong (FastAPI/Pydantic `detail` arrays carry a `loc`).
 * - `kind` lets callers decide whether to surface this inline (validation) or as
 *   a global toast (network / server).
 */
export interface ParsedHttpError {
  message: string;
  fieldErrors: Record<string, string>;
  kind: 'network' | 'server' | 'auth' | 'validation' | 'conflict' | 'notfound' | 'unknown';
  status: number;
}

const GENERIC: Record<ParsedHttpError['kind'], string> = {
  network: "We couldn't reach the server. Check your connection and try again.",
  server: 'Something went wrong on our end. Please try again in a moment.',
  auth: 'Your session has expired. Please sign in again.',
  validation: 'Please review the highlighted fields and try again.',
  conflict: 'That action conflicts with the current state. Refresh and try again.',
  notfound: "We couldn't find what you were looking for.",
  unknown: 'Something went wrong. Please try again.',
};

/** Turn a Pydantic-style message ("value is not a valid email address") into
 *  a clean, capitalized sentence. */
function humanize(raw: string): string {
  let msg = (raw || '').trim();
  msg = msg.replace(/^value error,?\s*/i, '');
  msg = msg.replace(/^assertion error,?\s*/i, '');
  if (!msg) return GENERIC.unknown;
  msg = msg.charAt(0).toUpperCase() + msg.slice(1);
  if (!/[.!?]$/.test(msg)) msg += '.';
  return msg;
}

/** Last segment of a Pydantic `loc` array is the field name (["body", "email"]). */
function fieldFromLoc(loc: unknown): string | null {
  if (!Array.isArray(loc) || loc.length === 0) return null;
  const last = loc[loc.length - 1];
  return typeof last === 'string' || typeof last === 'number' ? String(last) : null;
}

function kindForStatus(status: number): ParsedHttpError['kind'] {
  if (status === 0) return 'network';
  if (status === 401 || status === 403) return 'auth';
  if (status === 404) return 'notfound';
  if (status === 409) return 'conflict';
  if (status === 422 || status === 400) return 'validation';
  if (status >= 500) return 'server';
  return 'unknown';
}

export function parseHttpError(err: unknown): ParsedHttpError {
  // Already parsed — pass through (services may rethrow a ParsedHttpError).
  if (err && typeof err === 'object' && 'kind' in err && 'fieldErrors' in err) {
    return err as ParsedHttpError;
  }

  const http = err instanceof HttpErrorResponse ? err : null;
  const status = http?.status ?? 0;
  const kind = kindForStatus(status);
  const fieldErrors: Record<string, string> = {};
  let message = '';

  const detail = http?.error?.detail ?? http?.error;

  if (typeof detail === 'string') {
    message = humanize(detail);
  } else if (Array.isArray(detail)) {
    const parts: string[] = [];
    for (const item of detail) {
      const text = humanize(item?.msg || item?.message || 'This value is invalid');
      const field = fieldFromLoc(item?.loc);
      if (field && field !== 'body') {
        fieldErrors[field] = text;
      } else {
        parts.push(text);
      }
    }
    message = parts.join(' ') || (Object.keys(fieldErrors).length ? GENERIC.validation : '');
  } else if (detail && typeof detail === 'object') {
    if (typeof (detail as any).message === 'string') {
      message = humanize((detail as any).message);
    }
  }

  if (!message) {
    // Network errors surface as ProgressEvent with status 0.
    message = GENERIC[kind];
  }

  return { message, fieldErrors, kind, status };
}
