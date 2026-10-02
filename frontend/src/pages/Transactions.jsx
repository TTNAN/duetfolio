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

  const [editing, setEditing] = useState(null); // transaction id in edit mode
  const [eform, setEform] = useState({});
  const [refetchFx, setRefetchFx] = useState(false);
  const startEdit = (tx) => {
    setEditing(tx.id);
    setEform({ type: tx.type, quantity: tx.quantity, price: tx.price, fee: tx.fee, date: tx.date, note: tx.note || '' });
    setRefetchFx(false);
    setErr('');
  };

  const eset = (k) => (e) => setEform({ ...eform, [k]: e.target.value });

  const saveEdit = async (id) => {
    setErr('');
    try {
      await api.updateTransaction(id, {
        type: eform.type,
        quantity: Number(eform.quantity),
        price: Number(eform.price),
        fee: Number(eform.fee || 0),
        date: eform.date,
        note: eform.note,
        refetch_fx: refetchFx,
      });
      setEditing(null);
      await load();
      onChange && onChange();
    } catch (e2) { setErr(String(e2.message || e2)); }
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
              editing === tx.id ? (
                <>
                  <tr key={tx.id} className="editing">
                    <td><input type="date" value={eform.date} onChange={eset('date')} /></td>
                    <td><b>{tx.symbol}</b></td>
                    <td>
                      <select value={eform.type} onChange={eset('type')}>
                        <option value="buy">{t.txnTypes.buy}</option>
                        <option value="sell">{t.txnTypes.sell}</option>
                        <option value="dividend">{t.txnTypes.dividend}</option>
                      </select>
                    </td>
                    <td><input type="number" step="any" min="0" value={eform.quantity} onChange={eset('quantity')} /></td>
                    <td><input type="number" step="any" min="0" value={eform.price} onChange={eset('price')} /></td>
                    <td><input type="number" step="any" min="0" value={eform.fee} onChange={eset('fee')} /></td>
                    <td>
                      <button className="link" onClick={() => saveEdit(tx.id)}>{t.save}</button>
                      {' · '}
                      <button className="link muted" onClick={() => setEditing(null)}>{t.cancel}</button>
                    </td>
                  </tr>
                  <tr key={`${tx.id}-fx`} className="fxrow">
                    <td colSpan="7">
                      <span className="muted small">{t.fxSaved}：{tx.fx_to_hkd ?? '—'}</span>
                      {' · '}
                      <label className="muted small">
                        <input type="checkbox" checked={refetchFx} onChange={(e) => setRefetchFx(e.target.checked)} />
                        {' '}{t.refetchFx}
                      </label>
                    </td>
                  </tr>
                </>
              ) : (
                <tr key={tx.id}>
                  <td>{tx.date}</td><td><b>{tx.symbol}</b></td>
                  <td><span className={`pill ${tx.type}`}>{t.txnTypes[tx.type] || tx.type}</span></td>
                  <td>{tx.quantity}</td><td>{tx.price}</td><td>{tx.fee}</td>
                  <td>
                    <button className="link" onClick={() => startEdit(tx)}>{t.edit}</button>
                    {' · '}
                    <button className="link danger" onClick={() => remove(tx.id)}>{t.del}</button>
                  </td>
                </tr>
              )
            ))}
            {txns.length === 0 && <tr><td colSpan="7" className="muted">{t.noTxns}</td></tr>}
          </tbody>
        </table>
      </div>
      <CashCard onChange={onChange} />
      <ImportCard onChange={onChange} />
    </div>
  );
}

function CashCard({ onChange }) {
  const { t } = useLang();
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ direction: 'in', amount: '', currency: 'HKD', date: today(), note: '' });
  const [err, setErr] = useState('');

  const load = async () => {
    try { setList(await api.cash()); } catch (e) { setErr(String(e.message || e)); }
  };
  useEffect(() => { load(); }, []);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setErr('');
    try {
      await api.addCash({
        direction: form.direction, amount: Number(form.amount),
        currency: form.currency, date: form.date, note: form.note,
      });
      setForm({ ...form, amount: '', note: '' });
      await load();
      onChange && onChange();
    } catch (e2) { setErr(String(e2.message || e2)); }
  };

  const remove = async (id) => {
    if (!confirm(t.confirmDelTxn)) return;
    await api.deleteCash(id);
    await load();
    onChange && onChange();
  };

  return (
    <div className="card">
      <h3>{t.cashTitle}</h3>
      <form onSubmit={submit} className="form">
        <div className="row2">
          <label>{t.fDirection}
            <select value={form.direction} onChange={set('direction')}>
              <option value="in">{t.cashIn}</option>
              <option value="out">{t.cashOut}</option>
            </select>
          </label>
          <label>{t.fDate}<input type="date" value={form.date} onChange={set('date')} /></label>
        </div>
        <div className="row2">
          <label>{t.fAmount}<input type="number" step="any" min="0" required value={form.amount} onChange={set('amount')} placeholder="10000" /></label>
          <label>{t.fCcy}
            <select value={form.currency} onChange={set('currency')}>
              <option value="HKD">HKD</option>
              <option value="USD">USD</option>
              <option value="CNY">CNY</option>
            </select>
          </label>
        </div>
        <label>{t.fNote}<input value={form.note} onChange={set('note')} placeholder={t.optional} /></label>
        <button className="btn primary" type="submit">{t.add}</button>
      </form>
      {err && <div className="error-text">{err}</div>}
      <table className="tbl" style={{ marginTop: 12 }}>
        <thead><tr><th>{t.hth.date}</th><th>{t.fDirection}</th><th>{t.fAmount}</th><th></th></tr></thead>
        <tbody>
          {list.map((c) => (
            <tr key={c.id}>
              <td>{c.date}</td>
              <td><span className={`pill ${c.direction === 'in' ? 'buy' : 'sell'}`}>
                {c.direction === 'in' ? t.cashIn : t.cashOut}
              </span></td>
              <td>{c.direction === 'in' ? '-' : '+'}{c.amount} {c.currency}</td>
              <td><button className="link danger" onClick={() => remove(c.id)}>{t.del}</button></td>
            </tr>
          ))}
          {list.length === 0 && <tr><td colSpan="4" className="muted">{t.noCash}</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function ImportCard({ onChange }) {
  const { t } = useLang();
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [done, setDone] = useState('');

  const onFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true); setErr(''); setDone(''); setPreview(null);
    try {
      setPreview(await api.importPreview(f));
    } catch (e2) { setErr(String(e2.message || e2)); }
    finally { setBusy(false); e.target.value = ''; }
  };

  const confirm = async () => {
    const rows = (preview?.rows || []).filter((r) => r.status === 'ok');
    if (!rows.length) return;
    setBusy(true); setErr('');
    try {
      const r = await api.importConfirm(rows);
      setDone(`${t.importDone}: +${r.imported}, errors ${r.errors.length}`);
      setPreview(null);
      onChange && onChange();
    } catch (e2) { setErr(String(e2.message || e2)); }
    finally { setBusy(false); }
  };

  const rows = preview?.rows || [];
  const okCount = rows.filter((r) => r.status === 'ok').length;

  return (
    <div className="card">
      <h3>{t.importTitle}</h3>
      <div className="muted small" style={{ marginBottom: 8 }}>{t.importHint}</div>
      <label className="btn">
        {t.chooseFile}
        <input type="file" accept=".csv" onChange={onFile} style={{ display: 'none' }} />
      </label>
      {busy && <div className="muted" style={{ marginTop: 8 }}>{t.histLoading}</div>}
      {err && <div className="error-text">{err}</div>}
      {done && <div className="ok-text">{done}</div>}
      {preview && (
        <div style={{ marginTop: 12 }}>
          <div className="muted small" style={{ marginBottom: 6 }}>
            {preview.format} · {okCount} / {rows.length} OK
          </div>
          <div style={{ maxHeight: 260, overflowY: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>#</th><th>{t.hth.date}</th><th>{t.hth.symbol}</th><th>{t.hth.type}</th><th>{t.hth.qty}</th><th>{t.hth.price}</th><th></th></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className={r.status === 'ok' ? '' : r.status === 'skip' ? 'muted' : 'error-row'}>
                    <td>{r.lineno}</td>
                    <td>{r.date || '—'}</td>
                    <td><b>{r.symbol || '—'}</b></td>
                    <td>{r.type ? (t.txnTypes[r.type] || r.type) : '—'}</td>
                    <td>{r.quantity ?? '—'}</td>
                    <td>{r.price ?? '—'}</td>
                    <td className="muted small">{r.status === 'ok' ? '' : r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button className="btn primary" style={{ marginTop: 8 }} disabled={!okCount || busy} onClick={confirm}>
            {t.confirmImport} ({okCount})
          </button>
        </div>
      )}
    </div>
  );
}
