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

// Static demo build (GitHub Pages): no backend. GET requests are answered
// from a JSON snapshot generated in CI (scripts/build_static_demo.py);
// writes are refused like the server's read-only demo mode.
const STATIC = import.meta.env.VITE_STATIC_DEMO === 'true';
const STATIC_ROOT = import.meta.env.BASE_URL + 'demo/';
let snapshot;
const loadSnapshot = () => (snapshot ||= fetch(STATIC_ROOT + 'data.json').then((r) => {
  if (!r.ok) throw new ApiError(r.status, 'Demo data missing');
  return r.json();
}));

async function staticReq(path, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase();
  const [p, qs = ''] = path.split('?');
  const params = new URLSearchParams(qs);
  if (method !== 'GET') {
    if (p === '/prices/refresh') {
      const d = await loadSnapshot();
      return { updated: [], fresh: d['/instruments'].map((i) => i.symbol), failed: [] };
    }
    if (p === '/prices/backfill') return { inserted: 0, failed: [] };
    throw new ApiError(403, '演示模式是只读的 · The demo is read-only');
  }
  const d = await loadSnapshot();
  if (opts.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  if (p === '/portfolio/summary' || p === '/portfolio/history') {
    const key = `${p}?base=${params.get('base') || 'HKD'}&method=${params.get('method') || 'wac'}`;
    return structuredClone(d[key]);
  }
  if (p === '/benchmark') {
    const b = d[`/benchmark?symbol=${params.get('symbol')}`];
    if (!b) throw new ApiError(400, 'Unsupported benchmark');
    const start = params.get('start') || '';
    return { ...b, points: b.points.filter((x) => x.date >= start) };
  }
  if (p === '/transactions') {
    const id = params.get('instrument_id');
    return d['/transactions'].filter((x) => !id || String(x.instrument_id) === id);
  }
  if (p === '/instruments/search') return [];
  if (p in d) return structuredClone(d[p]);
  throw new ApiError(404, `Not in demo snapshot: ${p}`);
}

async function req(path, opts = {}) {
  if (STATIC) return staticReq(path, opts);
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
  backupUrl: () => (STATIC ? STATIC_ROOT + 'backup.json' : BASE + '/backup'),
  exportCsvUrl: () => (STATIC ? STATIC_ROOT + 'transactions.csv' : BASE + '/transactions/export.csv'),
};
