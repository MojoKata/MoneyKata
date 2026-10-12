// The browser's side of /ui/api (requirements §16.8): JSON in and out, problem+json errors with
// each refusal at its field, If-Match versions, and Idempotency-Key on creates.

/** A refusal from the server, with the field each part of it belongs to. */
export class ApiError extends Error {
  /**
   * @param {number} status
   * @param {any} body
   */
  constructor(status, body) {
    super(body?.detail || body?.title || `HTTP ${status}`);
    this.status = status;
    this.code = body?.code || 'error';
    /** @type {{ field: string | null, code: string, message: string }[]} */
    this.errors = body?.errors || [];
    this.current = body?.current;
    this.errorId = body?.errorId;
  }

  /**
   * The message for one field, or for the form when none names it.
   * @param {string | null} field
   */
  at(field) {
    const e = this.errors.find((x) => x.field === field);
    return e ? e.message : null;
  }
}

/** Called when a request finds no session: the frame goes to sign-in. */
let onSignedOut = (/** @type {string} */ _code) => {};
/** @param {(code: string) => void} fn */
export function whenSignedOut(fn) {
  onSignedOut = fn;
}

/**
 * @param {string} method
 * @param {string} path
 * @param {{ body?: any, version?: number, params?: Record<string, any>, idempotent?: boolean,
 *   form?: FormData }} [opts]
 */
async function call(method, path, opts = {}) {
  const url = new URL('/ui/api' + path, location.origin);
  for (const [k, v] of Object.entries(opts.params || {})) {
    if (Array.isArray(v)) v.forEach((x) => url.searchParams.append(k, String(x)));
    else if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
  }
  /** @type {Record<string, string>} */
  const headers = { Accept: 'application/json' };
  let body;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  if (opts.version !== undefined) headers['If-Match'] = `"${opts.version}"`;
  if (opts.idempotent) headers['Idempotency-Key'] = crypto.randomUUID();
  const r = await fetch(url, { method, headers, body, credentials: 'same-origin' });
  if (r.status === 204 || r.status === 201 && r.headers.get('content-length') === '0') {
    return null;
  }
  const text = await r.text();
  const data = text ? JSON.parse(text) : null;
  if (!r.ok) {
    const err = new ApiError(r.status, data);
    if (r.status === 401 && !path.startsWith('/session')) onSignedOut(err.code);
    throw err;
  }
  return data;
}

export const api = {
  /** @param {string} path @param {Record<string, any>} [params] */
  get: (path, params) => call('GET', path, { params }),
  /** @param {string} path @param {any} [body] @param {{ idempotent?: boolean }} [o] */
  post: (path, body, o = {}) => call('POST', path, { body, ...o }),
  /** @param {string} path @param {any} body */
  put: (path, body) => call('PUT', path, { body }),
  /** @param {string} path @param {any} body @param {number} [version] @param {Record<string, any>} [params] */
  patch: (path, body, version, params) => call('PATCH', path, { body, version, params }),
  /** @param {string} path @param {number} [version] */
  del: (path, version) => call('DELETE', path, { version }),
  /** @param {string} path @param {File} file */
  upload: (path, file) => {
    const form = new FormData();
    form.append('file', file);
    return call('POST', path, { form });
  },
};
