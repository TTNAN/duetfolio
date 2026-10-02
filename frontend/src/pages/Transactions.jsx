import { useEffect, useState } from 'react';
import { api } from '../api.js';

const today = () => new Date().toISOString().slice(0, 10);

export default function Transactions({ onChange }) {
  const [txns, setTxns] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const [err, setErr] = useState('');
  const [form, setForm] = useState({ instrument_id: '', type: 'buy', quantity: '', price: '', fee: '', date: today(), note: '' });

  const load = async () => {
    try {
      const [t, ins] = await Promise.all([api.transactions(), api.instruments()]);
      setTxns(t);
      setInstruments(ins);
      if (!form.instrument_id && ins.length) setForm((f) => ({ ...f, instrument_id: String(ins[0].id) }));
    } catch (e) { setErr(String(e.message || e)); }
  };
  useEffect(() => { load(); }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setErr('');
    try {
      await api.addTransaction({
        instrument_id: Number(form.instrument_id),
        type: form.type,
        quantity: Number(form.quantity),
        price: Number(form.price),
        fee: Number(form.fee || 0),
        date: form.date,
        note: form.note,
      });
      setForm({ ...form, quantity: '', price: '', fee: '', note: '' });
      await load();
      onChange && onChange();
    } catch (e2) { setErr(String(e2.message || e2)); }
  };

  const remove = async (id) => {
    if (!confirm('Delete this transaction?')) return;
    await api.deleteTransaction(id);
    await load();
    onChange && onChange();
  };

  return (
    <div className="grid2">
      <div className="card">
        <h3>Add transaction</h3>
        {instruments.length === 0 && <div className="muted">Add an instrument first.</div>}
        <form onSubmit={submit} className="form">
          <label>Instrument
            <select value={form.instrument_id} onChange={set('instrument_id')}>
              {instruments.map((i) => <option key={i.id} value={i.id}>{i.symbol} ({i.currency})</option>)}
            </select>
          </label>
          <div className="row2">
            <label>Type
              <select value={form.type} onChange={set('type')}>
                <option value="buy">buy</option>
                <option value="sell">sell</option>
                <option value="dividend">dividend</option>
              </select>
            </label>
            <label>Date<input type="date" value={form.date} onChange={set('date')} /></label>
          </div>
          <div className="row2">
            <label>Quantity<input type="number" step="any" min="0" required value={form.quantity} onChange={set('quantity')} placeholder="9" /></label>
            <label>Price / share<input type="number" step="any" min="0" required value={form.price} onChange={set('price')} placeholder="1134.65" /></label>
          </div>
          <div className="row2">
            <label>Fee<input type="number" step="any" min="0" value={form.fee} onChange={set('fee')} placeholder="0" /></label>
            <label>Note<input value={form.note} onChange={set('note')} placeholder="optional" /></label>
          </div>
          <button className="btn primary" type="submit" disabled={!instruments.length}>Add</button>
        </form>
        {err && <div className="error-text">{err}</div>}
      </div>
      <div className="card">
        <h3>History</h3>
        <table className="tbl">
          <thead><tr><th>Date</th><th>Symbol</th><th>Type</th><th>Qty</th><th>Price</th><th>Fee</th><th></th></tr></thead>
          <tbody>
            {txns.map((t) => (
              <tr key={t.id}>
                <td>{t.date}</td><td><b>{t.symbol}</b></td>
                <td><span className={`pill ${t.type}`}>{t.type}</span></td>
                <td>{t.quantity}</td><td>{t.price}</td><td>{t.fee}</td>
                <td><button className="link danger" onClick={() => remove(t.id)}>delete</button></td>
              </tr>
            ))}
            {txns.length === 0 && <tr><td colSpan="7" className="muted">No transactions yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
