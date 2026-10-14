const ROOT = import.meta.env.VITE_API_URL || '';
const BASE = ROOT + '/api';

function cleanError(status, text) {
  try {
    const j = JSON.parse(text);
    if (typeof j.detail === 'string') return j.detail;
    if (Array.isArray(j.detail)) return j.detail.map((d) => d.msg).join('; ');
  } catch { /* not json */ }
  return `${status} ${text.slice(0, 160)}`;
}

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: opts.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error(cleanError(res.status, await res.text()));
  if (res.status === 204) return null;
  return res.json();
}

const upload = (path, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return req(path, { method: 'POST', body: fd });
};

export const api = {
  health: () => req('/health'),
  summary: (base = 'HKD') => req(`/portfolio/summary?base=${base}`),
  history: (base = 'HKD') => req(`/portfolio/history?base=${base}`),
  benchmarks: () => req('/benchmarks'),
  benchmark: (symbol, start) => req(`/benchmark?symbol=${encodeURIComponent(symbol)}&start=${start}`),

  searchInstruments: (q) => req(`/instruments/search?q=${encodeURIComponent(q)}`),
  instruments: () => req('/instruments'),
  instrumentPrices: (id) => req(`/instruments/${id}/prices`),
  addInstrument: (body) => req('/instruments', { method: 'POST', body: JSON.stringify(body) }),
  updateInstrument: (id, body) => req(`/instruments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteInstrument: (id) => req(`/instruments/${id}`, { method: 'DELETE' }),

  transactions: (instrumentId) => req(`/transactions?limit=1000${instrumentId ? `&instrument_id=${instrumentId}` : ''}`),
  addTransaction: (body) => req('/transactions', { method: 'POST', body: JSON.stringify(body) }),
  updateTransaction: (id, body) => req(`/transactions/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteTransaction: (id) => req(`/transactions/${id}`, { method: 'DELETE' }),
  importPreview: (file) => upload('/transactions/import/preview', file),
  importConfirm: (rows) => req('/transactions/import', { method: 'POST', body: JSON.stringify({ rows }) }),

  cash: () => req('/cash'),
  addCash: (body) => req('/cash', { method: 'POST', body: JSON.stringify(body) }),
  deleteCash: (id) => req(`/cash/${id}`, { method: 'DELETE' }),

  refreshPrices: () => req('/prices/refresh', { method: 'POST' }),
  backfill: () => req('/prices/backfill', { method: 'POST' }),
  restoreBackup: (file) => upload('/backup/restore', file),
  backupUrl: () => BASE + '/backup',
  exportCsvUrl: () => BASE + '/transactions/export.csv',
};
