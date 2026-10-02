// Tiny i18n: no dependency, persisted in localStorage, default zh.
import { useEffect, useState } from 'react';

const STRINGS = {
  en: {
    brandSub: 'US + HK portfolio tracker',
    footer: 'duetfolio · FastAPI + React · prices via Yahoo Finance (15-min delay)',
    tabs: { dashboard: '📊 Dashboard', transactions: '🧾 Transactions', instruments: '🏷 Instruments' },
    langBtn: '中文',

    apiDown: 'API unreachable — is the backend running on :8000?',
    refresh: '⟳ Refresh prices',
    refreshing: 'Refreshing…',
    priceFailed: 'Price fetch failed: ',
    incomplete: 'Incomplete data, totals hidden:',
    noPriceFor: 'no price for',
    fxMissing: 'FX missing',

    totalValue: 'Total value',
    invested: 'Invested',
    totalPnl: 'Total P&L',
    xirr: 'XIRR (annualized)',
    xirrSub: 'incl. dividends & terminal value',
    realized: 'realized',
    unrealized: 'unrealized',

    netWorth: 'Net worth',
    histLoading: 'Loading…',
    histEmpty: 'Not enough history yet — refresh prices a few times.',
    since: 'since',
    fxNote: "FX uses today's rate for all days",

    allocation: 'Allocation',
    holdings: 'Holdings',
    th: { symbol: 'Symbol', qty: 'Qty', avgCost: 'Avg cost', price: 'Price', value: 'Value', pnl: 'P&L' },
    stale: 'stale',
    noInstruments: 'No instruments yet — add some under Instruments.',
    positions: 'positions',
    noValued: 'No valued holdings yet',

    addTxn: 'Add transaction',
    addInstFirst: 'Add an instrument first.',
    fInst: 'Instrument',
    fType: 'Type',
    fDate: 'Date',
    fQty: 'Quantity',
    fPrice: 'Price / share',
    fFee: 'Fee',
    fNote: 'Note',
    optional: 'optional',
    add: 'Add',
    history: 'History',
    hth: { date: 'Date', symbol: 'Symbol', type: 'Type', qty: 'Qty', price: 'Price', fee: 'Fee' },
    del: 'delete',
    noTxns: 'No transactions yet.',
    confirmDelTxn: 'Delete this transaction?',
    txnTypes: { buy: 'buy', sell: 'sell', dividend: 'dividend' },

    addInst: 'Add instrument',
    fSymbol: 'Symbol (Yahoo ticker)',
    fName: 'Name',
    fMarket: 'Market',
    fCcy: 'Currency',
    fAsset: 'Type',
    assetTypes: { etf: 'ETF', stock: 'Stock', fund: 'Fund' },
    instTip: 'Tip: Yahoo drops the leading zero on 5-digit HK codes — e.g. enter 3152.HK for 03152 (Bosera HKD Money Market ETF). US tickers as-is (e.g. SGOV).',
    instList: 'Instruments',
    ith: { symbol: 'Symbol', name: 'Name', mkt: 'Mkt', ccy: 'Ccy' },
    noInst: 'Nothing here yet.',
    confirmDelInst: (s) => `Delete ${s} and ALL its transactions?`,
    symPh: 'SGOV or 03152.HK',
    namePh: 'iShares 0-3 Month Treasury Bond ETF',
  },
  zh: {
    brandSub: '美股 + 港股组合追踪',
    footer: 'duetfolio · FastAPI + React · 行情来自雅虎财经（延迟约 15 分钟）',
    tabs: { dashboard: '📊 仪表盘', transactions: '🧾 流水', instruments: '🏷 标的' },
    langBtn: 'EN',

    apiDown: '连不上后端——:8000 跑起来了吗？',
    refresh: '⟳ 刷新行情',
    refreshing: '刷新中…',
    priceFailed: '行情抓取失败：',
    incomplete: '数据不完整，总数已隐藏：',
    noPriceFor: '缺行情',
    fxMissing: '汇率缺失',

    totalValue: '总市值',
    invested: '投入成本',
    totalPnl: '总盈亏',
    xirr: 'XIRR（年化）',
    xirrSub: '含分红与终值',
    realized: '已实现',
    unrealized: '未实现',

    netWorth: '净值曲线',
    histLoading: '加载中…',
    histEmpty: '历史数据不足——多刷新几次行情。',
    since: '自',
    fxNote: '历史日期按今日汇率折算',

    allocation: '仓位分布',
    holdings: '持仓',
    th: { symbol: '代码', qty: '数量', avgCost: '均价', price: '现价', value: '市值', pnl: '盈亏' },
    stale: '无行情',
    noInstruments: '还没有标的——去「标的」页添加。',
    positions: '个持仓',
    noValued: '暂无有市值的持仓',

    addTxn: '记一笔',
    addInstFirst: '先去「标的」页添加一个标的。',
    fInst: '标的',
    fType: '类型',
    fDate: '日期',
    fQty: '数量',
    fPrice: '单价',
    fFee: '手续费',
    fNote: '备注',
    optional: '选填',
    add: '添加',
    history: '流水记录',
    hth: { date: '日期', symbol: '代码', type: '类型', qty: '数量', price: '单价', fee: '手续费' },
    del: '删除',
    noTxns: '还没有流水。',
    confirmDelTxn: '删除这条流水？',
    txnTypes: { buy: '买入', sell: '卖出', dividend: '分红' },

    addInst: '添加标的',
    fSymbol: '代码（Yahoo 格式）',
    fName: '名称',
    fMarket: '市场',
    fCcy: '币种',
    fAsset: '类型',
    assetTypes: { etf: 'ETF', stock: '股票', fund: '基金' },
    instTip: '提示：雅虎会去掉 5 位港股代码的前导零——比如 03152 要填 3152.HK（博时港元货币市场 ETF），美股直接填代码（如 SGOV）。',
    instList: '标的列表',
    ith: { symbol: '代码', name: '名称', mkt: '市场', ccy: '币种' },
    noInst: '还没有标的。',
    confirmDelInst: (s) => `删除 ${s} 及其全部流水？`,
    symPh: 'SGOV 或 03152.HK',
    namePh: 'iShares 0-3 个月美国国债 ETF',
  },
};

let lang = 'zh';
try {
  lang = localStorage.getItem('duetfolio-lang') || 'zh';
  if (!STRINGS[lang]) lang = 'zh';
} catch { /* private mode */ }

const listeners = new Set();

export function setLang(l) {
  if (!STRINGS[l]) return;
  lang = l;
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
