import { useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Search, Pencil, Trash2, Download, Upload, FileSpreadsheet } from 'lucide-react';
import { api } from '../api.js';
import { useLang } from '../i18n.js';
import { usePrefs } from '../prefs.js';
import { money, qty, mask, todayISO } from '../format.js';
import { Seg, Skeleton, SymBadge, toast } from '../components/ui.jsx';
import TxnModal from '../components/TxnModal.jsx';

function Trades({ reloadKey, reload, openAdd, privacy }) {
  const { t } = useLang();
  const [txns, setTxns] = useState(null);
  const [insts, setInsts] = useState({});
  const [type, setType] = useState('all');
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState(null);

  useEffect(() => {
    Promise.all([api.transactions(), api.instruments()]).then(([tx, ins]) => {
      setTxns(tx);
      setInsts(Object.fromEntries(ins.map((i) => [i.id, i])));
    }).catch((e) => { toast(e.message, 'error'); setTxns([]); });
  }, [reloadKey]);

  const rows = useMemo(() => (txns || []).filter((x) =>
    (type === 'all' || x.type === type) &&
    (!q || `${x.symbol} ${insts[x.instrument_id]?.name || ''} ${x.note || ''}`.toLowerCase().includes(q.toLowerCase()))),
  [txns, type, q, insts]);

  const remove = async (x) => {
    if (!window.confirm(t.confirmDelTxn)) return;
    try { await api.deleteTransaction(x.id); toast(t.deleted); reload(); } catch (e) { toast(e.message, 'error'); }
  };
  const m = (s) => mask(s, privacy);

  return (
    <section className="card">
      <div className="toolbar">
        <div className="input-wrap grow">
          <Search size={15} />
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t.searchTx} />
        </div>
        <Seg value={type} onChange={setType} options={[
          { value: 'all', label: t.filterAll }, { value: 'buy', label: t.txTypes.buy },
          { value: 'sell', label: t.txTypes.sell }, { value: 'dividend', label: t.txTypes.dividend }]} />
        <a className="btn" href={api.exportCsvUrl()}><Download size={15} />{t.exportCsv}</a>
        <button className="btn primary" onClick={() => openAdd()}><Plus size={15} />{t.addTxn}</button>
      </div>
      {!txns ? <Skeleton h={220} /> : (
        <div className="table-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th className="l">{t.hth.date}</th><th className="l">{t.hth.symbol}</th><th className="l">{t.hth.type}</th>
                <th>{t.hth.qty}</th><th>{t.hth.price}</th><th className="hide-sm">{t.hth.fee}</th><th>{t.hth.amount}</th>
                <th className="l hide-sm">{t.hth.note}</th><th />
              </tr>
            </thead>
            <tbody>
              {rows.map((x) => {
                const inst = insts[x.instrument_id] || {};
                const gross = x.quantity * x.price;
                const amt = x.type === 'buy' ? -(gross + x.fee) : gross - x.fee;
                const isSplit = x.type === 'split';
                return (
                  <tr key={x.id}>
                    <td className="l num text-2">{x.date}</td>
                    <td className="l"><div className="sym"><SymBadge symbol={x.symbol} market={inst.market} />
                      <div><div className="sym-name">{x.symbol}</div><div className="sym-desc">{inst.name}</div></div></div></td>
                    <td className="l"><span className={`tag ${x.type}`}>{t.txTypes[x.type]}</span></td>
                    <td>{isSplit ? t.splitShort(qty(x.quantity)) : m(qty(x.quantity))}</td>
                    <td>{isSplit ? '—' : money(x.price, x.price < 10 ? 3 : 2)}</td>
                    <td className="hide-sm text-2">{x.fee ? money(x.fee) : '—'}</td>
                    <td>{isSplit ? <span className="muted">—</span> : <>{m((amt > 0 ? '+' : '−') + money(Math.abs(amt)))}<span className="sub">{inst.currency}</span></>}</td>
                    <td className="l hide-sm muted" style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>{x.note}</td>
                    <td>
                      <span className="row-actions">
                        <button className="btn ghost sm icon" title={t.edit} onClick={() => setEditing(x)}><Pencil size={14} /></button>
                        <button className="btn ghost sm icon danger" title={t.del} onClick={() => remove(x)}><Trash2 size={14} /></button>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {rows.length === 0 && <div className="empty">{txns.length ? t.noMatch : t.noTxns}</div>}
        </div>
      )}
      {txns && txns.length > 0 && <div className="list-foot"><span>{t.count(rows.length)}</span></div>}
      {editing && <TxnModal initial={editing} onClose={() => setEditing(null)} onSaved={reload} />}
    </section>
  );
}

function Cash({ reloadKey, reload, privacy }) {
  const { t } = useLang();
  const [list, setList] = useState(null);
  const [f, setF] = useState({ direction: 'in', amount: '', currency: 'HKD', date: todayISO(), note: '' });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  useEffect(() => { api.cash().then(setList).catch(() => setList([])); }, [reloadKey]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.addCash({ ...f, amount: Number(f.amount) });
      setF({ ...f, amount: '', note: '' });
      toast(t.added);
      reload();
    } catch (e2) { toast(e2.message, 'error'); }
  };
  const remove = async (id) => {
    if (!window.confirm(t.confirmDelTxn)) return;
    await api.deleteCash(id); toast(t.deleted); reload();
  };

  return (
    <div className="grid grid-main">
      <section className="card">
        <div className="card-head"><div><h3 className="card-title">{t.cashTitle}</h3><div className="card-sub">{t.cashSub}</div></div></div>
        {!list ? <Skeleton h={120} /> : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th className="l">{t.hth.date}</th><th className="l">{t.fDirection}</th><th>{t.fAmount}</th><th className="l hide-sm">{t.hth.note}</th><th /></tr></thead>
              <tbody>
                {list.map((c) => (
                  <tr key={c.id}>
                    <td className="l num text-2">{c.date}</td>
                    <td className="l"><span className={`tag ${c.direction}`}>{c.direction === 'in' ? t.cashIn : t.cashOut}</span></td>
                    <td>{mask(money(c.amount), privacy)} <span className="muted small">{c.currency}</span></td>
                    <td className="l hide-sm muted">{c.note}</td>
                    <td><span className="row-actions"><button className="btn ghost sm icon danger" onClick={() => remove(c.id)}><Trash2 size={14} /></button></span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {list.length === 0 && <div className="empty">{t.noCash}</div>}
          </div>
        )}
      </section>
      <section className="card">
        <form className="form" onSubmit={submit}>
          <Seg value={f.direction} onChange={(v) => setF({ ...f, direction: v })}
            options={[{ value: 'in', label: t.cashIn }, { value: 'out', label: t.cashOut }]} />
          <div className="row">
            <label className="field"><span>{t.fAmount}</span><input className="input num" type="number" step="any" min="0" required value={f.amount} onChange={set('amount')} placeholder="10000" /></label>
            <label className="field"><span>{t.fCcy}</span>
              <select className="select" value={f.currency} onChange={set('currency')}>{['HKD', 'USD', 'CNY'].map((c) => <option key={c}>{c}</option>)}</select>
            </label>
          </div>
          <label className="field"><span>{t.fDate}</span><input className="input num" type="date" required value={f.date} onChange={set('date')} /></label>
          <label className="field"><span>{t.fNote}</span><input className="input" value={f.note} onChange={set('note')} placeholder={t.optional} /></label>
          <button className="btn primary" type="submit"><Plus size={15} />{t.add}</button>
        </form>
      </section>
    </div>
  );
}

function Import({ reload }) {
  const { t } = useLang();
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [broker, setBroker] = useState(() => localStorage.getItem('df-broker') || 'auto');
  const input = useRef(null);
  useEffect(() => { localStorage.setItem('df-broker', broker); }, [broker]);

  const onFile = async (file) => {
    if (!file) return;
    setBusy(true); setPreview(null);
    try { setPreview(await api.importPreview(file, broker)); } catch (e) { toast(e.message, 'error'); } finally { setBusy(false); }
  };
  const rows = preview?.rows || [];
  const ok = rows.filter((r) => r.status === 'ok');
  const confirm = async () => {
    setBusy(true);
    try {
      const r = await api.importConfirm(ok);
      toast(t.importDone(r.imported, r.errors.length), r.errors.length ? 'error' : 'ok');
      setPreview(null); reload();
    } catch (e) { toast(e.message, 'error'); } finally { setBusy(false); }
  };

  return (
    <section className="card">
      <div className="card-head"><div><h3 className="card-title">{t.importTitle}</h3><div className="card-sub">{t.importHint}</div></div></div>
      <div className="broker-pick" role="radiogroup" aria-label={t.brokerLabel}>
        <span className="small muted">{t.brokerLabel}</span>
        {Object.keys(t.brokers).map((b) => (
          <button key={b} type="button" role="radio" aria-checked={broker === b}
            className={`pick ${broker === b ? 'on' : ''}`} onClick={() => setBroker(b)}>{t.brokers[b]}</button>
        ))}
      </div>
      <div className={`dropzone ${over ? 'over' : ''}`} onClick={() => input.current?.click()}
        role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.current?.click(); } }}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0]); }}>
        <FileSpreadsheet size={28} strokeWidth={1.4} />
        <div>{busy ? t.parsing : t.dropHere}</div>
        <input ref={input} type="file" accept=".csv" hidden onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ''; }} />
      </div>
      {preview && (
        <div style={{ marginTop: 18 }}>
          <div className="card-head" style={{ marginBottom: 10 }}>
            <span className="text-2 small">{t.previewLine(t.brokers[preview.format === 'table' ? 'generic' : preview.format] || preview.format, ok.length, rows.length)}</span>
            <button className="btn primary" disabled={!ok.length || busy} onClick={confirm}><Upload size={15} />{t.confirmImport(ok.length)}</button>
          </div>
          <div className="table-wrap" style={{ maxHeight: 360, overflowY: 'auto' }}>
            <table className="tbl">
              <thead><tr><th className="l">#</th><th className="l">{t.hth.date}</th><th className="l">{t.hth.symbol}</th><th className="l">{t.hth.type}</th><th>{t.hth.qty}</th><th>{t.hth.price}</th><th className="l" /></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} style={{ opacity: r.status === 'ok' ? 1 : 0.55 }}>
                    <td className="l muted">{r.lineno}</td>
                    <td className="l num">{r.date || '—'}</td>
                    <td className="l"><b>{r.symbol || '—'}</b></td>
                    <td className="l">{r.type ? <span className={`tag ${r.type}`}>{t.txTypes[r.type] || r.type}</span> : '—'}</td>
                    <td>{r.quantity ?? '—'}</td>
                    <td>{r.price ?? '—'}</td>
                    <td className={`l small ${r.status === 'error' ? 'down' : 'muted'}`}>{r.status === 'ok' ? '' : r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

export default function Transactions({ reloadKey, reload, openAdd }) {
  const { t } = useLang();
  const [prefs] = usePrefs();
  const [tab, setTab] = useState('trades');
  return (
    <>
      <div className="page-head">
        <div><h1 className="page-title">{t.txTitle}</h1><div className="page-sub">{t.txSub}</div></div>
        <Seg value={tab} onChange={setTab} options={['trades', 'cash', 'import'].map((k) => ({ value: k, label: t.tabs[k] }))} />
      </div>
      {tab === 'trades' && <Trades reloadKey={reloadKey} reload={reload} openAdd={openAdd} privacy={prefs.privacy} />}
      {tab === 'cash' && <Cash reloadKey={reloadKey} reload={reload} privacy={prefs.privacy} />}
      {tab === 'import' && <Import reload={reload} />}
    </>
  );
}
