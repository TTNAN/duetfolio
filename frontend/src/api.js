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
  instruments: () => req('/instruments'),
  addInstrument: (body) => req('/instruments', { method: 'POST', body: JSON.stringify(body) }),
  deleteInstrument: (id) => req(`/instruments/${id}`, { method: 'DELETE' }),
  transactions: () => req('/transactions'),
  addTransaction: (body) => req('/transactions', { method: 'POST', body: JSON.stringify(body) }),
  deleteTransaction: (id) => req(`/transactions/${id}`, { method: 'DELETE' }),
  refreshPrices: () => req('/prices/refresh', { method: 'POST' }),
};
