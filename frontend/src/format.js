export const isNum = (n) => typeof n === 'number' && Number.isFinite(n);

export function money(n, digits = 2) {
  if (!isNum(n)) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signed(n, digits = 2) {
  if (!isNum(n)) return '—';
  return (n > 0 ? '+' : n < 0 ? '−' : '') + money(Math.abs(n), digits);
}

export function pct(f, digits = 2, withSign = true) {
  if (!isNum(f)) return '—';
  const v = f * 100;
  const s = Math.abs(v).toFixed(digits) + '%';
  if (!withSign) return (v < 0 ? '−' : '') + s;
  return (v > 0 ? '+' : v < 0 ? '−' : '') + s;
}

export function qty(n) {
  if (!isNum(n)) return '—';
  return n.toLocaleString('en-US', { maximumFractionDigits: 6 });
}

export function compact(n) {
  if (!isNum(n)) return '—';
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (a >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (a >= 1e4) return (n / 1e3).toFixed(1) + 'K';
  return money(n, 0);
}

export const tone = (n) => (!isNum(n) || n === 0 ? '' : n > 0 ? 'up' : 'down');
export const mask = (s, on) => (on ? '••••••' : s);
export const todayISO = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};
