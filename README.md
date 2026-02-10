# FundVal Live

![GitHub stars](https://img.shields.io/github/stars/MingGH/FundVal-Live?style=social)
![GitHub views](https://komarev.com/ghpvc/?username=MingGH&repo=FundVal-Live&color=blue&style=flat-square&label=views)

**盘中基金实时估值与逻辑审计系统**

拒绝黑箱，拒绝情绪化叙事。基于透明的持仓穿透 + 实时行情加权计算 + 硬核数学模型，让基金估值回归数学事实。

---

## 目录

- [预览](#预览)
- [快速开始](#快速开始)
- [核心功能](#核心功能)
- [技术架构](#技术架构)

---

## 预览

### 资金看板
![Dashboard](docs/汇总页面.png)

### 多账户管理
![Multi Account](docs/多账户.png)

### 技术指标审计
![Technical Indicators](docs/基金详情-技术指标.png)

### AI 深度逻辑报告
![AI Analysis](docs/AI分析-持仓股明细.png)

### 自定义 AI 提示词
![Custom Prompts](docs/自定义提示词.png)

### 数据导入导出
![Data Import Export](docs/数据导入导出.png)

---

## 快速开始

### Docker 部署

```bash
# 快速启动
docker run -d -p 21345:21345 \
  -v fundval-data:/app/backend/data \
  -e DATABASE_URL=mysql://fundval:yourpass@mysql-host:3306/fundval \
  -e JWT_SECRET=your-random-secret \
  -e ADMIN_PASSWORD=admin123 \
  registry.cn-hongkong.aliyuncs.com/runnable-run/fundval:latest
```

可选环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | MySQL 连接地址 | `mysql://funduser:fundpass@localhost:3306/fundval` |
| `JWT_SECRET` | JWT 签名密钥 | 内置默认值（生产环境务必修改） |
| `ADMIN_PASSWORD` | 管理员初始密码 | `admin123` |
| `OPENAI_API_KEY` | AI 分析 API Key | 空（不启用 AI） |
| `OPENAI_API_BASE` | AI API 地址 | `https://api.openai.com/v1` |
| `AI_MODEL_NAME` | AI 模型名称 | `gpt-3.5-turbo` |
| `SMTP_HOST` | 邮件服务器 | `smtp.gmail.com` |
| `SMTP_PORT` | 邮件端口 | `587` |
| `SMTP_USER` | 邮件账号 | 空 |
| `SMTP_PASSWORD` | 邮件密码 | 空 |

访问 `http://localhost:21345`，默认管理员账号 `admin`，密码为 `ADMIN_PASSWORD` 环境变量的值。

---

## 核心功能

### 盘中实时估值
- 支持 A 股 / 港股 / 美股实时行情
- 自动识别 QDII 基金持仓代码格式
- 多源容灾（天天基金 ⇄ 新浪财经）

### 技术指标审计
基于 250 个交易日净值序列，Numpy 向量化计算：
- 夏普比率 — 风险调整后收益效率
- 最大回撤 — 历史极端风险审计
- 年化波动率 — 持仓稳定性量化

### AI 逻辑审计
- 支持自定义 AI 提示词模板（内置 Linus 风格 / 温和风格）
- 基于数学事实输出持有 / 止盈 / 定投指令
- 兼容 OpenAI / DeepSeek 等 API

### 持仓管理
- 多账户管理，支持全部账户聚合视图
- 加仓 / 减仓按 T+1 规则确认，自动更新成本与份额
- 实时计算持有收益，组合饼图可视化
- 一键同步持仓到关注列表

### 用户管理（管理员）
- 创建 / 删除用户，创建后直接展示密码方便分发
- 重置用户密码
- 启用 / 禁用用户

### 数据导入导出
- 支持导出为 JSON，可选择性导出模块
- 合并模式（保留现有数据）/ 替换模式（清空后导入）
- 敏感数据自动脱敏

### 订阅提醒
- 波动提醒（涨跌幅超阈值）
- 每日摘要（指定时间发送）
- 邮件通知（SMTP）

---

## 技术架构

```
前端：React 19 + Vite + Tailwind CSS + Recharts + Lucide Icons
后端：FastAPI + MySQL + Numpy + AkShare
AI：OpenAI / DeepSeek 兼容 API
```

---

## 开源协议

本项目基于 [Ye-Yu-Mo/FundVal-Live](https://github.com/Ye-Yu-Mo/FundVal-Live) 二次开发，采用 **AGPL-3.0** 协议。你可以自由使用和修改，但如果用本项目代码提供网络服务，必须开源你的修改。详见 [LICENSE](LICENSE)。

---

## 免责声明

本项目提供的数据与分析仅供技术研究使用，不构成任何投资建议。市场有风险，交易需谨慎。

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=MingGH/FundVal-Live&type=date&legend=top-left)](https://www.star-history.com/#MingGH/FundVal-Live&type=date&legend=top-left)
