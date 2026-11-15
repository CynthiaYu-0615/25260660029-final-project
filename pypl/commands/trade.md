---
description: 登记 PYPL 持仓变化，包括买入或卖出的数量与价格；系统仅登记，不执行真实交易。
---

# /pypl:trade

## 作用

用户报告自己买入或卖出了 PYPL，系统将数量和价格登记到 `.pypl/holdings.json`，并触发一次研究请求。

## 执行流程

1. 解析 `$ARGUMENTS` 中的 `action`、`quantity`、`price`、`date`。
2. 调用控制器：
   - `pypl/scripts/pypl.py record_trade --action <buy|sell> --quantity <n> --price <p> --date <date>`
3. 调用 `start` skill 的 Orchestrator 主流程，触发 `trade` 请求。
