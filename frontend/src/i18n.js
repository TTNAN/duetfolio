// Tiny i18n: no dependency, persisted in localStorage, default zh.
import { useEffect, useState } from 'react';

const STRINGS = {
  zh: {
    brandSub: '美股 · 港股 双市场账本',
    nav: { dashboard: '总览', transactions: '流水', instruments: '标的', settings: '设置', add: '记一笔' },
    online: '后端在线', offline: '后端离线',

    dashTitle: '总览',
    dashSub: (src) => `美股与港股合并估值${src ? ` · 行情来自${src}` : ''}`,
    refresh: '刷新行情', refreshing: '刷新中…', refreshed: (n) => `已更新 ${n} 只标的`,
    priceFailed: (s) => `以下标的行情抓取失败：${s}`,
    apiDown: '连不上后端——请确认 start.ps1 正在运行（端口 8000）。',
    retry: '重试',
    incomplete: '数据不完整，总数已隐藏',
    noPriceFor: (s) => `缺行情：${s}`,
    fxMissing: (s) => `缺汇率：${s}`,

    totalAssets: '总资产',
    posValue: '持仓', cashBal: '现金',
    today: '今日', totalPnlShort: '累计',
    asOf: (t) => `行情截至 ${t}`,
    fxLine: (b, r) => `USD/${b} ${r}`,
    invested: '持仓成本', investedSub: '仍持有仓位的成本',
    totalPnl: '累计盈亏', pnlSub: (r, u) => `已实现 ${r} · 未实现 ${u}`,
    xirr: '年化收益 XIRR', xirrSub: '按真实资金进出时点计算',
    div12m: '近 12 个月分红', divSub: '已扣预扣税',

    perf: '业绩走势',
    modeValue: '市值', modeReturn: '收益率',
    ranges: { '1M': '1月', '3M': '3月', '6M': '6月', YTD: '今年', '1Y': '1年', ALL: '全部' },
    vsCost: '高于成本',
    lValue: '组合市值', lCost: '持仓成本', lPortfolio: '我的组合（时间加权）', lBench: '基准',
    histEmpty: '历史数据还不够画曲线',
    histEmptyD: '一键补全每只标的自首笔交易以来的日线收盘价，曲线立刻就有。',
    backfill: '补全历史行情', backfilling: '补全中…',
    backfillDone: (n, f) => `补全了 ${n} 个交易日${f ? `，${f} 抓取失败` : ''}`,
    fxNote: '历史日期按当前汇率折算',
    twrNote: '时间加权收益剔除了加仓/减仓的影响，可以直接和指数比较',
    benchNone: '基准数据暂不可用',

    allocation: '资产分布',
    markets: { US: '美股', HK: '港股' },
    allocModes: { symbol: '标的', market: '市场', currency: '币种', type: '类型' },
    positions: '个持仓',
    noValued: '暂无可估值持仓',

    holdings: '持仓明细',
    holdingsSub: (n) => `${n} 个在持 · 点击行查看详情`,
    th: { symbol: '标的', qty: '数量', avg: '成本价', price: '现价', day: '今日', value: '市值', weight: '占比', pnl: '浮动盈亏', xirr: 'XIRR' },
    closedPos: (n) => `已清仓 (${n})`,
    realized: '已实现',
    noPrice: '无行情',

    emptyTitle: '把两个市场放进一个账本',
    emptySub: '三步开始：加标的、记一笔、刷新行情。',
    step1: '添加标的', step1d: '输入 00700、AAPL 或“腾讯”，点选即自动填好',
    step2: '记一笔买入', step2d: '数量、单价、日期——持仓与成本自动算好',
    step3: '刷新行情', step3d: '抓最新价，总资产和 XIRR 立刻出来',

    drawer: { qty: '持有数量', avg: '成本价', value: '市值', pnl: '浮动盈亏', realized: '已实现', xirr: '年化 XIRR', price: '价格走势', txns: '交易记录', close: '关闭', addTxn: '记一笔', noPrices: '还没有价格数据' },

    txTitle: '流水', txSub: '每一笔买卖、分红和资金进出',
    tabs: { trades: '交易', cash: '资金进出', import: '导入' },
    filterAll: '全部', searchTx: '搜索代码或备注',
    txTypes: { buy: '买入', sell: '卖出', dividend: '分红' },
    hth: { date: '日期', symbol: '标的', type: '类型', qty: '数量', price: '单价', fee: '费用', amount: '金额', note: '备注' },
    noTxns: '还没有流水', noMatch: '没有匹配的记录',
    confirmDelTxn: '删除这条流水？',
    deleted: '已删除', saved: '已保存', added: '已记录',
    count: (n) => `共 ${n} 条`,
    exportCsv: '导出 CSV',

    addTxn: '记一笔', editTxn: '编辑流水',
    fInst: '标的', fType: '类型', fDate: '日期', fQty: '数量', fPrice: '单价', fFee: '手续费 / 税',
    fNote: '备注', optional: '选填', fDivQty: '股数', fDivPrice: '每股派息',
    holdingNow: (q) => `当前持有 ${q}`,
    sellAll: '全部卖出',
    estTotal: { buy: '预计支出', sell: '预计到账', dividend: '到账金额' },
    fxSaved: '记账汇率（HKD）', refetchFx: '按新日期重抓汇率',
    cancel: '取消', save: '保存', add: '添加', del: '删除', edit: '编辑',
    addInstFirst: '还没有标的——先去「标的」页添加一个。', goInst: '去添加',

    cashTitle: '资金进出', cashSub: '入金和出金会计入 XIRR：年化算的是“这笔钱”的回报',
    cashIn: '转入', cashOut: '转出', fDirection: '方向', fAmount: '金额', fCcy: '币种',
    noCash: '还没有资金记录',

    importTitle: '导入券商 CSV',
    importHint: '支持富途 / 盈透导出的成交记录。先预览，确认后才写入；没见过的代码会自动建标的。',
    dropHere: '把 CSV 拖到这里，或点击选择文件',
    parsing: '解析中…',
    previewLine: (fmt, ok, all) => `${fmt} · 可导入 ${ok} / ${all} 行`,
    confirmImport: (n) => `确认导入 ${n} 行`,
    importDone: (n, e) => `导入完成：新增 ${n} 条${e ? `，${e} 条失败` : ''}`,

    instTitle: '标的', instSub: '你关注和持有的美股、港股',
    searchPh: '搜索代码或名称：00700 / AAPL / 腾讯 / 博时',
    searchHint: '输入即搜，↑↓ 选择、回车添加；类型会按名称自动判断。',
    searching: '搜索中…', searchNoHit: '没找到。换代码或英文名试试。',
    manual: '手动填写', manualHint: '雅虎格式：港股去前导零，00700 → 700.HK；美股直接写 AAPL。',
    fSymbol: '代码', fName: '名称', fMarket: '市场', fAsset: '类型',
    assetTypes: { etf: 'ETF', stock: '股票', fund: '基金' },
    ith: { symbol: '代码', name: '名称', mkt: '市场', ccy: '币种', type: '类型', txns: '流水' },
    noInst: '还没有标的',
    confirmDelInst: (s) => `删除 ${s} 以及它的全部流水？此操作不可撤销。`,
    instAdded: (s) => `已添加 ${s}`,
    exists: '已添加',

    setTitle: '设置', setSub: '显示偏好与数据管理',
    secDisplay: '显示', secData: '数据', secAbout: '关于',
    sLang: '语言', sLangD: '界面语言',
    sTheme: '主题', sThemeD: '深色 / 浅色', themes: { dark: '深色', light: '浅色' },
    sUpdown: '涨跌颜色', sUpdownD: '红涨绿跌（A股/港股习惯）或绿涨红跌（美股习惯）', updown: { cn: '红涨绿跌', intl: '绿涨红跌' },
    sBase: '默认本币', sBaseD: '总览页默认的折算货币',
    sPrivacy: '隐私模式', sPrivacyD: '隐藏金额，只看比例——截图分享时用', on: '开', off: '关',
    sBackfill: '补全历史行情', sBackfillD: '为每只标的抓取自首笔交易以来的日线收盘价（只补缺失的日期，不覆盖实时行情）。',
    sCsv: '导出流水 CSV', sCsvD: '全部交易导出为表格，Excel 可直接打开。',
    sBackup: '下载完整备份', sBackupD: '标的、流水、资金进出打包成一个 JSON 文件。',
    sRestore: '从备份恢复', sRestoreD: '用备份文件替换当前全部数据。会先校验文件，校验不过不会动现有数据。',
    restoreConfirm: '恢复会清空当前全部数据并替换为备份内容，确定吗？',
    restored: (i, t) => `已恢复 ${i} 个标的、${t} 条流水`,
    download: '下载', choose: '选择文件', run: '开始',
    sVersion: '版本', sProvider: '行情源', sDb: '数据存储', sDbD: '本地 SQLite，不上传任何地方',
    providerNames: { yfinance: '雅虎财经', eastmoney: '东方财富', sina: '新浪财经' },
    srcName: { yfinance: '雅虎（延迟）', eastmoney: '东方财富', sina: '新浪财经', 'yfinance-hist': '雅虎日线', 'eastmoney-hist': '东财日线' },
    disclaimer: '行情可能延迟，仅供个人记账参考，不构成投资建议。',
    shortcuts: '快捷键：N 记一笔 · R 刷新行情 · 1–4 切换页面',
  },
  en: {
    brandSub: 'US + HK portfolio ledger',
    nav: { dashboard: 'Overview', transactions: 'Activity', instruments: 'Instruments', settings: 'Settings', add: 'Add' },
    online: 'Backend online', offline: 'Backend offline',

    dashTitle: 'Overview',
    dashSub: (src) => `US and HK holdings, valued together${src ? ` · quotes via ${src}` : ''}`,
    refresh: 'Refresh prices', refreshing: 'Refreshing…', refreshed: (n) => `Updated ${n} instruments`,
    priceFailed: (s) => `Couldn't fetch prices for: ${s}`,
    apiDown: "Can't reach the backend — is start.ps1 running on port 8000?",
    retry: 'Retry',
    incomplete: 'Incomplete data, totals hidden',
    noPriceFor: (s) => `no price: ${s}`,
    fxMissing: (s) => `no FX: ${s}`,

    totalAssets: 'Total assets',
    posValue: 'Positions', cashBal: 'Cash',
    today: 'Today', totalPnlShort: 'All-time',
    asOf: (t) => `Quotes as of ${t}`,
    fxLine: (b, r) => `USD/${b} ${r}`,
    invested: 'Cost basis', investedSub: 'of positions still held',
    totalPnl: 'Total P&L', pnlSub: (r, u) => `realized ${r} · unrealized ${u}`,
    xirr: 'XIRR', xirrSub: 'money-weighted, annualized',
    div12m: 'Dividends, 12m', divSub: 'net of withholding',

    perf: 'Performance',
    modeValue: 'Value', modeReturn: 'Return',
    ranges: { '1M': '1M', '3M': '3M', '6M': '6M', YTD: 'YTD', '1Y': '1Y', ALL: 'All' },
    vsCost: 'vs cost',
    lValue: 'Portfolio value', lCost: 'Cost basis', lPortfolio: 'Portfolio (time-weighted)', lBench: 'Benchmark',
    histEmpty: 'Not enough history to draw a chart yet',
    histEmptyD: 'Backfill daily closes since your first trade and the curve appears instantly.',
    backfill: 'Backfill history', backfilling: 'Backfilling…',
    backfillDone: (n, f) => `Backfilled ${n} trading days${f ? `, ${f} failed` : ''}`,
    fxNote: "older days use today's FX",
    twrNote: 'Time-weighted return strips out deposits and top-ups, so it compares fairly with an index',
    benchNone: 'Benchmark data unavailable',

    allocation: 'Allocation',
    markets: { US: 'US', HK: 'Hong Kong' },
    allocModes: { symbol: 'Symbol', market: 'Market', currency: 'Currency', type: 'Type' },
    positions: 'positions',
    noValued: 'No valued holdings yet',

    holdings: 'Holdings',
    holdingsSub: (n) => `${n} open · click a row for details`,
    th: { symbol: 'Instrument', qty: 'Qty', avg: 'Avg cost', price: 'Price', day: 'Today', value: 'Value', weight: 'Weight', pnl: 'Unrealized', xirr: 'XIRR' },
    closedPos: (n) => `Closed (${n})`,
    realized: 'Realized',
    noPrice: 'no quote',

    emptyTitle: 'Two markets, one ledger',
    emptySub: 'Three steps: add an instrument, record a trade, refresh prices.',
    step1: 'Add an instrument', step1d: 'Type 00700, AAPL or a name — pick a hit to auto-fill',
    step2: 'Record a buy', step2d: 'Quantity, price, date — position and cost update automatically',
    step3: 'Refresh prices', step3d: 'Fetch quotes; total assets and XIRR appear',

    drawer: { qty: 'Quantity', avg: 'Avg cost', value: 'Value', pnl: 'Unrealized', realized: 'Realized', xirr: 'XIRR', price: 'Price', txns: 'Transactions', close: 'Close', addTxn: 'Add', noPrices: 'No price data yet' },

    txTitle: 'Activity', txSub: 'Every trade, dividend and cash movement',
    tabs: { trades: 'Trades', cash: 'Cash', import: 'Import' },
    filterAll: 'All', searchTx: 'Search symbol or note',
    txTypes: { buy: 'Buy', sell: 'Sell', dividend: 'Dividend' },
    hth: { date: 'Date', symbol: 'Instrument', type: 'Type', qty: 'Qty', price: 'Price', fee: 'Fee', amount: 'Amount', note: 'Note' },
    noTxns: 'No transactions yet', noMatch: 'Nothing matches',
    confirmDelTxn: 'Delete this transaction?',
    deleted: 'Deleted', saved: 'Saved', added: 'Recorded',
    count: (n) => `${n} total`,
    exportCsv: 'Export CSV',

    addTxn: 'New transaction', editTxn: 'Edit transaction',
    fInst: 'Instrument', fType: 'Type', fDate: 'Date', fQty: 'Quantity', fPrice: 'Price', fFee: 'Fee / tax',
    fNote: 'Note', optional: 'optional', fDivQty: 'Shares', fDivPrice: 'Per share',
    holdingNow: (q) => `holding ${q}`,
    sellAll: 'Sell all',
    estTotal: { buy: 'Total cost', sell: 'Net proceeds', dividend: 'Net received' },
    fxSaved: 'Booked FX (HKD)', refetchFx: 'Refetch FX for the new date',
    cancel: 'Cancel', save: 'Save', add: 'Add', del: 'Delete', edit: 'Edit',
    addInstFirst: 'No instruments yet — add one first.', goInst: 'Add instrument',

    cashTitle: 'Cash movements', cashSub: 'Deposits and withdrawals feed XIRR — it measures the return on the money itself',
    cashIn: 'Deposit', cashOut: 'Withdraw', fDirection: 'Direction', fAmount: 'Amount', fCcy: 'Currency',
    noCash: 'No cash movements yet',

    importTitle: 'Import broker CSV',
    importHint: 'Futu / IBKR trade exports. Preview first, nothing is written until you confirm; unknown tickers become instruments.',
    dropHere: 'Drop a CSV here, or click to choose',
    parsing: 'Parsing…',
    previewLine: (fmt, ok, all) => `${fmt} · ${ok} of ${all} rows importable`,
    confirmImport: (n) => `Import ${n} rows`,
    importDone: (n, e) => `Imported ${n}${e ? `, ${e} failed` : ''}`,

    instTitle: 'Instruments', instSub: 'The US and HK names you hold or track',
    searchPh: 'Search ticker or name: 00700 / AAPL / Tencent',
    searchHint: 'Results appear as you type; ↑↓ to choose, Enter to add.',
    searching: 'Searching…', searchNoHit: 'No hits. Try a ticker or English name.',
    manual: 'Enter manually', manualHint: 'Yahoo format: drop HK leading zeros, 00700 → 700.HK; US as-is, e.g. AAPL.',
    fSymbol: 'Symbol', fName: 'Name', fMarket: 'Market', fAsset: 'Type',
    assetTypes: { etf: 'ETF', stock: 'Stock', fund: 'Fund' },
    ith: { symbol: 'Symbol', name: 'Name', mkt: 'Market', ccy: 'Ccy', type: 'Type', txns: 'Txns' },
    noInst: 'No instruments yet',
    confirmDelInst: (s) => `Delete ${s} and ALL its transactions? This can't be undone.`,
    instAdded: (s) => `Added ${s}`,
    exists: 'Added',

    setTitle: 'Settings', setSub: 'Display preferences and your data',
    secDisplay: 'Display', secData: 'Data', secAbout: 'About',
    sLang: 'Language', sLangD: 'Interface language',
    sTheme: 'Theme', sThemeD: 'Dark or light', themes: { dark: 'Dark', light: 'Light' },
    sUpdown: 'Gain / loss colors', sUpdownD: 'Red-up (CN/HK convention) or green-up (US convention)', updown: { cn: 'Red up', intl: 'Green up' },
    sBase: 'Default currency', sBaseD: 'Valuation currency the overview opens in',
    sPrivacy: 'Privacy mode', sPrivacyD: 'Hide amounts, keep percentages — handy for screenshots', on: 'On', off: 'Off',
    sBackfill: 'Backfill price history', sBackfillD: 'Fetch daily closes since each instrument’s first trade (missing days only; live quotes are never overwritten).',
    sCsv: 'Export transactions CSV', sCsvD: 'Every trade as a spreadsheet that opens in Excel.',
    sBackup: 'Download full backup', sBackupD: 'Instruments, transactions and cash movements in one JSON file.',
    sRestore: 'Restore from backup', sRestoreD: 'Replace all data with a backup. The file is validated first; nothing changes if it fails.',
    restoreConfirm: 'Restoring wipes all current data and replaces it with the backup. Continue?',
    restored: (i, t) => `Restored ${i} instruments, ${t} transactions`,
    download: 'Download', choose: 'Choose file', run: 'Run',
    sVersion: 'Version', sProvider: 'Quote source', sDb: 'Storage', sDbD: 'Local SQLite, never uploaded',
    providerNames: { yfinance: 'Yahoo Finance', eastmoney: 'East Money', sina: 'Sina Finance' },
    srcName: { yfinance: 'Yahoo (delayed)', eastmoney: 'East Money', sina: 'Sina', 'yfinance-hist': 'Yahoo daily', 'eastmoney-hist': 'East Money daily' },
    disclaimer: 'Quotes may be delayed. For personal record-keeping only, not investment advice.',
    shortcuts: 'Shortcuts: N add · R refresh · 1–4 switch pages',
  },
};

let lang = 'zh';
try {
  lang = localStorage.getItem('duetfolio-lang') || 'zh';
  if (!STRINGS[lang]) lang = 'zh';
} catch { /* private mode */ }
document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';

const listeners = new Set();

export function setLang(l) {
  if (!STRINGS[l]) return;
  lang = l;
  document.documentElement.lang = l === 'zh' ? 'zh-CN' : 'en';
  try { localStorage.setItem('duetfolio-lang', l); } catch { /* ignore */ }
  listeners.forEach((fn) => fn(l));
}

export function useLang() {
  const [l, setL] = useState(lang);
  useEffect(() => {
    listeners.add(setL);
    return () => { listeners.delete(setL); };
  }, []);
  return { lang: l, setLang, t: STRINGS[l] };
}
