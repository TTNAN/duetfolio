const BASE = (import.meta.env.VITE_API_URL || '') + '/api';

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text.slice(0, 200)}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => req('/health'),
  summary: (base = 'HKD') => req(`/portfolio/summary?base=${base}`),
  history: (base = 'HKD') => req(`/portfolio/history?base=${base}`),
  searchInstruments: (q) => req(`/instruments/search?q=${encodeURIComponent(q)}`),
  updateTransaction: (id, body) => req(`/transactions/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  instruments: () => req('/instruments'),
  addInstrument: (body) => req('/instruments', { method: 'POST', body: JSON.stringify(body) }),
  deleteInstrument: (id) => req(`/instruments/${id}`, { method: 'DELETE' }),
  transactions: (instrumentId) => req(`/transactions${instrumentId ? `?instrument_id=${instrumentId}` : ''}`),
  addTransaction: (body) => req('/transactions', { method: 'POST', body: JSON.stringify(body) }),
  updateTransaction: (id, body) => req(`/transactions/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteTransaction: (id) => req(`/transactions/${id}`, { method: 'DELETE' }),
  importPreview: async (file) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch((import.meta.env.VITE_API_URL || '') + '/api/transactions/import/preview', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
    return res.json();
  },
  importConfirm: (rows) => req('/transactions/import', { method: 'POST', body: JSON.stringify({ rows }) }),
  cash: () => req('/cash'),
  addCash: (body) => req('/cash', { method: 'POST', body: JSON.stringify(body) }),
  deleteCash: (id) => req(`/cash/${id}`, { method: 'DELETE' }),
  refreshPrices: () => req('/prices/refresh', { method: 'POST' }),
};
