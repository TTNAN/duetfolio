import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useLang } from '../i18n.js';
import Donut from '../components/Donut.jsx';

function fmt(n, digits = 2) {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function StatCard({ label, value, sub, tone }) {
  return (
    <div className={`stat ${tone || ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function HistoryChart({ base }) {
  const { t } = useLang();
  const [pts, setPts] = useState(null);
  useEffect(() => {
    setPts(null);
    api.history(base).then(setPts).catch(() => setPts([]));
  }, [base]);

  if (!pts) return <div className="muted">{t.histLoading}</div>;
  const vals = pts.filter((p) => p.value != null);
  if (vals.length < 2) return <div className="muted">{t.histEmpty}</div>;

  const W = 560, H = 170, pad = 10;
  const min = Math.min(...vals.map((p) => p.value));
  const max = Math.max(...vals.map((p) => p.value));
  const span = max - min || 1;
  const xs = (i) => pad + (i / (vals.length - 1)) * (W - 2 * pad);
  const ys = (v) => H - pad - ((v - min) / span) * (H - 2 * pad);
  const line = vals.map((p, i) => `${xs(i).toFixed(1)},${ys(p.value).toFixed(1)}`).join(' ');
  const area = `${pad},${H - pad} ${line} ${W - pad},${H - pad}`;
  const first = vals[0].value, last = vals[vals.length - 1].value;
  const tone = last >= first ? 'pos' : 'neg';
  const chg = ((last - first) / (first || 1)) * 100;

  return (
    <div>
      <div className={`stat-sub ${tone}`} style={{ marginBottom: 6 }}>
        {last >= first ? '+' : ''}{chg.toFixed(2)}% {t.since} {vals[0].date}
        <span className="muted"> · {t.fxNote}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label="portfolio value history">
        <polygon points={area} fill="currentColor" className={tone} opacity="0.12" />
        <polyline points={line} fill="none" stroke="currentColor" strokeWidth="2" className={tone} />
        <circle cx={xs(vals.length - 1)} cy={ys(last)} r="3.5" className={tone} fill="currentColor" />
      </svg>
      <div className="muted small">{vals[0].date} → {vals[vals.length - 1].date} · {base}</div>
    </div>
  );
}

export default function Dashboard({ reloadKey, goTab }) {
  const { t } = useLang();
  const [data, setData] = useState(null);
  const [base, setBase] = useState('HKD');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState('');

  const load = async (b) => {
    setLoading(true);
    setErr('');
    try {
      setData(await api.summary(b));
    } catch (e) {
      setErr(t.apiDown);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(base); }, [base, reloadKey]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const r = await api.refreshPrices();
      if (r.failed?.length) setErr(`${t.priceFailed}${r.failed.join(', ')}`);
      await load(base);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) return <div className="card">{t.histLoading}</div>;
  if (err && !data) return <div className="card error">{err}</div>;

  // empty state: 3-step onboarding instead of an empty table
  if (data.holdings.length === 0) {
    const steps = [
      { n: '1', title: t.step1, desc: t.step1d, act: () => goTab && goTab('instruments') },
      { n: '2', title: t.step2, desc: t.step2d, act: () => goTab && goTab('transactions') },
      { n: '3', title: t.step3, desc: t.step3d, act: onRefresh },
    ];
    return (
      <div className="card empty-hero">
        <h3>{t.emptyTitle}</h3>
        <div className="steps">
          {steps.map((s) => (
            <button key={s.n} className="step" onClick={s.act}>
              <span className="step-n">{s.n}</span>
              <span className="step-t">{s.title}</span>
              <span className="step-d muted">{s.desc}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  const pnlTone = (data.total_pnl ?? 0) >= 0 ? 'pos' : 'neg';
  const donutItems = data.holdings
    .filter((h) => h.market_value_base)
    .map((h) => ({ label: h.symbol, value: h.market_value_base }));

  return (
    <div>
      <div className="toolbar">
        <div className="seg">
          {['HKD', 'USD', 'CNY'].map((c) => (
            <button key={c} className={base === c ? 'seg-btn active' : 'seg-btn'} onClick={() => setBase(c)}>{c}</button>
          ))}
        </div>
        <button className="btn" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? t.refreshing : t.refresh}
        </button>
      </div>
      {err && <div className="card error">{err}</div>}
      {(data.price_stale?.length > 0 || data.fx_stale?.length > 0) && (
        <div className="card warn">
          {t.incomplete}
          {data.price_stale?.length > 0 && ` ${data.price_stale.join(', ')} ${t.noPriceFor}；`}
          {data.fx_stale?.length > 0 && ` ${data.fx_stale.join(', ')} ${t.fxMissing}`}
        </div>
      )}

      <div className="stats">
        <StatCard label={`${t.totalValue} (${data.base_currency})`} value={fmt(data.total_value)} sub={data.fx_usd_to_base ? `USD/${data.base_currency} ${data.fx_usd_to_base.toFixed(4)}` : ''} />
        <StatCard label={t.invested} value={fmt(data.total_invested)} />
        <StatCard label={t.totalPnl} value={data.total_pnl == null ? '—' : (data.total_pnl >= 0 ? '+' : '') + fmt(data.total_pnl)} tone={pnlTone} sub={data.realized_pnl != null && data.unrealized_pnl != null ? `${t.realized} ${fmt(data.realized_pnl)} · ${t.unrealized} ${fmt(data.unrealized_pnl)}` : ''} />
        <StatCard label={t.xirr} value={data.xirr === null ? '—' : (data.xirr * 100).toFixed(2) + '%'} sub={t.xirrSub} tone={pnlTone} />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>{t.netWorth}</h3>
        <HistoryChart base={base} />
      </div>

      <div className="grid2">
        <div className="card">
          <h3>{t.allocation}</h3>
          <Donut items={donutItems} />
        </div>
        <div className="card">
          <h3>{t.holdings}</h3>
          <table className="tbl">
            <thead>
              <tr><th>{t.th.symbol}</th><th>{t.th.qty}</th><th>{t.th.avgCost}</th><th>{t.th.price}</th><th>{t.th.value} ({data.base_currency})</th><th>{t.th.pnl}</th></tr>
            </thead>
            <tbody>
              {data.holdings.map((h) => (
                <tr key={h.instrument_id}>
                  <td><b>{h.symbol}</b> <span className="muted">{h.market}</span></td>
                  <td>{h.quantity}</td>
                  <td>{fmt(h.avg_cost)} {h.currency}</td>
                  <td>{h.latest_price ? fmt(h.latest_price) : <span className="muted">{t.stale}</span>}</td>
                  <td>{fmt(h.market_value_base)}</td>
                  <td className={(h.unrealized_pnl_base ?? 0) >= 0 ? 'pos' : 'neg'}>
                    {(h.unrealized_pnl_base ?? 0) >= 0 ? '+' : ''}{fmt(h.unrealized_pnl_base)}
                  </td>
                </tr>
              ))}
              {data.holdings.length === 0 && (
                <tr><td colSpan="6" className="muted">{t.noInstruments}</td></tr>
              )}
            </tbody>
          </table>
          {data.price_stale.length > 0 && (
            <div className="muted small">⚠ {t.noPriceFor}：{data.price_stale.join(', ')}</div>
          )}
        </div>
      </div>
    </div>
  );
}
