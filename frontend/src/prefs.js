// User display preferences, persisted in localStorage, shared across components.
import { useEffect, useState } from 'react';

const KEY = 'duetfolio-prefs';
const lang0 = (() => { try { return localStorage.getItem('duetfolio-lang') || 'zh'; } catch { return 'zh'; } })();
const DEFAULTS = {
  theme: (() => { try { return localStorage.getItem('duetfolio-theme') || 'dark'; } catch { return 'dark'; } })(),
  // Chinese convention (red = up) by default for Chinese UI, Western otherwise
  updown: lang0 === 'zh' ? 'cn' : 'intl',
  base: 'HKD',
  privacy: false,
  // cost basis: 'wac' weighted average (HK/CN broker apps) | 'fifo' (US brokers)
  costMethod: 'wac',
};

let prefs = { ...DEFAULTS };
try { prefs = { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { /* ignore */ }
const listeners = new Set();

function apply() {
  const el = document.documentElement;
  el.dataset.theme = prefs.theme;
  el.dataset.updown = prefs.updown;
}
apply();

export function setPref(k, v) {
  prefs = { ...prefs, [k]: v };
  try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* ignore */ }
  apply();
  listeners.forEach((fn) => fn(prefs));
}

export function usePrefs() {
  const [p, setP] = useState(prefs);
  useEffect(() => { listeners.add(setP); return () => listeners.delete(setP); }, []);
  return [p, setPref];
}
