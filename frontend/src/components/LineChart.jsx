// Responsive multi-series SVG line chart with crosshair tooltip.
// Zero dependencies; x axis is trading-day index (no weekend gaps).
import { useMemo, useState } from 'react';
import { useWidth } from './ui.jsx';

function niceTicks(min, max, count = 4) {
  if (min === max) { const d = Math.abs(min) * 0.05 || 1; min -= d; max += d; }
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(+v.toFixed(10));
  return ticks;
}

function fmtDate(iso, long) {
  const [y, m, d] = iso.split('-');
  return long ? `${y}-${m}-${d}` : `${+m}/${+d}`;
}

export default function LineChart({
  series, height = 260, yFormat = (v) => v, tipValue = yFormat, markers = [], zeroLine = false,
}) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);

  const model = useMemo(() => {
    const dates = [...new Set(series.flatMap((s) => s.points.map((p) => p.date)))].sort();
    const maps = series.map((s) => new Map(s.points.map((p) => [p.date, p.value])));
    const vals = series.flatMap((s) => s.points.map((p) => p.value)).filter((v) => v != null);
    if (zeroLine) vals.push(0);
    if (!vals.length) return null;
    const ticks = niceTicks(Math.min(...vals), Math.max(...vals));
    return { dates, maps, ticks, lo: ticks[0], hi: ticks[ticks.length - 1] };
  }, [series, zeroLine]);

  const padL = 4, padR = 58, padT = 12, padB = 26;
  const W = Math.max(width, 200), H = height;
  const iw = W - padL - padR, ih = H - padT - padB;

  if (!model) return <div ref={ref} className="chart" style={{ height }} />;
  const { dates, maps, ticks, lo, hi } = model;
  const n = dates.length;
  const xs = (i) => padL + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw);
  const ys = (v) => padT + (1 - (v - lo) / (hi - lo || 1)) * ih;

  const paths = series.map((s, si) => {
    let d = '', area = '', first = null, last = null;
    dates.forEach((dt, i) => {
      const v = maps[si].get(dt);
      if (v == null) return;
      const x = xs(i).toFixed(1), y = ys(v).toFixed(1);
      d += (d ? 'L' : 'M') + x + ',' + y;
      if (first == null) first = x;
      last = x;
    });
    if (s.area && d) area = `${d}L${last},${padT + ih}L${first},${padT + ih}Z`;
    return { d, area };
  });

  // x labels: ~5 evenly spaced
  const xl = n <= 1 ? [0] : Array.from({ length: Math.min(5, n) }, (_, k) => Math.round((k / (Math.min(5, n) - 1)) * (n - 1)));

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const cx = e.touches ? e.touches[0]?.clientX : e.clientX;
    if (cx == null) return;
    const px = cx - r.left - padL;
    const i = n <= 1 ? 0 : Math.round((px / iw) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };

  const markerByDate = new Map();
  markers.forEach((m) => { if (!markerByDate.has(m.date)) markerByDate.set(m.date, m); });

  const hx = hover != null ? xs(hover) : null;
  const tipLeft = hx != null ? Math.min(Math.max(hx, 80), W - 150) : 0;

  return (
    <div ref={ref} className="chart" style={{ height }}>
      {width > 0 && (
        <svg width={W} height={H} onMouseMove={onMove} onMouseLeave={() => setHover(null)}
          onTouchStart={onMove} onTouchMove={onMove} onTouchEnd={() => setHover(null)}>
          <defs>
            {series.map((s, si) => s.area && (
              <linearGradient key={si} id={`g-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity=".22" />
                <stop offset="100%" stopColor={s.color} stopOpacity="0" />
              </linearGradient>
            ))}
          </defs>
          {ticks.map((tv) => (
            <g key={tv}>
              <line className="grid-line" x1={padL} x2={padL + iw} y1={ys(tv)} y2={ys(tv)}
                strokeDasharray={zeroLine && tv === 0 ? '' : '2 4'} opacity={zeroLine && tv === 0 ? 1 : 0.9} />
              <text className="axis-label" x={W - 4} y={ys(tv) + 3.5} textAnchor="end">{yFormat(tv)}</text>
            </g>
          ))}
          {xl.map((i) => (
            <text key={i} className="axis-label" x={xs(i)} y={H - 6}
              textAnchor={i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}>{fmtDate(dates[i])}</text>
          ))}
          {paths.map((p, si) => p.area && <path key={`a${si}`} d={p.area} fill={`url(#g-${series[si].key})`} />)}
          {paths.map((p, si) => (
            <path key={si} d={p.d} fill="none" stroke={series[si].color}
              strokeWidth={series[si].width || 1.8} strokeDasharray={series[si].dash ? '4 4' : ''}
              strokeLinejoin="round" strokeLinecap="round" opacity={series[si].opacity || 1} />
          ))}
          {[...markerByDate.values()].map((m) => {
            const i = dates.indexOf(m.date);
            const v = i >= 0 ? maps[0].get(m.date) : null;
            if (v == null) return null;
            return <circle key={m.date + m.kind} cx={xs(i)} cy={ys(v)} r="4" fill="var(--surface)"
              stroke={m.kind === 'sell' ? 'var(--down)' : m.kind === 'buy' ? 'var(--up)' : 'var(--accent)'} strokeWidth="2" />;
          })}
          {hover != null && (
            <g>
              <line x1={hx} x2={hx} y1={padT} y2={padT + ih} stroke="var(--hairline-2)" />
              {series.map((s, si) => {
                const v = maps[si].get(dates[hover]);
                return v == null ? null : (
                  <circle key={si} cx={hx} cy={ys(v)} r="4" fill={s.color} stroke="var(--surface)" strokeWidth="2" />
                );
              })}
            </g>
          )}
          {hover == null && series.map((s, si) => {
            // resting dot on the last point of the main series
            if (si !== 0) return null;
            const lastI = [...dates.keys()].reverse().find((i) => maps[0].get(dates[i]) != null);
            if (lastI == null) return null;
            return <circle key="last" cx={xs(lastI)} cy={ys(maps[0].get(dates[lastI]))} r="3.5" fill={s.color} />;
          })}
        </svg>
      )}
      {hover != null && (
        <div className="chart-tip" style={{ left: tipLeft, transform: 'translateX(-50%)' }}>
          <div className="tip-date num">{fmtDate(dates[hover], true)}</div>
          {series.map((s, si) => {
            const v = maps[si].get(dates[hover]);
            return (
              <div className="tip-row" key={si}>
                <span className="muted"><i style={{ display: 'inline-block', width: 7, height: 7, borderRadius: 2, background: s.color, marginRight: 6 }} />{s.label}</span>
                <b className="num">{v == null ? '—' : tipValue(v, s)}</b>
              </div>
            );
          })}
          {markerByDate.get(dates[hover]) && <div className="muted small" style={{ marginTop: 4 }}>{markerByDate.get(dates[hover]).label}</div>}
        </div>
      )}
    </div>
  );
}
