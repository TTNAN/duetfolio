import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useLang } from '../i18n.js';

export default function Instruments({ onChange }) {
  const { t } = useLang();
  const [list, setList] = useState([]);
  const [err, setErr] = useState('');
  const [form, setForm] = useState({ symbol: '', name: '', market: 'US', currency: 'USD', asset_type: 'etf' });
  const [sq, setSq] = useState('');
  const [hits, setHits] = useState(null);
  const [searching, setSearching] = useState(false);

  const doSearch = async (e) => {
    e && e.preventDefault();
    if (!sq.trim() || searching) return;
    setSearching(true);
    setHits(null);
    try {
      setHits(await api.searchInstruments(sq.trim()));
    } catch (e2) {
      setHits([]);
    } finally {
      setSearching(false);
    }
  };

  const pick = (h) => {
    setForm((f) => ({ ...f, symbol: h.symbol, name: h.name, market: h.market, currency: h.currency }));
    setHits(null);
    setSq('');
  };

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
    if (!confirm(t.confirmDelInst(symbol))) return;
    await api.deleteInstrument(id);
    await load();
    onChange && onChange();
  };

  return (
    <div className="grid2">
      <div className="card">
        <h3>{t.addInst}</h3>
        <form onSubmit={doSearch} className="form" style={{ marginBottom: 4 }}>
          <div className="row2" style={{ alignItems: 'end' }}>
            <label style={{ flex: 1 }}>{t.searchPh}
              <input value={sq} onChange={(e) => setSq(e.target.value)} placeholder="03152 / SGOV / 腾讯" />
            </label>
            <button className="btn" type="submit" disabled={searching || !sq.trim()}>
              {searching ? t.searching : t.search}
            </button>
          </div>
        </form>
        {hits && (
          <div className="search-hits">
            {hits.length === 0 && <div className="muted small">{t.searchNoHit}</div>}
            {hits.map((h, i) => (
              <button key={i} className="hit" onClick={() => pick(h)}>
                <b>{h.symbol}</b>
                <span className="muted">{h.name}</span>
                <span className="pill">{h.market} · {h.currency}</span>
              </button>
            ))}
          </div>
        )}
        {!hits && <div className="muted small" style={{ marginBottom: 8 }}>{t.searchHint}</div>}
        <form onSubmit={submit} className="form">
          <label>{t.fSymbol}
            <input required value={form.symbol} onChange={set('symbol')} placeholder={t.symPh} />
          </label>
          <label>{t.fName}<input value={form.name} onChange={set('name')} placeholder={t.namePh} /></label>
          <div className="row2">
            <label>{t.fMarket}
              <select value={form.market} onChange={set('market')}>
                <option value="US">US</option>
                <option value="HK">HK</option>
              </select>
            </label>
            <label>{t.fCcy}
              <select value={form.currency} onChange={set('currency')}>
                <option value="USD">USD</option>
                <option value="HKD">HKD</option>
              </select>
            </label>
          </div>
          <label>{t.fAsset}
            <select value={form.asset_type} onChange={set('asset_type')}>
              <option value="etf">{t.assetTypes.etf}</option>
              <option value="stock">{t.assetTypes.stock}</option>
              <option value="fund">{t.assetTypes.fund}</option>
            </select>
          </label>
          <button className="btn primary" type="submit">{t.add}</button>
        </form>
        {err && <div className="error-text">{err}</div>}
        <div className="muted small" style={{ marginTop: 12 }}>
          {t.instTip}
        </div>
      </div>
      <div className="card">
        <h3>{t.instList}</h3>
        <table className="tbl">
          <thead><tr><th>{t.ith.symbol}</th><th>{t.ith.name}</th><th>{t.ith.mkt}</th><th>{t.ith.ccy}</th><th></th></tr></thead>
          <tbody>
            {list.map((i) => (
              <tr key={i.id}>
                <td><b>{i.symbol}</b></td><td>{i.name || <span className="muted">—</span>}</td>
                <td>{i.market}</td><td>{i.currency}</td>
                <td><button className="link danger" onClick={() => remove(i.id, i.symbol)}>{t.del}</button></td>
              </tr>
            ))}
            {list.length === 0 && <tr><td colSpan="5" className="muted">{t.noInst}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
