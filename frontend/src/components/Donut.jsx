// Hand-rolled SVG donut: zero chart dependencies.
import { useLang } from '../i18n.js';

const COLORS = ['#4f8cff', '#ff6b6b', '#51cf66', '#fcc419', '#9775fa', '#3bc9db', '#ff922b', '#e599f7'];

export default function Donut({ items }) {
  const { t } = useLang();
  const total = items.reduce((s, i) => s + i.value, 0);
  if (!total) return <div className="donut-empty">{t.noValued}</div>;

  const R = 70;
  const C = 2 * Math.PI * R;
  let acc = 0;
  const segs = items.map((it, idx) => {
    const frac = it.value / total;
    const seg = (
      <circle
        key={it.label}
        cx="90" cy="90" r={R} fill="none"
        stroke={COLORS[idx % COLORS.length]}
        strokeWidth="26"
        strokeDasharray={`${(frac * C).toFixed(2)} ${C.toFixed(2)}`}
        strokeDashoffset={(-acc * C).toFixed(2)}
        transform="rotate(-90 90 90)"
      />
    );
    acc += frac;
    return seg;
  });

  return (
    <div className="donut-wrap">
      <svg width="180" height="180" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r={R} fill="none" stroke="#23232b" strokeWidth="26" />
        {segs}
        <text x="90" y="86" textAnchor="middle" className="donut-total">{items.length}</text>
        <text x="90" y="104" textAnchor="middle" className="donut-sub">{t.positions}</text>
      </svg>
      <ul className="donut-legend">
        {items.map((it, idx) => (
          <li key={it.label}>
            <span className="swatch" style={{ background: COLORS[idx % COLORS.length] }} />
            {it.label}
            <span className="pct">{((it.value / total) * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
