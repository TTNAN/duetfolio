import { useEffect, useState } from 'react';
import Dashboard from './pages/Dashboard.jsx';
import Transactions from './pages/Transactions.jsx';
import Instruments from './pages/Instruments.jsx';
import { useLang } from './i18n.js';
import { api } from './api.js';

function initTheme() {
  try {
    const saved = localStorage.getItem('duetfolio-theme');
    if (saved === 'light' || saved === 'dark') return saved;
  } catch { /* ignore */ }
  return 'dark';
}

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [reloadKey, setReloadKey] = useState(0);
  const { lang, setLang, t } = useLang();
  const [theme, setTheme] = useState(initTheme);
  const [provider, setProvider] = useState('yfinance');
  const reload = () => setReloadKey((k) => k + 1);

  useEffect(() => {
    api.health().then((h) => {
      if (h && h.market_provider) setProvider(h.market_provider);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('duetfolio-theme', theme); } catch { /* ignore */ }
  }, [theme]);

  const TABS = [
    { id: 'dashboard', label: t.tabs.dashboard },
    { id: 'transactions', label: t.tabs.transactions },
    { id: 'instruments', label: t.tabs.instruments },
  ];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">◈</span>
          <div>
            <div className="brand-name">duetfolio</div>
            <div className="brand-sub">{t.brandSub}</div>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((tb) => (
            <button
              key={tb.id}
              className={tab === tb.id ? 'tab active' : 'tab'}
              onClick={() => setTab(tb.id)}
            >
              {tb.label}
            </button>
          ))}
          <button
            className="tab lang-btn"
            onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}
            title="switch language"
          >
            {t.langBtn}
          </button>
          <button
            className="tab lang-btn"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title={theme === 'dark' ? t.themeLight : t.themeDark}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </nav>
      </header>
      <main className="main">
        {tab === 'dashboard' && <Dashboard reloadKey={reloadKey} goTab={setTab} />}
        {tab === 'transactions' && <Transactions onChange={reload} />}
        {tab === 'instruments' && <Instruments onChange={reload} />}
      </main>
      <footer className="footer">
        {t.footerTpl(
          t.providerNames[provider] || provider,
          t.providerNames[provider === 'eastmoney' ? 'yfinance' : 'eastmoney']
        )}
      </footer>
    </div>
  );
}
