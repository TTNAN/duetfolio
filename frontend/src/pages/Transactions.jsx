import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useLang } from '../i18n.js';

const today = () => new Date().toISOString().slice(0, 10);

export default function Transactions({ onChange }) {
  const { t } = useLang();
  const [txns, setTxns] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const [err, setErr] = useState('');
  const [form, setForm] = useState({ instrument_id: '', type: 'buy', quantity: '', price: '', fee: '', date: today(), note: '' });

  const load = async () => {
    try {
      const [t2, ins] = await Promise.all([api.transactions(), api.instruments()]);
      setTxns(t2);
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
    if (!confirm(t.confirmDelTxn)) return;
    await api.deleteTransaction(id);
    await load();
    onChange && onChange();
  };

  return (
    <div className="grid2">
      <div className="card">
        <h3>{t.addTxn}</h3>
        {instruments.length === 0 && <div className="muted">{t.addInstFirst}</div>}
        <form onSubmit={submit} className="form">
          <label>{t.fInst}
            <select value={form.instrument_id} onChange={set('instrument_id')}>
              {instruments.map((i) => <option key={i.id} value={i.id}>{i.symbol} ({i.currency})</option>)}
            </select>
          </label>
          <div className="row2">
            <label>{t.fType}
              <select value={form.type} onChange={set('type')}>
                <option value="buy">{t.txnTypes.buy}</option>
                <option value="sell">{t.txnTypes.sell}</option>
                <option value="dividend">{t.txnTypes.dividend}</option>
              </select>
            </label>
            <label>{t.fDate}<input type="date" value={form.date} onChange={set('date')} /></label>
          </div>
          <div className="row2">
            <label>{t.fQty}<input type="number" step="any" min="0" required value={form.quantity} onChange={set('quantity')} placeholder="9" /></label>
            <label>{t.fPrice}<input type="number" step="any" min="0" required value={form.price} onChange={set('price')} placeholder="1134.65" /></label>
          </div>
          <div className="row2">
            <label>{t.fFee}<input type="number" step="any" min="0" value={form.fee} onChange={set('fee')} placeholder="0" /></label>
            <label>{t.fNote}<input value={form.note} onChange={set('note')} placeholder={t.optional} /></label>
          </div>
          <button className="btn primary" type="submit" disabled={!instruments.length}>{t.add}</button>
        </form>
        {err && <div className="error-text">{err}</div>}
      </div>
      <div className="card">
        <h3>{t.history}</h3>
        <table className="tbl">
          <thead><tr><th>{t.hth.date}</th><th>{t.hth.symbol}</th><th>{t.hth.type}</th><th>{t.hth.qty}</th><th>{t.hth.price}</th><th>{t.hth.fee}</th><th></th></tr></thead>
          <tbody>
            {txns.map((tx) => (
              <tr key={tx.id}>
                <td>{tx.date}</td><td><b>{tx.symbol}</b></td>
                <td><span className={`pill ${tx.type}`}>{t.txnTypes[tx.type] || tx.type}</span></td>
                <td>{tx.quantity}</td><td>{tx.price}</td><td>{tx.fee}</td>
                <td><button className="link danger" onClick={() => remove(tx.id)}>{t.del}</button></td>
              </tr>
            ))}
            {txns.length === 0 && <tr><td colSpan="7" className="muted">{t.noTxns}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
