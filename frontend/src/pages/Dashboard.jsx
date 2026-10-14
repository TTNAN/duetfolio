import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw, History, AlertTriangle, X, Plus, ChevronDown, ChevronRight } from 'lucide-react';
import { api, isAbort } from '../api.js';
import { useLang } from '../i18n.js';
import { usePrefs } from '../prefs.js';
import { money, signed, pct, qty, tone, mask, compact, isNum } from '../format.js';
import { AnimatedNumber, Drawer, Seg, Skeleton, SymBadge, toast } from '../components/ui.jsx';
import LineChart from '../components/LineChart.jsx';
import Donut from '../components/Donut.jsx';

const BASES = ['HKD', 'USD', 'CNY'];
const RANGES = ['1M', '3M', '6M', 'YTD', '1Y', 'ALL'];

function rangeStart(range, lastDate) {
  if (range === 'ALL' || !lastDate) return null;
  const d = new Date(lastDate + 'T00:00:00');
  if (range === 'YTD') return `${d.getFullYear()}-01-01`;
  const months = { '1M': 1, '3M': 3, '6M': 6, '1Y': 12 }[range];
  d.setMonth(d.getMonth() - months);
  return d.toISOString().slice(0, 10);
}

/* ---------------- hero ---------------- */
function Hero({ data, privacy }) {
  const { t } = useLang();
  const b = data.base_currency;
  const m = (s) => mask(s, privacy);
  const asOf = data.quotes_as_of ? new Date(data.quotes_as_of.endsWith('Z') ? data.quotes_as_of : data.quotes_as_of + 'Z') : null;
  const asOfStr = asOf ? asOf.toLocaleString([], { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : null;
  const src = data.quotes_source ? (t.srcName[data.quotes_source] || data.quotes_source) : null;
  const pnlPct = isNum(data.total_pnl) && data.total_invested > 0 ? data.total_pnl / data.total_invested : null;
  const hasCash = isNum(data.cash_balance);
  const total = isNum(data.total_value) ? data.total_value + (hasCash ? data.cash_balance : 0) : null;

  return (
    <section className="card hero">
      <div className="hero-main">
        <div className="mono-label">{t.totalAssets} · {b}</div>
        <div className="hero-value num">
          {total == null ? '—'
            : privacy ? '••••••'
              : <AnimatedNumber value={total} format={(v) => money(v)} />}
          <span className="ccy">{b}</span>
        </div>
        <div className="hero-chips">
          <span className={`chip num ${tone(data.day_pnl)}`}>
            <span className="text-2">{t.today}</span>
            {m(signed(data.day_pnl))} <span>{pct(data.day_pnl_pct)}</span>
          </span>
          <span className={`chip num ${tone(data.total_pnl)}`}>
            <span className="text-2">{t.totalPnlShort}</span>
            {m(signed(data.total_pnl))} {pnlPct != null && <span>{pct(pnlPct)}</span>}
          </span>
        </div>
        <div className="hero-meta num">
          {hasCash && <span>{t.posValue} {m(money(data.total_value))} · {t.cashBal} {m(money(data.cash_balance))}</span>}
          {asOfStr && <span>{t.asOf(asOfStr)}{src ? ` · ${src}` : ''}</span>}
          {data.fx_usd_to_base && <span>{t.fxLine(b, data.fx_usd_to_base.toFixed(4))}</span>}
        </div>
      </div>
      <div className="hero-kpis">
        <div className="kpi">
          <div className="mono-label">{t.invested}</div>
          <div className="kpi-value num">{m(money(data.total_invested))}</div>
          <div className="kpi-sub">{t.investedSub}</div>
        </div>
        <div className="kpi">
          <div className="mono-label">{t.totalPnl}</div>
          <div className={`kpi-value num ${tone(data.total_pnl)}`}>{m(signed(data.total_pnl))}</div>
          <div className="kpi-sub num">{data.realized_pnl != null && data.unrealized_pnl != null
            ? m(t.pnlSub(compact(data.realized_pnl), compact(data.unrealized_pnl))) : '—'}</div>
        </div>
        <div className="kpi">
          <div className="mono-label">{t.xirr}</div>
          <div className={`kpi-value num ${tone(data.xirr)}`}>{pct(data.xirr)}</div>
          <div className="kpi-sub">{t.xirrSub}</div>
        </div>
        <div className="kpi">
          <div className="mono-label">{t.div12m}</div>
          <div className="kpi-value num">{m(money(data.dividends_12m))}</div>
          <div className="kpi-sub">{t.divSub}</div>
        </div>
      </div>
    </section>
  );
}

/* ---------------- performance ---------------- */
function Performance({ base, method, reloadKey, privacy, onBackfilled }) {
  const { t } = useLang();
  const [pts, setPts] = useState(null);
  const [mode, setMode] = useState(() => localStorage.getItem('df-perf-mode') || 'value');
  const [range, setRange] = useState(() => localStorage.getItem('df-perf-range') || 'ALL');
  const [benchList, setBenchList] = useState([]);
  const [bench, setBench] = useState(() => localStorage.getItem('df-bench') || 'QQQ');
  const [benchPts, setBenchPts] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { localStorage.setItem('df-perf-mode', mode); }, [mode]);
  useEffect(() => { localStorage.setItem('df-perf-range', range); }, [range]);
  useEffect(() => { localStorage.setItem('df-bench', bench); }, [bench]);
  useEffect(() => {
    const ac = new AbortController();
    api.benchmarks(ac.signal).then(setBenchList).catch(() => {});
    return () => ac.abort();
  }, []);
  useEffect(() => {
    const ac = new AbortController();
    setPts(null);
    api.history(base, method, ac.signal).then(setPts).catch((e) => { if (!isAbort(e)) setPts([]); });
    return () => ac.abort();
  }, [base, method, reloadKey]);

  const valid = useMemo(() => (pts || []).filter((p) => p.value != null), [pts]);
  const last = valid.length ? valid[valid.length - 1].date : null;
  const start = rangeStart(range, last);
  const inRange = useMemo(() => valid.filter((p) => !start || p.date >= start), [valid, start]);

  useEffect(() => {
    if (mode !== 'return' || !inRange.length) return undefined;
    const ac = new AbortController();
    setBenchPts(null);
    api.benchmark(bench, inRange[0].date, ac.signal).then((r) => setBenchPts(r.points))
      .catch((e) => { if (!isAbort(e)) setBenchPts([]); });
    return () => ac.abort();
  }, [mode, bench, inRange.length && inRange[0].date]); // eslint-disable-line react-hooks/exhaustive-deps

  const doBackfill = async () => {
    setBusy(true);
    try {
      const r = await api.backfill();
      toast(t.backfillDone(r.inserted, r.failed.join(', ')), r.failed.length ? 'error' : 'ok');
      onBackfilled();
    } catch (e) { toast(e.message, 'error'); } finally { setBusy(false); }
  };

  const head = (
    <div className="card-head">
      <div>
        <h3 className="card-title">{t.perf}</h3>
        <div className="card-sub">{mode === 'value' ? t.fxNote : t.twrNote}</div>
      </div>
      <div className="page-actions">
        <Seg size="sm" value={mode} onChange={setMode}
          options={[{ value: 'value', label: t.modeValue }, { value: 'return', label: t.modeReturn }]} />
        <Seg size="sm" value={range} onChange={setRange} options={RANGES.map((r) => ({ value: r, label: t.ranges[r] }))} />
      </div>
    </div>
  );

  if (!pts) return <section className="card">{head}<Skeleton h={260} /></section>;
  if (inRange.length < 2) {
    return (
      <section className="card">
        {head}
        <div className="chart-empty">
          <div>
            <History size={28} strokeWidth={1.4} />
            <div style={{ color: 'var(--text)', fontWeight: 500 }}>{t.histEmpty}</div>
            <div className="small" style={{ maxWidth: 360 }}>{t.histEmptyD}</div>
            <button className="btn" onClick={doBackfill} disabled={busy}>
              <History size={15} className={busy ? 'spin' : ''} />{busy ? t.backfilling : t.backfill}
            </button>
          </div>
        </div>
      </section>
    );
  }

  const first = inRange[0], lastP = inRange[inRange.length - 1];
  let series, yFormat, summary;
  if (mode === 'value') {
    series = [
      { key: 'v', label: t.lValue, color: 'var(--accent)', area: true, width: 2, points: inRange.map((p) => ({ date: p.date, value: p.value })) },
      { key: 'c', label: t.lCost, color: 'var(--muted)', dash: true, width: 1.3, points: inRange.filter((p) => p.cost != null).map((p) => ({ date: p.date, value: p.cost })) },
    ];
    yFormat = privacy ? () => '•••' : compact;
    // value vs cost at the end of the range: what the line gap means
    const gapV = lastP.cost != null ? lastP.value - lastP.cost : null;
    summary = gapV == null ? null : (
      <span className={`num ${tone(gapV)}`}>{t.vsCost} {mask(signed(gapV), privacy)} · {pct(lastP.cost ? gapV / lastP.cost : null)}</span>
    );
  } else {
    const b0 = 1 + (first.twr || 0);
    const mine = inRange.map((p) => ({ date: p.date, value: ((1 + (p.twr || 0)) / b0 - 1) }));
    const bp = (benchPts || []).filter((p) => p.date >= first.date);
    const bench0 = bp.length ? bp[0].close : null;
    const bSeries = bench0 ? bp.map((p) => ({ date: p.date, value: p.close / bench0 - 1 })) : [];
    const bName = benchList.find((x) => x.symbol === bench)?.name || bench;
    series = [
      { key: 'r', label: t.lPortfolio, color: 'var(--accent)', area: true, width: 2, points: mine },
      { key: 'b', label: bName, color: 'var(--chart-2)', width: 1.5, opacity: 0.9, points: bSeries },
    ];
    yFormat = (v) => pct(v, 0);
    const myR = mine[mine.length - 1].value;
    const bR = bSeries.length ? bSeries[bSeries.length - 1].value : null;
    summary = (
      <span className="num">
        <span className={tone(myR)}>{pct(myR)}</span>
        {bR != null && <span className="muted"> vs {bench} <span className={tone(bR)}>{pct(bR)}</span></span>}
        {benchPts && !bSeries.length && <span className="muted"> · {t.benchNone}</span>}
      </span>
    );
  }

  return (
    <section className="card">
      {head}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, gap: 12, flexWrap: 'wrap' }}>
        <div className="legend">
          {series.map((s) => <span key={s.key}><i className={s.dash ? 'dash' : ''} style={{ background: s.color, color: s.color }} />{s.label}</span>)}
          {summary && <span className="muted">· {summary}</span>}
        </div>
        {mode === 'return' && benchList.length > 0 && (
          <select className="select sm" style={{ width: 'auto' }} value={bench} onChange={(e) => setBench(e.target.value)}>
            {benchList.map((b) => <option key={b.symbol} value={b.symbol}>{b.name}</option>)}
          </select>
        )}
      </div>
      <LineChart series={series} height={330} yFormat={yFormat} zeroLine={mode === 'return'} label={t.perf}
        tipValue={(v) => (mode === 'return' ? pct(v) : mask(money(v), privacy))} />
    </section>
  );
}

/* ---------------- allocation ---------------- */
function Allocation({ data, privacy }) {
  const { t } = useLang();
  const [mode, setMode] = useState('symbol');
  const [types, setTypes] = useState({});
  useEffect(() => {
    api.instruments().then((xs) => setTypes(Object.fromEntries(xs.map((i) => [i.id, i.asset_type])))).catch(() => {});
  }, [data]);
  const items = useMemo(() => {
    const vals = data.holdings.filter((h) => h.market_value_base > 0);
    const group = (keyFn) => {
      const g = {};
      vals.forEach((h) => { const k = keyFn(h); g[k] = (g[k] || 0) + h.market_value_base; });
      return Object.entries(g).map(([label, value]) => ({ label, value }));
    };
    let out;
    if (mode === 'market') out = group((h) => t.markets[h.market] || h.market);
    else if (mode === 'currency') out = group((h) => h.currency);
    else if (mode === 'type') out = group((h) => t.assetTypes[types[h.instrument_id]] || '—');
    else out = vals.map((h) => ({ label: h.symbol, sub: compact(h.market_value_base), value: h.market_value_base }));
    return out.sort((a, b) => b.value - a.value);
  }, [data, mode, types, t]);
  return (
    <section className="card">
      <div className="card-head">
        <h3 className="card-title">{t.allocation}</h3>
        <Seg size="sm" value={mode} onChange={setMode}
          options={['symbol', 'market', 'currency', 'type'].map((m) => ({ value: m, label: t.allocModes[m] }))} />
      </div>
      <Donut items={items} privacy={privacy}
        center={mode === 'symbol' ? String(items.length) : String(items.length)}
        centerLabel={mode === 'symbol' ? t.positions : t.allocModes[mode]} />
    </section>
  );
}

/* ---------------- holdings ---------------- */
const SORTS = {
  symbol: (h) => h.symbol, value: (h) => h.market_value_base ?? -Infinity, day: (h) => h.day_change_pct ?? -Infinity,
  pnl: (h) => h.unrealized_pnl_pct ?? -Infinity, weight: (h) => h.weight_pct ?? -Infinity, xirr: (h) => h.xirr ?? -Infinity,
};

function Holdings({ data, privacy, onOpen }) {
  const { t } = useLang();
  const [sort, setSort] = useState({ key: 'value', dir: -1 });
  const [showClosed, setShowClosed] = useState(false);
  const open = data.holdings.filter((h) => h.quantity > 0);
  const closed = data.holdings.filter((h) => h.quantity <= 0);
  const rows = [...open].sort((a, b) => {
    const x = SORTS[sort.key](a), y = SORTS[sort.key](b);
    return (x > y ? 1 : x < y ? -1 : 0) * sort.dir;
  });
  const m = (s) => mask(s, privacy);
  const Th = ({ k, children, l }) => (
    <th className={`${l ? 'l' : ''} ${k ? 'sortable' : ''}`}
      onClick={k ? () => setSort((s) => ({ key: k, dir: s.key === k ? -s.dir : -1 })) : undefined}>
      {children}{k && <span className="sort">{sort.key === k ? (sort.dir < 0 ? '↓' : '↑') : ''}</span>}
    </th>
  );
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h3 className="card-title">{t.holdings}</h3>
          <div className="card-sub">{t.holdingsSub(open.length)}</div>
        </div>
      </div>
      <div className="table-wrap">
        <table className="tbl hover">
          <thead>
            <tr>
              <Th k="symbol" l>{t.th.symbol}</Th>
              <Th>{t.th.price}</Th>
              <Th k="day">{t.th.day}</Th>
              <th className="hide-sm">{t.th.qty}</th>
              <th className="hide-sm">{t.th.avg}</th>
              <Th k="value">{t.th.value} ({data.base_currency})</Th>
              <Th k="weight">{t.th.weight}</Th>
              <Th k="pnl">{t.th.pnl}</Th>
              <Th k="xirr">{t.th.xirr}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((h) => (
              <tr key={h.instrument_id} onClick={() => onOpen(h)}>
                <td className="l">
                  <div className="sym">
                    <SymBadge symbol={h.symbol} market={h.market} />
                    <div style={{ minWidth: 0 }}>
                      <div className="sym-name">{h.symbol}</div>
                      <div className="sym-desc">{h.name}</div>
                    </div>
                  </div>
                </td>
                <td>{h.latest_price != null ? money(h.latest_price, h.latest_price < 10 ? 3 : 2) : <span className="muted">{t.noPrice}</span>}
                  <span className="sub">{h.currency}</span></td>
                <td className={tone(h.day_change_pct)}>{pct(h.day_change_pct)}
                  <span className="sub">{m(signed(h.day_change_base))}</span></td>
                <td className="hide-sm">{m(qty(h.quantity))}</td>
                <td className="hide-sm">{money(h.avg_cost, h.avg_cost < 10 ? 3 : 2)}</td>
                <td>{m(money(h.market_value_base))}</td>
                <td><span className="wbar">{h.weight_pct != null ? `${h.weight_pct}%` : '—'}<i><b style={{ width: `${h.weight_pct || 0}%` }} /></i></span></td>
                <td className={tone(h.unrealized_pnl_base)}>{pct(h.unrealized_pnl_pct)}
                  <span className="sub">{m(signed(h.unrealized_pnl_base))}</span></td>
                <td className={tone(h.xirr)}>{pct(h.xirr, 1)}</td>
              </tr>
            ))}
            {showClosed && closed.map((h) => (
              <tr key={h.instrument_id} className="closed" onClick={() => onOpen(h)}>
                <td className="l"><div className="sym"><SymBadge symbol={h.symbol} market={h.market} /><div><div className="sym-name">{h.symbol}</div><div className="sym-desc">{h.name}</div></div></div></td>
                <td>{h.latest_price != null ? money(h.latest_price) : '—'}</td>
                <td>—</td><td className="hide-sm">0</td><td className="hide-sm">—</td><td>—</td><td>—</td>
                <td className={tone(h.realized_pnl)}>{t.realized}<span className="sub">{m(signed(h.realized_pnl))} {h.currency}</span></td>
                <td className={tone(h.xirr)}>{pct(h.xirr, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {closed.length > 0 && (
        <button className="btn ghost sm" style={{ marginTop: 10 }} onClick={() => setShowClosed((s) => !s)}>
          {showClosed ? <ChevronDown size={14} /> : <ChevronRight size={14} />}{t.closedPos(closed.length)}
        </button>
      )}
    </section>
  );
}

/* ---------------- holding drawer ---------------- */
function HoldingDrawer({ h, onClose, privacy, openAdd }) {
  const { t } = useLang();
  const [txns, setTxns] = useState(null);
  const [prices, setPrices] = useState(null);
  useEffect(() => {
    const ac = new AbortController();
    setTxns(null); setPrices(null);
    api.transactions(h.instrument_id, ac.signal).then(setTxns).catch((e) => { if (!isAbort(e)) setTxns([]); });
    api.instrumentPrices(h.instrument_id, ac.signal).then(setPrices).catch((e) => { if (!isAbort(e)) setPrices([]); });
    return () => ac.abort();
  }, [h.instrument_id]);
  const m = (s) => mask(s, privacy);
  const markers = (txns || []).map((x) => ({
    date: x.date, kind: x.type,
    label: x.type === 'split' ? `${t.txTypes.split} ${t.splitShort(qty(x.quantity))}` : `${t.txTypes[x.type]} ${qty(x.quantity)} @ ${x.price}`,
  }));
  const ccy = h.currency;
  return (
    <Drawer onClose={onClose} label={h.symbol}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div className="sym">
          <SymBadge symbol={h.symbol} market={h.market} />
          <div>
            <div className="serif" style={{ fontSize: 28, lineHeight: 1 }}>{h.symbol}</div>
            <div className="muted small" style={{ marginTop: 4 }}>{h.name} · {h.market} · {ccy}</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn sm" onClick={() => openAdd(h.instrument_id)}><Plus size={14} />{t.drawer.addTxn}</button>
          <button className="btn sm ghost icon" onClick={onClose} aria-label={t.drawer.close}><X size={16} /></button>
        </div>
      </div>
      <div style={{ marginTop: 18 }}>
        <span className="serif num" style={{ fontSize: 40 }}>{h.latest_price != null ? money(h.latest_price, h.latest_price < 10 ? 3 : 2) : '—'}</span>
        <span className="muted" style={{ marginLeft: 8 }}>{ccy}</span>
        <span className={`chip num ${tone(h.day_change_pct)}`} style={{ marginLeft: 12, verticalAlign: 8 }}>{pct(h.day_change_pct)}</span>
      </div>
      <div className="drawer-kpis">
        <div><div className="mono-label">{t.drawer.qty}</div><div className="v num">{m(qty(h.quantity))}</div></div>
        <div><div className="mono-label">{t.drawer.avg}</div><div className="v num">{money(h.avg_cost, 3)}</div></div>
        <div><div className="mono-label">{t.drawer.value}</div><div className="v num">{m(compact(h.market_value))}</div></div>
        <div><div className="mono-label">{t.drawer.pnl}</div><div className={`v num ${tone(h.unrealized_pnl)}`}>{pct(h.unrealized_pnl_pct)}</div></div>
        <div><div className="mono-label">{t.drawer.realized}</div><div className={`v num ${tone(h.realized_pnl)}`}>{m(signed(h.realized_pnl))}</div></div>
        <div><div className="mono-label">{t.drawer.xirr}</div><div className={`v num ${tone(h.xirr)}`}>{pct(h.xirr, 1)}</div></div>
      </div>
      <div className="mono-label" style={{ marginBottom: 8 }}>{t.drawer.price}</div>
      {!prices ? <Skeleton h={180} /> : prices.length < 2
        ? <div className="chart-empty" style={{ height: 120 }}>{t.drawer.noPrices}</div>
        : <LineChart height={190} markers={markers}
            series={[{ key: 'p', label: h.symbol, color: 'var(--accent)', area: true, width: 1.8, points: prices.map((p) => ({ date: p.date, value: p.close })) }]}
            yFormat={(v) => money(v, v < 10 ? 2 : 0)} tipValue={(v) => money(v, 3)} />}
      <div className="mono-label" style={{ margin: '22px 0 6px' }}>{t.drawer.txns}</div>
      {!txns ? <Skeleton h={80} /> : (
        <table className="tbl">
          <tbody>
            {txns.map((x) => (
              <tr key={x.id}>
                <td className="l num">{x.date}</td>
                <td className="l"><span className={`tag ${x.type}`}>{t.txTypes[x.type]}</span></td>
                <td className="num">{x.type === 'split' ? t.splitShort(qty(x.quantity)) : m(qty(x.quantity))}</td>
                <td className="num">{x.type === 'split' ? '' : `@ ${x.price}`}</td>
              </tr>
            ))}
            {txns.length === 0 && <tr><td className="l muted">{t.noTxns}</td></tr>}
          </tbody>
        </table>
      )}
    </Drawer>
  );
}

/* ---------------- page ---------------- */
export default function Dashboard({ reloadKey, reload, go, openAdd, provider }) {
  const { t } = useLang();
  const [prefs, setPref] = usePrefs();
  const base = prefs.base;
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [panel, setPanel] = useState(null);

  const method = prefs.costMethod;
  useEffect(() => {
    // abort the in-flight request when base / method change quickly, so a
    // slow old response can't overwrite the newer one
    const ac = new AbortController();
    setErr('');
    api.summary(base, method, ac.signal).then(setData)
      .catch((e) => { if (!isAbort(e)) setErr(t.apiDown); });
    return () => ac.abort();
  }, [base, method, reloadKey, t]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const r = await api.refreshPrices();
      if (r.failed?.length) toast(t.priceFailed(r.failed.join(', ')), 'error');
      else if (!r.updated.length && r.fresh?.length) toast(t.quotesFresh);
      else toast(t.refreshed(r.updated.length));
      reload();
    } catch (e) { toast(e.message, 'error'); } finally { setRefreshing(false); }
  }, [reload, t]);

  useEffect(() => {
    const h = (e) => {
      const tag = (e.target.tagName || '').toLowerCase();
      if (['input', 'textarea', 'select'].includes(tag) || e.metaKey || e.ctrlKey) return;
      if ((e.key === 'r' || e.key === 'R') && !refreshing && !document.querySelector('.modal, .drawer')) onRefresh();
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onRefresh, refreshing]);

  const head = (
    <div className="page-head">
      <div>
        <h1 className="page-title">{t.dashTitle}</h1>
        <div className="page-sub">{t.dashSub(provider ? t.providerNames[provider] : '')}</div>
      </div>
      <div className="page-actions">
        <Seg value={base} onChange={(v) => setPref('base', v)} options={BASES.map((c) => ({ value: c, label: c }))} />
        <button className="btn" onClick={onRefresh} disabled={refreshing}>
          <RefreshCw size={15} className={refreshing ? 'spin' : ''} />{refreshing ? t.refreshing : t.refresh}
        </button>
      </div>
    </div>
  );

  if (err && !data) {
    return <>{head}<div className="banner error"><AlertTriangle size={16} />{err}<button className="btn sm" style={{ marginLeft: 'auto' }} onClick={reload}>{t.retry}</button></div></>;
  }
  if (!data) {
    return (
      <>{head}
        <div className="card hero"><div className="hero-main"><Skeleton h={12} w={120} /><Skeleton h={58} w={360} style={{ margin: '16px 0' }} /><Skeleton h={26} w={260} /></div>
          <div className="hero-kpis">{[0, 1, 2, 3].map((i) => <div className="kpi" key={i}><Skeleton h={10} w={80} /><Skeleton h={22} w={140} style={{ marginTop: 10 }} /></div>)}</div></div>
        <div className="card"><Skeleton h={280} /></div>
      </>
    );
  }

  if (data.holdings.length === 0) {
    const steps = [
      { title: t.step1, d: t.step1d, act: () => go('instruments') },
      { title: t.step2, d: t.step2d, act: () => openAdd() },
      { title: t.step3, d: t.step3d, act: onRefresh },
    ];
    return (
      <>{head}
        <section className="card empty">
          <h3>{t.emptyTitle}</h3>
          <div>{t.emptySub}</div>
          <div className="onboard">
            {steps.map((s, i) => (
              <button key={i} onClick={s.act}><span className="n">0{i + 1}</span><span className="t">{s.title}</span><span className="d">{s.d}</span></button>
            ))}
          </div>
        </section>
      </>
    );
  }

  const incomplete = data.price_stale?.length > 0 || data.fx_stale?.length > 0;
  return (
    <>
      {head}
      {incomplete && (
        <div className="banner warn">
          <AlertTriangle size={16} />
          <span>{t.incomplete}：{[
            data.price_stale?.length ? t.noPriceFor(data.price_stale.join(', ')) : null,
            data.fx_stale?.length ? t.fxMissing(data.fx_stale.join(', ')) : null,
          ].filter(Boolean).join('；')}</span>
        </div>
      )}
      <div className="stack">
        <Hero data={data} privacy={prefs.privacy} />
        <div className="grid grid-main">
          <Performance base={base} method={method} reloadKey={reloadKey} privacy={prefs.privacy} onBackfilled={reload} />
          <Allocation data={data} privacy={prefs.privacy} />
        </div>
        <Holdings data={data} privacy={prefs.privacy} onOpen={setPanel} />
      </div>
      {panel && <HoldingDrawer h={panel} privacy={prefs.privacy} onClose={() => setPanel(null)}
        openAdd={(id) => { setPanel(null); openAdd(id); }} />}
    </>
  );
}
