import { useEffect, useState } from 'react';
import { api } from '../api.js';

export default function Instruments({ onChange }) {
  const [list, setList] = useState([]);
  const [err, setErr] = useState('');
  const [form, setForm] = useState({ symbol: '', name: '', market: 'US', currency: 'USD', asset_type: 'etf' });

  const load = async () => {
    try { setList(await api.instruments()); }
    catch (e) { setErr(String(e.message || e)); }
  };
  useEffect(() => { load(); }, []);

  const set = (k) => (e) => {
    const v = { ...form, [k]: e.target.value };
    // sensible defaults per market
    if (k === 'market') v.currency = e.target.value === 'HK' ? 'HKD' : 'USD';
    setForm(v);
  };

  const submit = async (e) => {
    e.preventDefault();
    setErr('');
    try {
      await api.addInstrument({ ...form, symbol: form.symbol.trim().toUpperCase() });
      setForm({ symbol: '', name: '', market: 'US', currency: 'USD', asset_type: 'etf' });
      await load();
      onChange && onChange();
    } catch (e2) { setErr(String(e2.message || e2)); }
  };

  const remove = async (id, symbol) => {
    if (!confirm(`Delete ${symbol} and ALL its transactions?`)) return;
    await api.deleteInstrument(id);
    await load();
    onChange && onChange();
  };

  return (
    <div className="grid2">
      <div className="card">
        <h3>Add instrument</h3>
        <form onSubmit={submit} className="form">
          <label>Symbol (Yahoo ticker)
            <input required value={form.symbol} onChange={set('symbol')} placeholder="SGOV or 03152.HK" />
          </label>
          <label>Name<input value={form.name} onChange={set('name')} placeholder="iShares 0-3 Month Treasury Bond ETF" /></label>
          <div className="row2">
            <label>Market
              <select value={form.market} onChange={set('market')}>
                <option value="US">US</option>
                <option value="HK">HK</option>
              </select>
            </label>
            <label>Currency
              <select value={form.currency} onChange={set('currency')}>
                <option value="USD">USD</option>
                <option value="HKD">HKD</option>
              </select>
            </label>
          </div>
          <label>Type
            <select value={form.asset_type} onChange={set('asset_type')}>
              <option value="etf">ETF</option>
              <option value="stock">Stock</option>
              <option value="fund">Fund</option>
            </select>
          </label>
          <button className="btn primary" type="submit">Add</button>
        </form>
        {err && <div className="error-text">{err}</div>}
        <div className="muted small" style={{ marginTop: 12 }}>
          Tip: Yahoo drops the leading zero on 5-digit HK codes — e.g. enter <code>3152.HK</code> for 03152 (Bosera HKD Money Market ETF). US tickers as-is (e.g. <code>SGOV</code>).
        </div>
      </div>
      <div className="card">
        <h3>Instruments</h3>
        <table className="tbl">
          <thead><tr><th>Symbol</th><th>Name</th><th>Mkt</th><th>Ccy</th><th></th></tr></thead>
          <tbody>
            {list.map((i) => (
              <tr key={i.id}>
                <td><b>{i.symbol}</b></td><td>{i.name || <span className="muted">—</span>}</td>
                <td>{i.market}</td><td>{i.currency}</td>
                <td><button className="link danger" onClick={() => remove(i.id, i.symbol)}>delete</button></td>
              </tr>
            ))}
            {list.length === 0 && <tr><td colSpan="5" className="muted">Nothing here yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
