[English](README_en.md) | **简体中文**

# duetfolio ◈

**美股港股一起买？每天打开看一眼，就知道按港币算一共赚了多少。**

![duetfolio dashboard](assets/dashboard.png)

---

## 这是什么

duetfolio 是一个跑在你自己电脑上的组合记账本，专门给**同时玩美股和港股**的人：

- 两个市场的持仓放在一个页面看，不用来回切券商 App
- 美元、港币的资产自动折成你选的本币（港币 / 美元 / 人民币），总数一目了然
- 每笔买入、卖出、分红都按真实时间和金额，算出**年化收益率（XIRR）**——不是简单的"涨了几个点"，而是"这笔钱到底跑赢了多少"

不用注册、不用上传数据，账本存在你电脑本地。深色 / 浅色模式右上角一键切换。

## 3 分钟上手（Windows）

1. 装 Python（[官网下载](https://www.python.org/downloads/)，安装时勾选 **Add python.exe to PATH**）
2. 点本仓库绿色 **Code** → **Download ZIP**，解压
3. 在项目文件夹里打开 PowerShell，运行 **`& .\start.ps1`**（等它装好依赖，首次较慢），浏览器会自动打开仪表盘

> 如果提示"禁止运行脚本"，先跑一次 `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`（输 `Y` 确认），再运行上面的命令。
> 打开的是 [http://127.0.0.1:8000](http://127.0.0.1:8000) —— 后端会把前端页面一起 serve 起来，**只用开这一个窗口**，关掉即停止。
> 备选：双击 `start.bat` 效果相同（部分系统上批处理窗口可能闪退，改用上面的 PowerShell 方式）。
> 只要 API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
> 前端手动开发：`cd frontend && npm install && npm run dev`（需 Node.js 18+，此时页面在 `:5173`）

## 记第一笔账

**① 加标的** — 打开「标的」页，搜索框输入 `03152`、`SGOV`、`腾讯` 或 `博时`，点搜索结果自动填好代码、市场和币种，保存。

**② 记买入** — 打开「流水」页，选标的、填数量、单价、日期，保存。持仓数量和平均成本自动算好。

**③ 刷新行情** — 回仪表盘点「刷新行情」，总市值、总盈亏、XIRR 就出来了。按钮旁边会显示"行情截至几点、数据哪来的"。

> 成交记录多？「流水」页 → 「导入券商 CSV」，支持富途 / 盈透导出的成交记录，先预览再确认写入，没见过的代码会自动建标的。
> 有入金出金？「流水」页底部「现金」卡记一笔转入 / 转出，XIRR 会把这笔钱的进出算进去——年化算的是"这堆钱的回报"，不只是"这几只票的回报"。

## 常见问题

**港股代码怎么写？**
搜出来点一下就行，不用手写。非要手写的话：雅虎格式去前导零，`03152` → `3152.HK`，`00700` → `700.HK`；美股直接写 `AAPL`、`SGOV`。

**总盈亏是怎么算的？**
总盈亏 = 未实现盈亏（现价 − 剩余持仓成本）+ 已实现盈亏（卖出和分红，扣掉手续费）。页面上的"投入成本"是**还拿在手里的仓位**的成本，不是历史上累计投过多少钱。

**XIRR 的数字为什么大得离谱？**
XIRR 是"年化"——持有 4 天赚 0.1%，年化出来会非常大。这是数学特性，不是 bug，拿得越久数字越实在。每笔流水的汇率按**交易当日**的汇率折算（记账时自动抓取），汇率波动不会被算进投资收益。

**行情准吗？**
默认走**东方财富**（更接近实时），如果它某只票没返回，会自动用**雅虎财经**补（延迟约 15 分钟）。每条行情会记下实际来源，仪表盘"行情截至"旁边能看到。

**首页的净值曲线是怎么画的？**
每天的总市值 = 当天持仓数量 × 当天收盘价，只用已存进库的行情快照（不触发实时抓取）。历史日期的汇率统一按**今天**的汇率折算——曲线形状可信，老日期的绝对值仅供参考，旁边有文字说明。

**数据存在哪？**
你电脑本地的 SQLite 文件（`backend/duetfolio.db`），不上传到任何地方。

---

## 架构（给开发者看）

```
frontend/  React 18 + Vite，手写 SVG 图表（零图表库依赖）
backend/   FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2
db         SQLite（默认零配置）/ PostgreSQL（DATABASE_URL 一键切换）
```

### 核心口径

- **持仓与成本**：平均成本法。买入按比例抬高成本，卖出按比例释放成本，清仓后成本归零（不会出现负成本）。
- **XIRR**：纯 Python 实现（牛顿迭代，`backend/app/services/xirr.py`）。现金流 = 买入（负，含手续费）/ 卖出与分红（正，扣手续费）/ 现金转入（负）/ 转出（正），终值取**最新行情日期**的组合总市值（不用今天，避免年化虚高）。现金流不足两笔或全同号时返回空，不硬算。
- **汇率**：每笔交易在记账时抓取**交易当日**汇率存入 `fx_to_hkd`，XIRR 现金流按当时汇率折算；最新汇率 10 分钟 TTL 缓存。
- **缺数据熔断**：任一持仓缺行情、或任一币种缺汇率时，总市值 / 总盈亏 / XIRR 直接置空（并在前端黄条提示缺哪只），不输出"部分可信"的总数。

### 行情源设计

`backend/app/services/market.py` 内 `BaseProvider` 抽象，`MARKET_PROVIDER` 环境变量切换（默认 `eastmoney`，可选 `yfinance`）。

- **主备链路**：`refresh_all` 对每只标的先走主行情源，返回为空再走备选源；快照的 `source`/`fetched_at` 记录**实际**来源与抓取时间，前端"行情截至"据此展示。
- **eastmoney**：非官方 push2 接口（`f43` 最新价 / `f60` 昨收），符号经 suggest API 映射（`3152.HK` → `116.03152`，前导零自动补回），yfinance 做汇率（东财无可靠外汇接口）。
- **标的搜索**：`GET /api/instruments/search` 并发查 Yahoo search + 东财 suggest（通用 + `mktnum=116` 港股专查，防止内地基金把港股 ETF 挤出排名），去重、只保留美/港。

### API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 存活探针 |
| GET/POST/DELETE | `/api/instruments…` | 标的增删查 |
| GET | `/api/instruments/search?q=` | 代码/中文名模糊搜索 |
| GET/POST/PUT/DELETE | `/api/transactions…` | 流水增删改查（含行内编辑） |
| POST | `/api/transactions/import/preview` | 券商 CSV 解析预览（富途/盈透/通用表） |
| POST | `/api/transactions/import` | 确认导入（未知代码自动建标的） |
| GET/POST/DELETE | `/api/cash…` | 现金转入/转出 |
| GET | `/api/portfolio/summary?base=` | 总市值/盈亏/XIRR/分红/持仓明细 |
| GET | `/api/portfolio/history?base=` | 净值曲线点 |
| POST | `/api/prices/refresh` | 刷新全部行情（8 线程并发） |

完整交互式文档：启动后端后打开 `/docs`。

### 本地开发

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload        # 数据库迁移启动时自动执行
.venv/bin/python -m pytest tests/              # 24 个测试

cd ../frontend
npm install && npm run dev
```

### 配置（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `MARKET_PROVIDER` | `eastmoney` | 主行情源；`yfinance` 可切换，另一方自动成为备选 |
| `BASE_CURRENCY` | `HKD` | 本币 |
| `DATABASE_URL` | 本地 SQLite | `postgresql+psycopg2://…` 切 Postgres |
| `CORS_ORIGINS` | `*` | 前端跨域 |
| `BASIC_AUTH_USER` / `BASIC_AUTH_PASS` | 空 | 设置后 `/api/*` 需要认证（health 除外） |
| `YFINANCE_TIMEOUT` | `15` | yfinance 超时秒数 |

### 部署

```bash
docker compose up --build
```

## 免责

行情数据有延迟、可能不准。本工具仅用于个人记账追踪，不构成投资建议。

## 许可证

MIT

## 请我喝杯咖啡

如果这个项目帮你省了点时间，欢迎请我喝杯咖啡。☕

| 支付宝 | 微信支付 |
| ------ | -------- |
| ![支付宝收款码](assets/alipay.jpg) | ![微信支付收款码](assets/wechat-pay.png) |
