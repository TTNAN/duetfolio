import { useCallback, useEffect, useState } from 'react';
import { LayoutDashboard, ReceiptText, Tags, Settings as Cog, Plus, Moon, Sun, Eye, EyeOff } from 'lucide-react';
import Dashboard from './pages/Dashboard.jsx';
import Transactions from './pages/Transactions.jsx';
import Instruments from './pages/Instruments.jsx';
import Settings from './pages/Settings.jsx';
import TxnModal from './components/TxnModal.jsx';
import { Logo, Toaster } from './components/ui.jsx';
import { useLang } from './i18n.js';
import { usePrefs } from './prefs.js';
import { api } from './api.js';

const PAGES = ['dashboard', 'transactions', 'instruments', 'settings'];
const ICONS = { dashboard: LayoutDashboard, transactions: ReceiptText, instruments: Tags, settings: Cog };
const pageFromHash = () => {
  const h = window.location.hash.replace('#/', '');
  return PAGES.includes(h) ? h : 'dashboard';
};

export default function App() {
  const { lang, setLang, t } = useLang();
  const [prefs, setPref] = usePrefs();
  const [page, setPage] = useState(pageFromHash);
  const [reloadKey, setReloadKey] = useState(0);
  const [health, setHealth] = useState(null);
  const [addFor, setAddFor] = useState(null); // null = closed, {} = open, {instrumentId} = preset

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  const go = useCallback((p) => { window.location.hash = '/' + p; }, []);
  const openAdd = useCallback((instrumentId) => setAddFor({ instrumentId }), []);

  useEffect(() => {
    const h = () => setPage(pageFromHash());
    window.addEventListener('hashchange', h);
    return () => window.removeEventListener('hashchange', h);
  }, []);

  useEffect(() => {
    const ping = () => api.health().then(setHealth).catch(() => setHealth(false));
    ping();
    const id = setInterval(ping, 60000);
    return () => clearInterval(id);
  }, []);

  // keyboard shortcuts (ignored while typing)
  useEffect(() => {
    const h = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = (e.target.tagName || '').toLowerCase();
      if (['input', 'textarea', 'select'].includes(tag) || document.querySelector('.modal, .drawer')) return;
      if (e.key === 'n' || e.key === 'N') { e.preventDefault(); openAdd(); }
      const idx = Number(e.key) - 1;
      if (idx >= 0 && idx < PAGES.length) go(PAGES[idx]);
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [go, openAdd]);

  const provider = health && health.market_provider;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Logo />
          <div>
            <div className="brand-name">duetfolio</div>
            <div className="brand-sub">{t.brandSub}</div>
          </div>
        </div>
        {PAGES.map((p, i) => {
          const Icon = ICONS[p];
          return (
            <button key={p} className={`nav-item ${page === p ? 'active' : ''}`} onClick={() => go(p)}>
              <Icon size={17} strokeWidth={1.7} />
              {t.nav[p]}
              <span className="nav-kbd">{i + 1}</span>
            </button>
          );
        })}
        <button className="btn primary" style={{ marginTop: 14 }} onClick={() => openAdd()}>
          <Plus size={16} />{t.nav.add}<span style={{ opacity: .6, fontSize: 11, marginLeft: 4 }}>N</span>
        </button>
        <div className="sidebar-spacer" />
        <div className="sidebar-foot">
          <div className="sidebar-row">
            <button className="btn sm ghost icon" title={t.sTheme}
              onClick={() => setPref('theme', prefs.theme === 'dark' ? 'light' : 'dark')}>
              {prefs.theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
            </button>
            <button className="btn sm ghost icon" title={t.sPrivacy}
              onClick={() => setPref('privacy', !prefs.privacy)}>
              {prefs.privacy ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
            <button className="btn sm ghost" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}>
              {lang === 'zh' ? 'EN' : '中文'}
            </button>
          </div>
          <div className="small muted">
            <span className={`status-dot ${health === false ? 'off' : ''}`} />
            {health === false ? t.offline : t.online}
            {provider ? ` · ${t.providerNames[provider] || provider}` : ''}
          </div>
        </div>
      </aside>

      <main className="main">
        {health && health.demo && (
          <div className="demo-banner" role="note">
            <b>DEMO</b><span>{t.demoBanner}</span>
            <a href="https://github.com/TTNAN/duetfolio" target="_blank" rel="noreferrer">GitHub →</a>
          </div>
        )}
        {page === 'dashboard' && <Dashboard reloadKey={reloadKey} reload={reload} go={go} openAdd={openAdd} provider={provider} />}
        {page === 'transactions' && <Transactions reloadKey={reloadKey} reload={reload} openAdd={openAdd} />}
        {page === 'instruments' && <Instruments reloadKey={reloadKey} reload={reload} openAdd={openAdd} />}
        {page === 'settings' && <Settings reload={reload} health={health} />}
        <div className="footer-note">{t.disclaimer} <span className="hide-sm">· {t.shortcuts}</span></div>
      </main>

      <nav className="mobile-bar">
        {['dashboard', 'transactions'].map((p) => {
          const Icon = ICONS[p];
          return <button key={p} className={page === p ? 'on' : ''} onClick={() => go(p)}><Icon size={20} strokeWidth={1.7} /><span>{t.nav[p]}</span></button>;
        })}
        <button className="fab" onClick={() => openAdd()}><span><Plus size={20} /></span></button>
        {['instruments', 'settings'].map((p) => {
          const Icon = ICONS[p];
          return <button key={p} className={page === p ? 'on' : ''} onClick={() => go(p)}><Icon size={20} strokeWidth={1.7} /><span>{t.nav[p]}</span></button>;
        })}
      </nav>

      {addFor && (
        <TxnModal presetInstrumentId={addFor.instrumentId} onClose={() => setAddFor(null)}
          onSaved={reload} goInstruments={() => go('instruments')} />
      )}
      <Toaster />
    </div>
  );
}
