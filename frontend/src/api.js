const ROOT = import.meta.env.VITE_API_URL || '';
const BASE = ROOT + '/api';

/** Thrown for HTTP errors; `status` lets callers tell 403 (demo) from 5xx. */
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/** True when a request was cancelled on purpose (component re-rendered). */
export const isAbort = (e) => e?.name === 'AbortError';

function cleanError(status, text) {
  try {
    const j = JSON.parse(text);
    if (typeof j.detail === 'string') return j.detail;
    if (Array.isArray(j.detail)) return j.detail.map((d) => d.msg).join('; ');
  } catch { /* not json */ }
  if (status === 0) return 'Network error';
  return `${status} ${text.slice(0, 160)}`;
}

async function req(path, opts = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      headers: opts.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
      ...opts,
    });
  } catch (e) {
    if (isAbort(e)) throw e;
    throw new ApiError(0, 'Network error — is the backend running?');
  }
  if (!res.ok) throw new ApiError(res.status, cleanError(res.status, await res.text()));
  if (res.status === 204) return null;
  return res.json();
}

const upload = (path, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return req(path, { method: 'POST', body: fd });
};

const q = (o) => Object.entries(o).filter(([, v]) => v != null && v !== '')
  .map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');

// Read calls take an optional AbortSignal: effects pass one and abort it on
// cleanup, so a slow response for an old base currency / range never
// overwrites the state of the newer request.
export const api = {
  health: (signal) => req('/health', { signal }),
  summary: (base = 'HKD', method, signal) => req(`/portfolio/summary?${q({ base, method })}`, { signal }),
  history: (base = 'HKD', method, signal) => req(`/portfolio/history?${q({ base, method })}`, { signal }),
  benchmarks: (signal) => req('/benchmarks', { signal }),
  benchmark: (symbol, start, signal) => req(`/benchmark?${q({ symbol, start })}`, { signal }),

  searchInstruments: (term, signal) => req(`/instruments/search?${q({ q: term })}`, { signal }),
  instruments: (signal) => req('/instruments', { signal }),
  instrumentPrices: (id, signal) => req(`/instruments/${id}/prices`, { signal }),
  addInstrument: (body) => req('/instruments', { method: 'POST', body: JSON.stringify(body) }),
  updateInstrument: (id, body) => req(`/instruments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteInstrument: (id) => req(`/instruments/${id}`, { method: 'DELETE' }),

  transactions: (instrumentId, signal) => req(`/transactions?${q({ limit: 1000, instrument_id: instrumentId })}`, { signal }),
  addTransaction: (body) => req('/transactions', { method: 'POST', body: JSON.stringify(body) }),
  updateTransaction: (id, body) => req(`/transactions/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteTransaction: (id) => req(`/transactions/${id}`, { method: 'DELETE' }),
  importPreview: (file, broker = 'auto') => upload(`/transactions/import/preview?${q({ broker })}`, file),
  importConfirm: (rows) => req('/transactions/import', { method: 'POST', body: JSON.stringify({ rows }) }),

  cash: (signal) => req('/cash', { signal }),
  addCash: (body) => req('/cash', { method: 'POST', body: JSON.stringify(body) }),
  deleteCash: (id) => req(`/cash/${id}`, { method: 'DELETE' }),

  refreshPrices: (force = false) => req(`/prices/refresh${force ? '?force=true' : ''}`, { method: 'POST' }),
  backfill: () => req('/prices/backfill', { method: 'POST' }),
  restoreBackup: (file) => upload('/backup/restore', file),
  backupUrl: () => BASE + '/backup',
  exportCsvUrl: () => BASE + '/transactions/export.csv',
};
