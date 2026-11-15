---
description: 手动触发生成一份 PYPL 研究报告。
---

# /pypl:start

## 作用

用户手动要求立即生成一份 PYPL 研究报告。

## 执行流程

1. 调用 `start` skill 的 Orchestrator 主流程。
2. 使用 `$ARGUMENTS` 接收可选参数：
   - `--as-of`：信息截止时点，默认为当前时间。
3. 触发 `manual` 请求，按完整流水线生成报告。
