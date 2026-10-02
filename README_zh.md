# duetfolio ◈

给同时持有美股和港股的人用的组合追踪器——比如手里有 SGOV（美元）和 03152（港币），想看一个本币计价的总数。

**[English](README.md)**

## 为什么做

主流组合追踪工具都是欧美视角。持仓横跨美股+港股、两种货币时，只能在脑子里换算。duetfolio 用 Yahoo Finance 拉双市场行情，按实时汇率折成你的本币（HKD/USD/CNY），并算出包含分红的真实年化收益（XIRR）。

## 功能

- 📈 **双市场行情** — 美股代码直接写（`SGOV`），港股加 `.HK` 后缀（`03152.HK`），走 Yahoo Finance
- 💱 **多币种估值** — 所有持仓按实时汇率（`HKD=X`）折成本币
- 🧮 **XIRR** — 基于真实资金流水（买入/卖出/分红 + 期末市值）的年化收益，纯 Python 实现
- 🧾 **交易流水是唯一真相** — 持仓永远由流水推导，不存快照；平均成本法
- 🐳 **一键部署** — `docker compose up`

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI、SQLAlchemy 2.0、Alembic、Pydantic v2 |
| 数据库 | SQLite（开发零配置）/ PostgreSQL（生产，`DATABASE_URL` 一键切换） |
| 行情 | yfinance（Yahoo Finance） |
| 前端 | React 18 + Vite，手写 SVG 图表（零图表依赖） |
| 部署 | Docker Compose |

## 快速开始

**后端：**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload   # 启动时自动跑 Alembic 迁移
# API 文档: http://localhost:8000/docs
```

**前端：**
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173（/api 代理到 :8000）
```

**Docker：**
```bash
docker compose up --build
# 前端: http://localhost:5173  API 文档: http://localhost:8000/docs
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET/POST | `/api/instruments` | 上市/管理标的 |
| DELETE | `/api/instruments/{id}` | 删除（含其全部流水） |
| GET/POST | `/api/transactions` | 流水：买入 / 卖出 / 分红 |
| DELETE | `/api/transactions/{id}` | 删除 |
| GET | `/api/portfolio/summary?base=HKD` | 估值、盈亏、XIRR、持仓明细 |
| POST | `/api/prices/refresh` | 从 Yahoo Finance 拉最新收盘价 |

## Scope 取舍（故意的）

- **单用户、无登录** — 登录是下一个里程碑，不是这版的。
- **默认 SQLite** — 开发零配置；`DATABASE_URL` 切 Postgres 无需改代码。
- **平均成本法** — 简单可审计；FIFO 以后再说。
- **行情是缓存** — `price_snapshots` 是韧性层，不是权威状态。
- **Yahoo 的港股代码去前导零** — 比如 03152（博时港元货币 ETF）在 Yahoo 是 `3152.HK` 而不是 `03152.HK`；部分小港股货币 ETF Yahoo 根本没收录。
- **XIRR 年化很激进** — 持有 4 天算出来的年化会非常极端，这是数学不是 bug；只有全部持仓都有新鲜行情时才报告 XIRR。

## 免责

Yahoo Finance 数据延迟约 15 分钟，可能不准。本工具仅用于个人追踪，不构成投资建议。

## 许可证

MIT
