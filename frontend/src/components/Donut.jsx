// Hand-rolled SVG donut with hover highlight: zero chart dependencies.
import { useState } from 'react';
import { useLang } from '../i18n.js';

export const PALETTE = Array.from({ length: 8 }, (_, i) => `var(--chart-${i + 1})`);

export default function Donut({ items, center, centerLabel, privacy }) {
  const { t } = useLang();
  const [hover, setHover] = useState(null);
  const total = items.reduce((s, i) => s + i.value, 0);
  if (!total) return <div className="chart-empty" style={{ height: 180 }}>{t.noValued}</div>;

  const size = 190, R = 78, SW = 14, C = 2 * Math.PI * R;
  const gap = items.length > 1 ? 2.5 : 0;
  let acc = 0;
  const segs = items.map((it, idx) => {
    const frac = it.value / total;
    const len = Math.max(0, frac * C - gap);
    const el = (
      <circle key={it.label} cx={size / 2} cy={size / 2} r={R} fill="none"
        stroke={PALETTE[idx % PALETTE.length]} strokeWidth={hover === idx ? SW + 4 : SW}
        strokeDasharray={`${len} ${C}`} strokeDashoffset={-acc * C}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-width .15s', opacity: hover == null || hover === idx ? 1 : 0.35, cursor: 'default' }}
        onMouseEnter={() => setHover(idx)} onMouseLeave={() => setHover(null)} />
    );
    acc += frac;
    return el;
  });
  const h = hover != null ? items[hover] : null;

  return (
    <div className="alloc">
      <div className="alloc-donut">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
          aria-label={items.map((it) => `${it.label} ${((it.value / total) * 100).toFixed(1)}%`).join(', ')}>
          <circle cx={size / 2} cy={size / 2} r={R} fill="none" stroke="var(--surface-3)" strokeWidth={SW} opacity=".5" />
          {segs}
          <text x={size / 2} y={size / 2 + 4} textAnchor="middle" className="big">
            {h ? `${((h.value / total) * 100).toFixed(1)}%` : center}
          </text>
          <text x={size / 2} y={size / 2 + 24} textAnchor="middle" className="lbl">
            {h ? h.label : centerLabel}
          </text>
        </svg>
      </div>
      <div className="alloc-list">
        {items.map((it, idx) => {
          const p = (it.value / total) * 100;
          return (
            <div key={it.label} className={`alloc-item ${hover != null && hover !== idx ? 'dim' : ''}`}
              tabIndex={0} onFocus={() => setHover(idx)} onBlur={() => setHover(null)}
              onMouseEnter={() => setHover(idx)} onMouseLeave={() => setHover(null)}>
              <span className="dot" style={{ background: PALETTE[idx % PALETTE.length] }} />
              <span>{it.label}{it.sub && !privacy ? <span className="muted small"> · {it.sub}</span> : null}</span>
              <span className="num text-2">{p.toFixed(1)}%</span>
              <span className="bar"><b style={{ width: `${p}%`, background: PALETTE[idx % PALETTE.length] }} /></span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
