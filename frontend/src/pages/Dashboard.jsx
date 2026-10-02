import { useEffect, useState } from 'react';
import { api } from '../api.js';
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

export default function Dashboard({ reloadKey }) {
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
      setErr('API unreachable — is the backend running on :8000?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(base); }, [base, reloadKey]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const r = await api.refreshPrices();
      if (r.failed?.length) setErr(`Price fetch failed: ${r.failed.join(', ')}`);
      await load(base);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) return <div className="card">Loading…</div>;
  if (err && !data) return <div className="card error">{err}</div>;

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
          {refreshing ? 'Refreshing…' : '⟳ Refresh prices'}
        </button>
      </div>
      {err && <div className="card error">{err}</div>}
      {(data.price_stale?.length > 0 || data.fx_stale?.length > 0) && (
        <div className="card warn">
          数据不完整，总数已隐藏：
          {data.price_stale?.length > 0 && ` ${data.price_stale.join(', ')} 缺行情；`}
          {data.fx_stale?.length > 0 && ` ${data.fx_stale.join(', ')} 汇率缺失`}
        </div>
      )}

      <div className="stats">
        <StatCard label={`Total value (${data.base_currency})`} value={fmt(data.total_value)} sub={data.fx_usd_to_base ? `USD/${data.base_currency} ${data.fx_usd_to_base.toFixed(4)}` : ''} />
        <StatCard label="Invested" value={fmt(data.total_invested)} />
        <StatCard label="Total P&L" value={data.total_pnl == null ? '—' : (data.total_pnl >= 0 ? '+' : '') + fmt(data.total_pnl)} tone={pnlTone} sub={data.realized_pnl != null && data.unrealized_pnl != null ? `realized ${fmt(data.realized_pnl)} · unrealized ${fmt(data.unrealized_pnl)}` : ''} />
        <StatCard label="XIRR (annualized)" value={data.xirr === null ? '—' : (data.xirr * 100).toFixed(2) + '%'} sub="incl. dividends & terminal value" tone={pnlTone} />
      </div>

      <div className="grid2">
        <div className="card">
          <h3>Allocation</h3>
          <Donut items={donutItems} />
        </div>
        <div className="card">
          <h3>Holdings</h3>
          <table className="tbl">
            <thead>
              <tr><th>Symbol</th><th>Qty</th><th>Avg cost</th><th>Price</th><th>Value ({data.base_currency})</th><th>P&L</th></tr>
            </thead>
            <tbody>
              {data.holdings.map((h) => (
                <tr key={h.instrument_id}>
                  <td><b>{h.symbol}</b> <span className="muted">{h.market}</span></td>
                  <td>{h.quantity}</td>
                  <td>{fmt(h.avg_cost)} {h.currency}</td>
                  <td>{h.latest_price ? fmt(h.latest_price) : <span className="muted">stale</span>}</td>
                  <td>{fmt(h.market_value_base)}</td>
                  <td className={(h.unrealized_pnl_base ?? 0) >= 0 ? 'pos' : 'neg'}>
                    {(h.unrealized_pnl_base ?? 0) >= 0 ? '+' : ''}{fmt(h.unrealized_pnl_base)}
                  </td>
                </tr>
              ))}
              {data.holdings.length === 0 && (
                <tr><td colSpan="6" className="muted">No instruments yet — add some under Instruments.</td></tr>
              )}
            </tbody>
          </table>
          {data.price_stale.length > 0 && (
            <div className="muted small">⚠ no price for: {data.price_stale.join(', ')}</div>
          )}
        </div>
      </div>
    </div>
  );
}
