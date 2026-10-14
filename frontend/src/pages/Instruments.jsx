import { useEffect, useRef, useState } from 'react';
import { Search, Plus, Trash2, Check, Pencil, Loader2 } from 'lucide-react';
import { api } from '../api.js';
import { useLang } from '../i18n.js';
import { Seg, Skeleton, SymBadge, toast } from '../components/ui.jsx';

const EMPTY = { symbol: '', name: '', market: 'US', currency: 'USD', asset_type: 'stock' };

function guessType(name) {
  return /etf|fund|trust|基金|货币|tracker|盈富|ishares|vanguard|spdr|invesco/i.test(name || '') ? 'etf' : 'stock';
}

export default function Instruments({ reloadKey, reload, openAdd }) {
  const { t } = useLang();
  const [list, setList] = useState(null);
  const [counts, setCounts] = useState({});
  const [q, setQ] = useState('');
  const [hits, setHits] = useState(null);
  const [searching, setSearching] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [manual, setManual] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [renaming, setRenaming] = useState(null);
  const seq = useRef(0);

  const load = () => {
    api.instruments().then(setList).catch((e) => { toast(e.message, 'error'); setList([]); });
    api.transactions().then((tx) => {
      const c = {};
      tx.forEach((x) => { c[x.instrument_id] = (c[x.instrument_id] || 0) + 1; });
      setCounts(c);
    }).catch(() => {});
  };
  useEffect(load, [reloadKey]);

  // debounced type-ahead search
  useEffect(() => {
    const term = q.trim();
    if (!term) { setHits(null); return undefined; }
    const my = ++seq.current;
    const id = setTimeout(async () => {
      setSearching(true);
      try {
        const r = await api.searchInstruments(term);
        if (my === seq.current) { setHits(r); setCursor(0); }
      } catch { if (my === seq.current) setHits([]); } finally { if (my === seq.current) setSearching(false); }
    }, 350);
    return () => clearTimeout(id);
  }, [q]);

  const have = new Set((list || []).map((i) => i.symbol));

  const add = async (body) => {
    try {
      const inst = await api.addInstrument({ ...body, symbol: body.symbol.trim().toUpperCase() });
      toast(t.instAdded(inst.symbol));
      setQ(''); setHits(null); setForm(EMPTY); setManual(false);
      reload();
      return inst;
    } catch (e) { toast(e.message, 'error'); return null; }
  };
  const pick = (h) => {
    if (have.has(h.symbol)) return;
    add({ symbol: h.symbol, name: h.name, market: h.market, currency: h.currency, asset_type: guessType(h.name) });
  };
  const onKey = (e) => {
    if (!hits?.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setCursor((c) => Math.min(hits.length - 1, c + 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
    if (e.key === 'Enter') { e.preventDefault(); pick(hits[cursor]); }
  };
  const remove = async (i) => {
    if (!window.confirm(t.confirmDelInst(i.symbol))) return;
    await api.deleteInstrument(i.id); toast(t.deleted); reload();
  };
  const saveName = async () => {
    try { await api.updateInstrument(renaming.id, { name: renaming.name }); setRenaming(null); toast(t.saved); reload(); }
    catch (e) { toast(e.message, 'error'); }
  };
  const setF = (k) => (e) => {
    const v = { ...form, [k]: e.target.value };
    if (k === 'market') v.currency = e.target.value === 'HK' ? 'HKD' : 'USD';
    setForm(v);
  };

  return (
    <>
      <div className="page-head">
        <div><h1 className="page-title">{t.instTitle}</h1><div className="page-sub">{t.instSub}</div></div>
      </div>
      <div className="grid grid-main">
        <section className="card">
          {!list ? <Skeleton h={200} /> : (
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th className="l">{t.ith.symbol}</th><th className="l">{t.ith.mkt}</th><th className="l hide-sm">{t.ith.type}</th><th>{t.ith.txns}</th><th /></tr></thead>
                <tbody>
                  {list.map((i) => (
                    <tr key={i.id}>
                      <td className="l">
                        <div className="sym">
                          <SymBadge symbol={i.symbol} market={i.market} />
                          <div style={{ minWidth: 0 }}>
                            <div className="sym-name">{i.symbol}</div>
                            {renaming?.id === i.id ? (
                              <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                                <input className="input sm" autoFocus value={renaming.name}
                                  onChange={(e) => setRenaming({ ...renaming, name: e.target.value })}
                                  onKeyDown={(e) => { if (e.key === 'Enter') saveName(); if (e.key === 'Escape') setRenaming(null); }} />
                                <button className="btn sm icon" onClick={saveName}><Check size={14} /></button>
                              </div>
                            ) : <div className="sym-desc">{i.name}</div>}
                          </div>
                        </div>
                      </td>
                      <td className="l"><span className="tag">{i.market} · {i.currency}</span></td>
                      <td className="l hide-sm text-2">{t.assetTypes[i.asset_type] || i.asset_type}</td>
                      <td className="text-2">{counts[i.id] || 0}</td>
                      <td>
                        <span className="row-actions">
                          <button className="btn ghost sm icon" title={t.addTxn} onClick={() => openAdd(i.id)}><Plus size={14} /></button>
                          <button className="btn ghost sm icon" title={t.edit} onClick={() => setRenaming({ id: i.id, name: i.name })}><Pencil size={14} /></button>
                          <button className="btn ghost sm icon danger" title={t.del} onClick={() => remove(i)}><Trash2 size={14} /></button>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {list.length === 0 && <div className="empty">{t.noInst}</div>}
            </div>
          )}
        </section>

        <section className="card">
          <div className="input-wrap">
            {searching ? <Loader2 size={15} className="spin" /> : <Search size={15} />}
            <input className="input" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey}
              placeholder={t.searchPh} autoFocus />
          </div>
          {hits && (
            <div className="hits">
              {hits.length === 0 && !searching && <div className="hit muted small" style={{ cursor: 'default' }}>{t.searchNoHit}</div>}
              {hits.map((h, i) => (
                <button key={h.symbol + i} className={`hit ${i === cursor ? 'on' : ''}`} onMouseEnter={() => setCursor(i)} onClick={() => pick(h)}>
                  <SymBadge symbol={h.symbol} market={h.market} />
                  <div className="grow"><div><b>{h.symbol}</b></div><div>{h.name}</div></div>
                  {have.has(h.symbol) ? <span className="tag">{t.exists}</span> : <span className="tag">{h.market}</span>}
                </button>
              ))}
            </div>
          )}
          {!hits && <div className="small muted" style={{ marginTop: 10 }}>{t.searchHint}</div>}
          <div style={{ marginTop: 14 }}>
            <button className="btn ghost sm" onClick={() => setManual((m) => !m)}>{t.manual}</button>
          </div>
          {manual && (
            <form className="form" style={{ marginTop: 12 }} onSubmit={(e) => { e.preventDefault(); add(form); }}>
              <div className="small muted">{t.manualHint}</div>
              <label className="field"><span>{t.fSymbol}</span><input className="input" required value={form.symbol} onChange={setF('symbol')} placeholder="AAPL / 700.HK" /></label>
              <label className="field"><span>{t.fName}</span><input className="input" value={form.name} onChange={setF('name')} placeholder={t.optional} /></label>
              <div className="row">
                <label className="field"><span>{t.fMarket}</span>
                  <select className="select" value={form.market} onChange={setF('market')}><option>US</option><option>HK</option></select></label>
                <label className="field"><span>{t.fCcy}</span>
                  <select className="select" value={form.currency} onChange={setF('currency')}><option>USD</option><option>HKD</option></select></label>
              </div>
              <div className="field"><span>{t.fAsset}</span>
                <Seg value={form.asset_type} onChange={(v) => setForm({ ...form, asset_type: v })}
                  options={['stock', 'etf', 'fund'].map((k) => ({ value: k, label: t.assetTypes[k] }))} /></div>
              <button className="btn primary" type="submit"><Plus size={15} />{t.add}</button>
            </form>
          )}
        </section>
      </div>
    </>
  );
}
