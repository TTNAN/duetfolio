[English](README_en.md) | **简体中文**

# duetfolio ◈

**同时买了美股和港股？这个工具帮你算清一共赚了多少。**

比如你在美股买了国债 ETF、在港股买了货币基金——两个市场、两种货币，每天想知道"按港币算，我总共是赚是赔"，脑子里换算很麻烦。duetfolio 自动拉取两个市场的行情，全部折成你选的本币（港币/美元/人民币），告诉你一个总数：总市值、总盈亏，还有算上分红的真实年化收益。

## 能帮你做什么

- 📈 **美股 + 港股一起管** — 一个地方看两个市场的持仓，不用来回切 App
- 💱 **自动换算本币** — 美元、港币的持仓，按实时汇率统一折成港币（或美元/人民币）
- 🧮 **真实年化收益（XIRR）** — 不是简单的"涨了百分之几"，而是按你每笔买入、卖出、分红的时间和金额，算出年化收益率
- 🧾 **交易流水自动算持仓** — 你只管记"哪天买了几股、多少钱"，持仓数量和成本自动算出来，不用自己维护表格
- 🔌 **两种行情源** — 默认雅虎财经（免配置，延迟约 15 分钟）；也可以切换东方财富（更接近实时，免 key）

## 快速开始（Windows，小白版）

只需要装一个 Python（[官网下载](https://www.python.org/downloads/)，安装时勾选 **Add python.exe to PATH**），然后：

1. 点本仓库绿色的 **Code** 按钮 → **Download ZIP**，解压
2. 双击解压出来的 **`start.bat`**，等它装完依赖、启动后端
3. 浏览器打开 http://127.0.0.1:8000/docs

看到页面就说明启动成功了。下面开始记第一笔账。

## 第一次使用：记一笔持仓

在刚才打开的页面（API 文档）里操作，全程点鼠标：

**第一步：添加标的** — 找到 `POST /api/instruments`，展开 → **Try it out** → 把请求体换成下面这样 → **Execute**

```json
{"symbol": "SGOV", "name": "iShares 0-3 Month Treasury Bond ETF", "market": "US", "currency": "USD", "asset_type": "etf"}
```

港股的话，代码后面加 `.HK`（注意：雅虎的港股代码**不带前导零**，比如 `03152` 要写成 `3152.HK`）：

```json
{"symbol": "3152.HK", "name": "博时港元货币市场ETF", "market": "HK", "currency": "HKD", "asset_type": "etf"}
```

**第二步：刷新行情** — 找到 `POST /api/prices/refresh` → **Try it out** → **Execute**，看到 `"failed": []` 就是行情拉到了

**第三步：记买入流水** — 找到 `POST /api/transactions`，按你的真实成交填：

```json
{"instrument_id": 1, "type": "buy", "date": "2026-09-28", "quantity": 2, "price": 100.66, "fee": 1.99}
```

（`instrument_id` 是第一步返回里的 `id`；分红就把 `type` 改成 `dividend`，此时 `quantity × price` = 分红到账金额，`fee` 填预扣税/手续费，会从分红里扣除）

**第四步：看总数** — 浏览器打开 http://127.0.0.1:8000/api/portfolio/summary?base=HKD，就能看到按港币折算的总市值、盈亏和 XIRR

> 之后每天只需要做一件事：调一下 `POST /api/prices/refresh` 刷新行情，再看 summary。

## 常见问题

**港股代码怎么写？**
雅虎财经的港股代码去掉了前导零：`03152` 写成 `3152.HK`，`00700` 写成 `700.HK`。美股直接写代码，如 `AAPL`、`SGOV`。

**总盈亏是怎么算的？**
总盈亏 = 未实现盈亏（现价 − 剩余持仓成本）+ 已实现盈亏（卖出和分红，扣掉手续费）。页面上的 Invested 是**剩余持仓**的成本，不是累计投入过多少钱。

**XIRR 的数字为什么大得离谱？**
XIRR 是"年化"收益——持有 4 天赚了 0.1%，年化出来会非常大。这是数学特性，不是 bug。持仓时间越长，数字越接近真实水平。每笔流水的汇率按**交易当日**的汇率折算（记账时自动抓取），所以汇率波动不会被算进投资收益。

**行情准吗？**
默认雅虎财经延迟约 15 分钟。想更接近实时可以切换东方财富行情源：关掉后端窗口，在 PowerShell 里先执行 `$env:MARKET_PROVIDER="eastmoney"` 再启动（`start.bat` 里有提示）。

**数据存在哪？**
存在你电脑本地的 SQLite 文件里（`backend/duetfolio.db`），不上传到任何地方。

## 技术栈（给开发者看）

| 层 | 选型 |
|---|---|
| 后端 | FastAPI、SQLAlchemy 2.0、Alembic、Pydantic v2 |
| 数据库 | SQLite（默认零配置）/ PostgreSQL（`DATABASE_URL` 切换） |
| 行情 | yfinance（默认）/ 东方财富 push2（`MARKET_PROVIDER=eastmoney`） |
| 前端 | React 18 + Vite，手写 SVG 图表 |
| 部署 | Docker Compose（`docker compose up --build`） |

数据库迁移在启动时自动执行。行情源是可插拔的 `BaseProvider` 架构（见 `backend/app/services/market.py`）。

## 免责

行情数据有延迟、可能不准。本工具仅用于个人记账追踪，不构成投资建议。

## 许可证

MIT

## 请我喝杯咖啡

如果这个项目帮你省了点时间，欢迎请我喝杯咖啡。☕

| 支付宝 | 微信支付 |
| ------ | -------- |
| ![支付宝收款码](assets/alipay.jpg) | ![微信支付收款码](assets/wechat-pay.png) |
