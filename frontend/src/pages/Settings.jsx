import { useRef, useState } from 'react';
import { History, Download, Upload, FileSpreadsheet } from 'lucide-react';
import { api } from '../api.js';
import { useLang } from '../i18n.js';
import { usePrefs } from '../prefs.js';
import { Seg, toast } from '../components/ui.jsx';

function Row({ title, desc, children }) {
  return (
    <div className="settings-row">
      <div><div className="t">{title}</div>{desc && <div className="d">{desc}</div>}</div>
      <div style={{ flex: 'none' }}>{children}</div>
    </div>
  );
}

export default function Settings({ reload, health }) {
  const { t, lang, setLang } = useLang();
  const [prefs, setPref] = usePrefs();
  const [busy, setBusy] = useState(false);
  const file = useRef(null);

  const backfill = async () => {
    setBusy(true);
    try {
      const r = await api.backfill();
      toast(t.backfillDone(r.inserted, r.failed.join(', ')), r.failed.length ? 'error' : 'ok');
      reload();
    } catch (e) { toast(e.message, 'error'); } finally { setBusy(false); }
  };
  const restore = async (f) => {
    if (!f || !window.confirm(t.restoreConfirm)) return;
    try {
      const r = await api.restoreBackup(f);
      toast(t.restored(r.instruments, r.transactions));
      reload();
    } catch (e) { toast(e.message, 'error'); }
  };

  return (
    <>
      <div className="page-head">
        <div><h1 className="page-title">{t.setTitle}</h1><div className="page-sub">{t.setSub}</div></div>
      </div>
      <div className="stack" style={{ maxWidth: 860 }}>
        <section className="card">
          <div className="mono-label" style={{ marginBottom: 14 }}>{t.secDisplay}</div>
          <Row title={t.sLang} desc={t.sLangD}>
            <Seg value={lang} onChange={setLang} options={[{ value: 'zh', label: '中文' }, { value: 'en', label: 'English' }]} />
          </Row>
          <Row title={t.sTheme} desc={t.sThemeD}>
            <Seg value={prefs.theme} onChange={(v) => setPref('theme', v)} options={['dark', 'light'].map((k) => ({ value: k, label: t.themes[k] }))} />
          </Row>
          <Row title={t.sUpdown} desc={t.sUpdownD}>
            <Seg value={prefs.updown} onChange={(v) => setPref('updown', v)}
              options={[{ value: 'cn', label: <><span style={{ color: 'var(--loss)' }}>▲</span> {t.updown.cn}</> }, { value: 'intl', label: <><span style={{ color: 'var(--gain)' }}>▲</span> {t.updown.intl}</> }]} />
          </Row>
          <Row title={t.sBase} desc={t.sBaseD}>
            <Seg value={prefs.base} onChange={(v) => setPref('base', v)} options={['HKD', 'USD', 'CNY'].map((c) => ({ value: c, label: c }))} />
          </Row>
          <Row title={t.sPrivacy} desc={t.sPrivacyD}>
            <Seg value={prefs.privacy ? 'on' : 'off'} onChange={(v) => setPref('privacy', v === 'on')}
              options={[{ value: 'off', label: t.off }, { value: 'on', label: t.on }]} />
          </Row>
        </section>

        <section className="card">
          <div className="mono-label" style={{ marginBottom: 14 }}>{t.secData}</div>
          <Row title={t.sBackfill} desc={t.sBackfillD}>
            <button className="btn" onClick={backfill} disabled={busy}><History size={15} className={busy ? 'spin' : ''} />{busy ? t.backfilling : t.run}</button>
          </Row>
          <Row title={t.sCsv} desc={t.sCsvD}>
            <a className="btn" href={api.exportCsvUrl()}><FileSpreadsheet size={15} />{t.download}</a>
          </Row>
          <Row title={t.sBackup} desc={t.sBackupD}>
            <a className="btn" href={api.backupUrl()}><Download size={15} />{t.download}</a>
          </Row>
          <Row title={t.sRestore} desc={t.sRestoreD}>
            <button className="btn danger" onClick={() => file.current?.click()}><Upload size={15} />{t.choose}</button>
            <input ref={file} type="file" accept=".json,application/json" hidden onChange={(e) => { restore(e.target.files?.[0]); e.target.value = ''; }} />
          </Row>
        </section>

        <section className="card">
          <div className="mono-label" style={{ marginBottom: 14 }}>{t.secAbout}</div>
          <Row title={t.sVersion}><span className="num text-2">{health?.version || '—'}</span></Row>
          <Row title={t.sProvider}><span className="text-2">{health?.market_provider ? t.providerNames[health.market_provider] : '—'}</span></Row>
          <Row title={t.sDb} desc={t.sDbD}><span className="text-2">SQLite</span></Row>
        </section>
      </div>
    </>
  );
}
