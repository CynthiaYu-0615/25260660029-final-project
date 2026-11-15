---
description: 系统演进命令：对照固定基线用确定性脚本评估关卡规则改动，由用户批准采纳、拒绝或回滚；不直接触发生产报告。
---

# /pypl:evo

## 作用

用户想改进 PYPL 插件的关卡规则（`pypl/references/gate_rules.json`）时，运行 evo 流程。系统在固定基线样例（`evals/baseline/`）上用真实的 `gate_report` 做 A/B 对比，按 `pypl/references/evo_policy.md` 的阈值给出采纳/拒绝建议，由用户批准后执行，记录版本并可回滚。

## 执行流程

1. 从 `$ARGUMENTS` 接收改动说明（改哪条规则、怎么改）；为空时用 `AskUserQuestion` 向用户补问，不要只回一句「请按格式输入」。
2. 按 `skills/evo/SKILL.md` 的确定性流程调用 `pypl/scripts/evo.py`：
   - `run` 跑基线；`compare` 对比新旧规则（误拦率不得高于基线、召回率必须提高）；
   - 建议采纳时经 `AskUserQuestion` 确认后 `approve`（写 `evals/approvals.json`）再 `adopt`（更新规则 + CHANGELOG + git tag）；
   - 不满足阈值时 `reject` 记录拒绝原因；需要时 `rollback --to <tag>` 回滚并用 fingerprint 验证基线指标一致。
3. 把对比报告路径（如 `evals/ab-001.md`）和决定告知用户。

## 局限（如实告知用户）

当前只对 gate 规则做确定性评估；提示词改动的「完整 LLM 流程前后对比」是未来工作，尚未实现。
