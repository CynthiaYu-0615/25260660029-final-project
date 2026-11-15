---
description: 登记 PYPL 持仓变化，包括买入或卖出的数量与价格；系统仅登记，不执行真实交易。
---

# /pypl:trade

## 作用

用户报告自己买入或卖出了 PYPL，系统将数量和价格登记到 `.pypl/holdings.json`，并触发一次研究请求。系统只登记，不执行任何真实交易。

## 执行流程

1. 从 `$ARGUMENTS` 解析 `action`（buy/sell）、`quantity`、`price`、`date`。
2. `$ARGUMENTS` 为空或缺字段时，用 `AskUserQuestion` 逐项补问（买卖方向、数量、价格、日期），不要只回一句「请按格式输入」。
3. 调用控制器 `record_trade`（stdin 传 JSON，路径固定）：

```bash
CONTROLLER="${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/pypl/scripts/pypl.py"
python3 "$CONTROLLER" record_trade << 'EOF'
{ "symbol": "PYPL", "action": "buy", "quantity": 100, "price": 65.5, "date": "2026-11-10" }
EOF
```

4. 调用 `start` skill 的 Orchestrator 主流程，触发 `trade` 请求。
