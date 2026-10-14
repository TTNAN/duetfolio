[English](README_en.md) | **简体中文**

# duetfolio ◈

[![test](https://github.com/TTNAN/duetfolio/actions/workflows/test.yml/badge.svg)](https://github.com/TTNAN/duetfolio/actions/workflows/test.yml)
[![在线演示](https://img.shields.io/badge/%E5%9C%A8%E7%BA%BF%E6%BC%94%E7%A4%BA-%E5%85%8D%E7%99%BB%E5%BD%95-b89a6a)](https://ttnan.github.io/duetfolio/)

**美股港股一起买？每天打开看一眼，就知道按港币算一共赚了多少。**

![duetfolio dashboard](assets/dashboard.png)

---

## 这是什么

duetfolio 是一个跑在你自己电脑上的组合记账本，专门给**同时玩美股和港股**的人：

- 两个市场的持仓放在一个页面看，不用来回切券商 App
- 美元、港币的资产自动折成你选的本币（港币 / 美元 / 人民币），总数一目了然
- 每笔买入、卖出、分红都按真实时间和金额，算出**年化收益率（XIRR）**——不是简单的"涨了几个点"，而是"这笔钱到底跑赢了多少"

不用注册、不用上传数据，账本存在你电脑本地。

### v0.3 新增

- **拆合股**：新增「拆合股」记账类型，填比例即可（1 拆 4 填 4，10 股合 1 填 0.1），持股数自动换算、总成本不变，历史净值曲线不会在拆股日出现假暴跌
- **加权平均 / 先进先出 可切换**：设置里一键切换成本口径，已实现和未实现盈亏能和券商 App 对上（总盈亏、XIRR 不受影响）
- **券商账单直接导入**：内置富途 / moomoo、老虎、盈透 IBKR、嘉信 Schwab 原始导出格式，不用改 Excel 列名；分项费用自动加总
- **Docker 部署修好了**：之前镜像构建会直接失败；现在前端容器内置反向代理，放到 NAS / 远程服务器上也能直接用，后端改为非 root 运行、依赖版本锁定
- **更快**：组合计算结果按数据版本缓存，数据没变不重复计算；行情 5 分钟内刚拉过不重复请求（重启后依然有效）
- **XIRR 更稳**：频繁大额进出、正负交替的现金流也能算出结果（牛顿法不收敛时自动切换 Brent 区间求解）
- **键盘与手机体验**：弹窗 Esc 关闭、焦点不跑出弹窗、图表可用方向键查看每日数值；手机上宽表格横向滑动时首列固定
- **在线演示**：[ttnan.github.io/duetfolio](https://ttnan.github.io/duetfolio/) 点开即用、无需登录（虚构组合、只读，行情每个交易日自动更新）

### v0.2 新增

- **全新界面**：侧边栏布局、衬线大字总资产、深浅双主题、手机底部导航，字体随包内置（离线、内地网络都一样好看）
- **今日盈亏**：总资产下方直接显示今天赚/亏了多少
- **跑赢大盘了吗**：「收益率」视图用时间加权收益（剔除加仓影响）和 纳指100 / 标普500 / 恒指 / 恒生科技 同框对比
- **一键补全历史**：自动抓每只标的自首笔交易以来的日线，净值曲线不用再"多刷几次"
- **持仓详情抽屉**：价格走势 + 买卖点标记 + 单只标的 XIRR
- **红涨绿跌 / 绿涨红跌** 可切换，**隐私模式** 一键隐藏金额方便截图
- **导出 CSV、完整备份 / 恢复**，快捷键 `N` 记一笔、`R` 刷新、`1–4` 切页

![收益率 vs 基准](assets/benchmark.png)

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

**③ 刷新行情** — 回总览点「刷新行情」（或按 `R`），总资产、今日盈亏、XIRR 就出来了。曲线是空的？点「补全历史行情」，几秒后就有完整走势。

> 成交记录多？「流水」页 → 「导入券商 CSV」，支持富途、老虎、盈透、嘉信导出的原始账单（选对券商格式或用自动识别），先预览再确认写入，没见过的代码会自动建标的。
> 有入金出金？「流水」→「资金进出」记一笔转入 / 转出。记了之后 XIRR 切换为**账户视角**：只把进出账户的钱当现金流，终值 = 持仓市值 + 账上闲置现金——算的是"这笔钱的回报"。没记就按交易本身算。

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
每天的总市值 = 当天持仓数量 × 当天收盘价，只用已存进库的行情快照（不触发实时抓取）；虚线是当天的持仓成本，两条线的距离就是浮盈。历史日期的汇率统一按**今天**的汇率折算——曲线形状可信，老日期的绝对值仅供参考。

**"收益率"和 XIRR 有什么不同？**
收益率曲线是**时间加权收益（TWR）**：每天的涨跌连乘，加仓减仓不影响，所以能和指数直接比。XIRR 是**资金加权**：钱多的时候涨得多，它就高——反映的是你实际赚到的年化。两个都看才完整。

**数据存在哪？**
你电脑本地的 SQLite 文件（`backend/duetfolio.db`），不上传到任何地方。

---

## 架构（给开发者看）

```
frontend/  React 18 + Vite，手写 SVG 图表（零图表库依赖），lucide 图标，Inter + Instrument Serif 本地字体
backend/   FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2
db         SQLite（默认零配置）/ PostgreSQL（DATABASE_URL 一键切换）
```

### 核心口径

- **持仓与成本**：默认加权平均成本法（`COST_METHOD=fifo` 或设置页可切换先进先出）。卖出手续费只减少到手金额，不会改动剩余持仓成本；清仓后成本归零。两种口径下总盈亏、XIRR 完全一致，只是已实现/未实现的拆分不同。
- **拆合股**：交易类型 `split`，`quantity` 存比例。持股数 × 比例、批次单价 ÷ 比例、总成本不变、无现金流。雅虎/东财日线是复权后的价格，所以历史净值在拆股日之前按「股数 × 之后所有拆股比例」估值；记录或删除拆股时，该标的旧日线会被清掉并重新拉取复权数据。
- **XIRR**：纯 Python 实现（`backend/app/services/xirr.py`）：先用牛顿法（解析导数），不收敛时扫描 −99.99%～+1000% 区间找变号点，再用 Brent 法求根；多个根时取最接近 10% 的那个。没有记资金进出时：现金流 = 买入（负，含手续费）/ 卖出与分红（正，扣手续费），终值 = 持仓市值。记了资金进出后切换为账户视角：现金流只有转入（负）/ 转出（正），终值 = 持仓市值 + 闲置现金（v0.1 两者混算，同一笔钱算了两次，会把 XIRR 严重拉低）。终值取**最新行情日期**（不用今天，避免年化虚高）。每只持仓另算自己的 XIRR。
- **时间加权收益**：`r_d = (V_d + 当日分红) / (V_{d-1} + 当日净买入) − 1`，逐日连乘；基准用 SPY / QQQ / 2800.HK / 3033.HK 日线，从区间第一天归一。
- **汇率**：每笔交易在记账时抓取**交易当日**汇率存入 `fx_to_hkd`，XIRR 现金流按当时汇率折算；最新汇率 10 分钟 TTL 缓存。
- **缺数据熔断**：任一持仓缺行情、或任一币种缺汇率时，总市值 / 总盈亏 / XIRR 直接置空（并在前端黄条提示缺哪只），不输出"部分可信"的总数。

### 行情源设计

`backend/app/services/market.py` 内 `BaseProvider` 抽象，`MARKET_PROVIDER` 环境变量切换（默认 `yfinance`，可选 `eastmoney`）。

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
| POST | `/api/transactions/import/preview?broker=` | 券商 CSV 解析预览（`auto`/`futu`/`tiger`/`ibkr`/`schwab`/`generic`） |
| POST | `/api/transactions/import` | 确认导入（未知代码自动建标的） |
| GET/POST/DELETE | `/api/cash…` | 现金转入/转出 |
| GET | `/api/portfolio/summary?base=&method=` | 总市值/盈亏/XIRR/分红/持仓明细（`method=wac|fifo`） |
| GET | `/api/portfolio/history?base=&method=` | 净值曲线点（市值 / 成本 / 时间加权收益） |
| POST | `/api/prices/refresh?force=` | 刷新全部行情（8 线程并发；5 分钟内刚拉过的跳过，`force=true` 强制） |
| POST | `/api/prices/backfill` | 补全自首笔交易以来的日线（只补缺失日） |
| GET | `/api/benchmark?symbol=&start=` | 基准指数日线（1 小时缓存） |
| GET | `/api/instruments/{id}/prices` | 单只标的已存日线 |
| GET | `/api/transactions/export.csv` | 导出全部流水 |
| GET / POST | `/api/backup` · `/api/backup/restore` | 完整备份 / 恢复（先校验再替换） |

完整交互式文档：启动后端后打开 `/docs`。

### 本地开发

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload        # 数据库迁移启动时自动执行
.venv/bin/python -m pytest tests/              # 47 个测试

cd ../frontend
npm install && npm run dev
npm run lint                                   # ESLint（CI 里也会跑）
```

### 配置（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `MARKET_PROVIDER` | `yfinance` | 主行情源；`eastmoney` 可切换。抓不到的标的按 `yfinance → eastmoney → sina（新浪）` 顺序自动补抓 |
| `BASE_CURRENCY` | `HKD` | 本币 |
| `DATABASE_URL` | 本地 SQLite | `postgresql+psycopg2://…` 切 Postgres |
| `CORS_ORIGINS` | `*`（Docker 里为空） | 允许跨域的前端地址，逗号分隔；留空 = 只允许同源 |
| `COST_METHOD` | `wac` | 默认成本口径：`wac` 加权平均 / `fifo` 先进先出 |
| `QUOTE_TTL_SECONDS` | `300` | 行情多少秒内不重复拉取；`0` 关闭 |
| `DEMO_MODE` | 空 | `true` = 只读在线演示（空库自动灌入虚构组合） |
| `BASIC_AUTH_USER` / `BASIC_AUTH_PASS` | 空 | 设置后 `/api/*` 需要认证（health 除外） |
| `YFINANCE_TIMEOUT` | `15` | yfinance 超时秒数 |

### 部署

**Docker Compose（NAS / 家用服务器 / 云主机）**

```bash
docker compose up -d --build
# 浏览器打开 http://<机器IP>:5173
```

前端容器（nginx）把 `/api/` 反向代理到后端容器，浏览器只和一个地址打交道，所以在 NAS 或远程服务器上同样能用。数据存在 `duetfolio-data` 卷里。对外开放时建议在 `docker-compose.yml` 里打开 `BASIC_AUTH_USER` / `BASIC_AUTH_PASS`。

**单容器**

```bash
docker build -t duetfolio .
docker run -d -p 8000:8000 -v duetfolio-data:/data duetfolio
```

**在线演示**：[ttnan.github.io/duetfolio](https://ttnan.github.io/duetfolio/) 由 GitHub Actions（`.github/workflows/pages.yml`）构建：用虚构组合拉取真实行情，生成静态数据，前端以只读静态模式发布到 GitHub Pages，美股收盘后每个交易日自动重建。Fork 后在 Settings → Pages 把 Source 设为 GitHub Actions，即可得到自己的演示站。

如需带后端的演示，也可以用 `render.yaml` 在 Render 上部署（`DEMO_MODE=true`；免费实例闲置会休眠、没有持久磁盘，只适合演示）。

## 免责

行情数据有延迟、可能不准。本工具仅用于个人记账追踪，不构成投资建议。

## 许可证

MIT

## 请我喝杯咖啡

如果这个项目帮你省了点时间，欢迎请我喝杯咖啡。☕

| 支付宝 | 微信支付 |
| ------ | -------- |
| ![支付宝收款码](assets/alipay.jpg) | ![微信支付收款码](assets/wechat-pay.png) |
