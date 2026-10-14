import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, AlertCircle, X } from 'lucide-react';

/* ---------- brand mark: two interlocking rings, one per market ---------- */
export function Logo({ size = 26 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="12" cy="16" r="8.5" stroke="var(--accent)" strokeWidth="2" />
      <circle cx="20" cy="16" r="8.5" stroke="var(--text)" strokeOpacity=".55" strokeWidth="2" />
    </svg>
  );
}

/* ---------- segmented control ---------- */
export function Seg({ value, options, onChange, size }) {
  return (
    <div className={`seg ${size || ''}`} role="tablist">
      {options.map((o) => (
        <button key={o.value} type="button" role="tab" aria-selected={value === o.value}
          className={value === o.value ? 'on' : ''} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- ticker monogram ---------- */
export function SymBadge({ symbol, market }) {
  const base = (symbol || '').replace(/\.HK$/i, '');
  const txt = /^\d+$/.test(base) ? base.padStart(4, '0').slice(-4) : base.slice(0, 4);
  return <span className={`sym-badge ${String(market).toLowerCase()}`}>{txt}</span>;
}

export function Skeleton({ h = 16, w = '100%', style }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} />;
}

/* ---------- number that eases to its new value ---------- */
export function AnimatedNumber({ value, format }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (typeof value !== 'number' || typeof from.current !== 'number') {
      from.current = value; setShown(value); return undefined;
    }
    const start = performance.now(), a = from.current, b = value, dur = 700;
    let raf;
    const step = (now) => {
      const k = Math.min(1, (now - start) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      setShown(a + (b - a) * e);
      if (k < 1) raf = requestAnimationFrame(step); else from.current = b;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <>{format(shown)}</>;
}

/* ---------- modal & drawer ---------- */
function useEsc(onClose) {
  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);
}

export function Modal({ title, onClose, children, footer }) {
  useEsc(onClose);
  return createPortal(
    <>
      <div className="overlay" onClick={onClose} />
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2 className="modal-title">{title}</h2>
          <button className="btn ghost icon sm" onClick={onClose} aria-label="close"><X size={16} /></button>
        </div>
        {children}
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </>,
    document.body,
  );
}

export function Drawer({ onClose, children }) {
  useEsc(onClose);
  return createPortal(
    <>
      <div className="overlay" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true">{children}</aside>
    </>,
    document.body,
  );
}

/* ---------- toasts ---------- */
const toastListeners = new Set();
let toastId = 0;
export function toast(text, kind = 'ok') {
  const item = { id: ++toastId, text, kind };
  toastListeners.forEach((fn) => fn(item));
}
export function Toaster() {
  const [items, setItems] = useState([]);
  useEffect(() => {
    const add = (it) => {
      setItems((xs) => [...xs.slice(-2), it]);
      setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== it.id)), it.kind === 'error' ? 5200 : 2800);
    };
    toastListeners.add(add);
    return () => toastListeners.delete(add);
  }, []);
  return createPortal(
    <div className="toasts" aria-live="polite">
      {items.map((it) => (
        <div key={it.id} className={`toast ${it.kind}`}>
          {it.kind === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          <span>{it.text}</span>
        </div>
      ))}
    </div>,
    document.body,
  );
}

/* ---------- element width (for responsive SVG charts) ---------- */
export function useWidth() {
  const ref = useRef(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}
