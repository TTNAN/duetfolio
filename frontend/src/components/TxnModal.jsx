// Add / edit a transaction. Used from the global "Add" button, the holding
// drawer, and the activity list.
import { useEffect, useMemo, useState } from 'react';
import { api } from '../api.js';
import { useLang } from '../i18n.js';
import { money, qty as fq, todayISO } from '../format.js';
import { Modal, toast } from './ui.jsx';

export default function TxnModal({ initial, presetInstrumentId, onClose, onSaved, goInstruments }) {
  const { t } = useLang();
  const editing = !!initial;
  const [instruments, setInstruments] = useState(null);
  const [held, setHeld] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [refetchFx, setRefetchFx] = useState(false);
  const [f, setF] = useState(() => initial
    ? { instrument_id: String(initial.instrument_id), type: initial.type, quantity: String(initial.quantity),
        price: String(initial.price), fee: String(initial.fee || ''), date: initial.date, note: initial.note || '' }
    : { instrument_id: presetInstrumentId ? String(presetInstrumentId) : '', type: 'buy', quantity: '', price: '',
        fee: '', date: todayISO(), note: '' });

  useEffect(() => {
    api.instruments().then((ins) => {
      setInstruments(ins);
      if (!f.instrument_id && ins.length) setF((x) => ({ ...x, instrument_id: String(ins[0].id) }));
    }).catch((e) => setErr(e.message));
    api.summary('HKD').then((s) => {
      setHeld(Object.fromEntries(s.holdings.map((h) => [h.instrument_id, h.quantity])));
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const inst = instruments?.find((i) => String(i.id) === f.instrument_id);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const total = useMemo(() => {
    const q = Number(f.quantity), p = Number(f.price), fee = Number(f.fee || 0);
    if (!q || Number.isNaN(p)) return null;
    return f.type === 'buy' ? q * p + fee : q * p - fee;
  }, [f]);

  const submit = async (e) => {
    e.preventDefault();
    setErr('');
    setBusy(true);
    const body = {
      type: f.type, quantity: Number(f.quantity), price: Number(f.price),
      fee: Number(f.fee || 0), date: f.date, note: f.note,
    };
    try {
      if (editing) await api.updateTransaction(initial.id, { ...body, refetch_fx: refetchFx });
      else await api.addTransaction({ ...body, instrument_id: Number(f.instrument_id) });
      toast(editing ? t.saved : t.added);
      onSaved && onSaved();
      onClose();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  };

  if (instruments && instruments.length === 0) {
    return (
      <Modal title={t.addTxn} onClose={onClose}
        footer={<button className="btn primary" onClick={() => { onClose(); goInstruments && goInstruments(); }}>{t.goInst}</button>}>
        <p className="text-2" style={{ margin: 0 }}>{t.addInstFirst}</p>
      </Modal>
    );
  }

  const heldQty = inst ? held[inst.id] : null;
  const isDiv = f.type === 'dividend';

  return (
    <Modal title={editing ? t.editTxn : t.addTxn} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <div className="type-picker" role="radiogroup">
          {['buy', 'sell', 'dividend'].map((ty) => (
            <button key={ty} type="button" className={`${ty} ${f.type === ty ? 'on' : ''}`}
              onClick={() => setF({ ...f, type: ty })}>{t.txTypes[ty]}</button>
          ))}
        </div>
        <label className="field"><span>{t.fInst}</span>
          <select className="select" value={f.instrument_id} onChange={set('instrument_id')} disabled={editing || !instruments}>
            {(instruments || []).map((i) => (
              <option key={i.id} value={i.id}>{i.symbol} · {i.name || i.symbol} ({i.currency})</option>
            ))}
          </select>
        </label>
        <div className="row">
          <label className="field">
            <span style={{ display: 'flex', justifyContent: 'space-between' }}>
              {isDiv ? t.fDivQty : t.fQty}
              {heldQty > 0 && !editing && (
                f.type === 'buy'
                  ? <span className="muted">{t.holdingNow(fq(heldQty))}</span>
                  : <button type="button" className="btn ghost sm" style={{ height: 18, padding: '0 4px' }}
                      onClick={() => setF({ ...f, quantity: String(heldQty) })}>
                      {f.type === 'sell' ? t.sellAll : t.holdingNow(fq(heldQty))}
                    </button>
              )}
            </span>
            <input className="input num" type="number" step="any" min="0" required autoFocus={!editing}
              value={f.quantity} onChange={set('quantity')} placeholder="100" />
          </label>
          <label className="field"><span>{isDiv ? t.fDivPrice : t.fPrice}{inst ? ` (${inst.currency})` : ''}</span>
            <input className="input num" type="number" step="any" min="0" required
              value={f.price} onChange={set('price')} placeholder="0.00" />
          </label>
        </div>
        <div className="row">
          <label className="field"><span>{t.fDate}</span>
            <input className="input num" type="date" required value={f.date} onChange={set('date')} />
          </label>
          <label className="field"><span>{t.fFee}</span>
            <input className="input num" type="number" step="any" min="0" value={f.fee} onChange={set('fee')} placeholder="0" />
          </label>
        </div>
        <label className="field"><span>{t.fNote}</span>
          <input className="input" value={f.note} onChange={set('note')} placeholder={t.optional} />
        </label>
        {editing && (
          <div className="small muted" style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <span>{t.fxSaved}: <span className="num">{initial.fx_to_hkd ?? '—'}</span></span>
            <label className="check"><input type="checkbox" checked={refetchFx} onChange={(e) => setRefetchFx(e.target.checked)} />{t.refetchFx}</label>
          </div>
        )}
        {total != null && (
          <div className="form-total">
            <span className="text-2 small">{t.estTotal[f.type]}</span>
            <span className="num" style={{ fontSize: 18, fontWeight: 550 }}>{money(total)} <span className="muted small">{inst?.currency}</span></span>
          </div>
        )}
        {err && <div className="banner error" style={{ margin: 0 }}>{err}</div>}
        <div className="modal-foot" style={{ marginTop: 4 }}>
          <button type="button" className="btn ghost" onClick={onClose}>{t.cancel}</button>
          <button type="submit" className="btn primary" disabled={busy || !instruments}>{editing ? t.save : t.add}</button>
        </div>
      </form>
    </Modal>
  );
}
