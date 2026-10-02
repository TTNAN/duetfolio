import { useState } from 'react';
import Dashboard from './pages/Dashboard.jsx';
import Transactions from './pages/Transactions.jsx';
import Instruments from './pages/Instruments.jsx';

const TABS = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'transactions', label: '🧾 Transactions' },
  { id: 'instruments', label: '🏷 Instruments' },
];

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => setReloadKey((k) => k + 1);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">◈</span>
          <div>
            <div className="brand-name">duetfolio</div>
            <div className="brand-sub">US + HK portfolio tracker</div>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? 'tab active' : 'tab'}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="main">
        {tab === 'dashboard' && <Dashboard reloadKey={reloadKey} />}
        {tab === 'transactions' && <Transactions onChange={reload} />}
        {tab === 'instruments' && <Instruments onChange={reload} />}
      </main>
      <footer className="footer">
        duetfolio · FastAPI + React · prices via Yahoo Finance (15-min delay)
      </footer>
    </div>
  );
}
