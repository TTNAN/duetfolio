import { useEffect, useMemo, useState } from 'react';
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
  const [hover, setHover] = useState(null);
  useEffect(() => {
    setPts(null);
    setHover(null);
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

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const fx = (e.clientX - rect.left) / rect.width;
    const i = Math.round(fx * (vals.length - 1));
    setHover(Math.max(0, Math.min(vals.length - 1, i)));
  };

  return (
    <div>
      <div className={`stat-sub ${tone}`} style={{ marginBottom: 6 }}>
        {last >= first ? '+' : ''}{chg.toFixed(2)}% {t.since} {vals[0].date}
        <span className="muted"> · {t.fxNote}</span>
      </div>
      <div className="chart-wrap" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label="portfolio value history">
          <polygon points={area} fill="currentColor" className={tone} opacity="0.12" />
          <polyline points={line} fill="none" stroke="currentColor" strokeWidth="2" className={tone} />
          {hover != null && (
            <g>
              <line x1={xs(hover)} y1={pad} x2={xs(hover)} y2={H - pad} stroke="currentColor" className="muted" strokeDasharray="3 3" opacity="0.5" />
              <circle cx={xs(hover)} cy={ys(vals[hover].value)} r="4" className={tone} fill="currentColor" />
            </g>
          )}
          <circle cx={xs(vals.length - 1)} cy={ys(last)} r="3.5" className={tone} fill="currentColor" />
        </svg>
        {hover != null && (
          <div className="chart-tip" style={{ left: `${(xs(hover) / W) * 100}%` }}>
            <div><b>{fmt(vals[hover].value)}</b> {base}</div>
            <div className="muted">{vals[hover].date}</div>
          </div>
        )}
      </div>
      <div className="muted small">
        {vals[0].date} → {vals[vals.length - 1].date} · {base}
        <span style={{ float: 'right' }}>min {fmt(min)} · max {fmt(max)}</span>
      </div>
    </div>
  );
}

function HoldingPanel({ holding, base, onClose }) {
  const { t } = useLang();
  const [txns, setTxns] = useState(null);
  useEffect(() => {
    setTxns(null);
    api.transactions(holding.instrument_id).then(setTxns).catch(() => setTxns([]));
  }, [holding.instrument_id]);

  return (
    <>
      <div className="sidepanel-backdrop" onClick={onClose} />
      <div className="sidepanel">
        <div className="panel-head">
          <div>
            <div className="panel-title">{holding.symbol}</div>
            <div className="muted small">{holding.name}</div>
          </div>
          <button className="btn" onClick={onClose}>{t.closePanel}</button>
        </div>
        <div className="stats" style={{ marginTop: 12 }}>
          <StatCard label={t.th.qty} value={holding.quantity} />
          <StatCard label={t.realizedPnl} value={(holding.realized_pnl >= 0 ? '+' : '') + fmt(holding.realized_pnl) + ' ' + holding.currency}
            tone={holding.realized_pnl >= 0 ? 'pos' : 'neg'} />
        </div>
        <h3 style={{ marginTop: 16 }}>{t.panelTxns}</h3>
        {!txns && <div className="muted">{t.histLoading}</div>}
        {txns && txns.length === 0 && <div className="muted">{t.noTxns}</div>}
        {txns && txns.length > 0 && (
          <table className="tbl">
            <thead><tr><th>{t.hth.date}</th><th>{t.hth.type}</th><th>{t.hth.qty}</th><th>{t.hth.price}</th><th>{t.hth.fee}</th></tr></thead>
            <tbody>
              {txns.map((x) => (
                <tr key={x.id}>
                  <td>{x.date}</td>
                  <td><span className={`pill ${x.type}`}>{t.txnTypes[x.type] || x.type}</span></td>
                  <td>{x.quantity}</td><td>{x.price}</td><td>{x.fee}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

export default function Dashboard({ reloadKey, goTab }) {
  const { t } = useLang();
  const [data, setData] = useState(null);
  const [base, setBase] = useState('HKD');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState('');
  const [donutMode, setDonutMode] = useState('symbol');
  const [panel, setPanel] = useState(null);

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

  const donutItems = useMemo(() => {
    if (!data) return [];
    const vals = data.holdings.filter((h) => h.market_value_base);
    if (donutMode === 'market') {
      const g = {};
      vals.forEach((h) => {
        const k = h.market === 'HK' ? '🇭🇰 HK' : h.market === 'US' ? '🇺🇸 US' : h.market;
        g[k] = (g[k] || 0) + h.market_value_base;
      });
      return Object.entries(g).map(([label, value]) => ({ label, value }));
    }
    if (donutMode === 'currency') {
      const g = {};
      vals.forEach((h) => { g[h.currency] = (g[h.currency] || 0) + h.market_value_base; });
      return Object.entries(g).map(([label, value]) => ({ label, value }));
    }
    return vals.map((h) => ({ label: h.symbol, value: h.market_value_base }));
  }, [data, donutMode]);

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
  const asOf = data.quotes_as_of ? new Date(data.quotes_as_of) : null;
  const asOfStr = asOf ? asOf.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : null;
  const srcStr = data.quotes_source ? (t.srcName[data.quotes_source] || data.quotes_source) : null;

  return (
    <div>
      <div className="toolbar">
        <div className="seg">
          {['HKD', 'USD', 'CNY'].map((c) => (
            <button key={c} className={base === c ? 'seg-btn active' : 'seg-btn'} onClick={() => setBase(c)}>{c}</button>
          ))}
        </div>
        <div className="toolbar-right">
          {asOfStr && <span className="muted small">{t.asOf} {asOfStr}{srcStr ? ` · ${srcStr}` : ''}</span>}
          <button className="btn" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? t.refreshing : t.refresh}
          </button>
        </div>
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
        <StatCard label={t.div12m} value={fmt(data.dividends_12m)} sub={data.base_currency} />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>{t.netWorth}</h3>
        <HistoryChart base={base} />
      </div>

      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <h3>{t.allocation}</h3>
            <div className="seg small">
              {['symbol', 'market', 'currency'].map((m) => (
                <button key={m} className={donutMode === m ? 'seg-btn active' : 'seg-btn'}
                  onClick={() => setDonutMode(m)}>{t.donutModes[m]}</button>
              ))}
            </div>
          </div>
          <Donut items={donutItems} subLabel={donutMode === 'symbol' ? t.positions : ''} />
        </div>
        <div className="card">
          <h3>{t.holdings}</h3>
          <table className="tbl clickable">
            <thead>
              <tr><th>{t.th.symbol}</th><th>{t.th.qty}</th><th>{t.th.avgCost}</th><th>{t.th.price}</th><th>{t.th.dayChg}</th><th>{t.th.weight}</th><th>{t.th.value} ({data.base_currency})</th><th>{t.th.pnl}</th></tr>
            </thead>
            <tbody>
              {data.holdings.map((h) => (
                <tr key={h.instrument_id} onClick={() => setPanel(h)} title={t.panelTxns}>
                  <td><b>{h.symbol}</b> <span className="muted">{h.market}</span></td>
                  <td>{h.quantity}</td>
                  <td>{fmt(h.avg_cost)} {h.currency}</td>
                  <td>{h.latest_price ? fmt(h.latest_price) : <span className="muted">{t.stale}</span>}</td>
                  <td className={(h.day_change_base ?? 0) >= 0 ? 'pos' : 'neg'}>
                    {h.day_change_pct == null ? '—' : `${(h.day_change_pct * 100).toFixed(2)}%`}
                  </td>
                  <td>{h.weight_pct == null ? '—' : `${h.weight_pct}%`}</td>
                  <td>{fmt(h.market_value_base)}</td>
                  <td className={(h.unrealized_pnl_base ?? 0) >= 0 ? 'pos' : 'neg'}>
                    {(h.unrealized_pnl_base ?? 0) >= 0 ? '+' : ''}{fmt(h.unrealized_pnl_base)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.price_stale.length > 0 && (
            <div className="muted small">⚠ {t.noPriceFor}：{data.price_stale.join(', ')}</div>
          )}
        </div>
      </div>

      {panel && <HoldingPanel holding={panel} base={base} onClose={() => setPanel(null)} />}
    </div>
  );
}
