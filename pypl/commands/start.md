---
description: 手动触发生成一份 PYPL 研究报告。
---

# /pypl:start

## 作用

用户手动要求立即生成一份 PYPL 研究报告。

## 执行流程

1. 若 `$ARGUMENTS` 为空，用 `AskUserQuestion` 向用户确认现在生成（可附带 `--as-of <ISO时间>` 指定信息截止时点，缺省为当前时间）；不要只回一句「请按格式输入」。
2. 调用 `start` skill 的 Orchestrator 主流程，触发 `manual` 请求，按完整流水线执行：新建请求 → `fetch_sec` 取财报数字 → 派 Generator → 落盘核对 → Gate → Critic → 最多 3 轮修订 → 连续两轮通过后请用户批准归档。

控制器调用方式与 `start` skill 一致（stdin 传 JSON）：

```bash
CONTROLLER="${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/pypl/scripts/pypl.py"
python3 "$CONTROLLER" new_request << 'EOF'
{ "trigger": "manual", "as_of": "2026-11-15T09:00:00+08:00" }
EOF
```
