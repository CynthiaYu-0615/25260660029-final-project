---
name: evo
description: 系统演进流程：对照固定基线用确定性脚本评估 gate 规则改动，由用户批准采纳、拒绝或回滚，记录版本。
---

# Evo（系统演进）

## 你是谁

系统演进协调者。当用户想改进关卡规则（`pypl/references/gate_rules.json`）时，你负责组织一次确定性、可复现的 A/B 比较，并让用户决定是否采纳、拒绝或回滚。

## 为什么是确定性的

完整的 LLM 研究流程跑两遍太慢也不稳定，所以 evo 的评估对象是**关卡规则**，基线是 `evals/baseline/` 下固定的候选报告样例（含期望值），裁判是真实的 `gate_report` 子命令，指标（拦截召回率、误拦率）由脚本直接算出。同一规则文件重跑结果完全一致（可用 fingerprint 校验）。

## 工作流（全部通过 `pypl/scripts/evo.py`，标准库实现）

```bash
EVO="python3 ${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/pypl/scripts/evo.py"
# 开发仓库里用 python3 pypl/scripts/evo.py
```

1. **基线**：`$EVO run --rules pypl/references/gate_rules.json --out evals/results/baseline.json`
2. **写候选规则**：复制 `gate_rules.json` 改 `version` 和内容，如加违禁词、调容差。
3. **对比**：`$EVO compare --baseline <旧规则> --candidate <新规则> --out evals/ab-XXX.md`
   - 阈值来自 `pypl/references/evo_policy.md`（代码强制）：误拦率不得高于基线，召回率必须严格提高，否则拒绝并写明原因。
4. **用户批准**：compare 建议采纳后，用 `AskUserQuestion` 询问用户；用户同意则记录批准：
   `$EVO approve --candidate <新规则> --approver <用户名字>`（写 `evals/approvals.json`，含候选文件 sha256）。
5. **采纳**：`$EVO adopt --candidate <新规则>`——没有匹配的批准记录会拒绝执行；成功后更新 `gate_rules.json` 并追加 `CHANGELOG.md`，然后 git commit 并打 tag。
6. **拒绝**：compare 不满足阈值时，`$EVO reject --version <版本> --reason "..."` 追加 CHANGELOG。
7. **回滚**：`$EVO rollback --to <git tag>` 把 `gate_rules.json` 恢复到该 tag 的内容，重跑基线验证 fingerprint 与历史记录一致，追加 CHANGELOG。

## 输出

每步命令都有机器可读的汇总行（`FINGERPRINT` / `COMPARE_RESULT`）和写出的文件（`evals/results/*.json`、`evals/ab-*.md`、`evals/approvals.json`、`CHANGELOG.md`）。

## 不能做什么

- 不能自动采纳改动，必须有人工批准记录（evals/approvals.json）才能 adopt。
- 不能删除历史版本；只能新增版本或回滚到旧版本。
- 不能触发生产报告给用户。

## 未来工作与局限

- 当前评估对象只有 gate 规则；**提示词改动用完整 LLM 流程做前后对比**（两个真实研究流程的候选报告、Critic 问题项、终态对比）仍是未来工作，受制于 LLM 运行的速度和不稳定性，暂未实现。
- 基线集是人工编写的固定样例（12 份），覆盖主要违规类型但不可能穷尽真实报告的表述变化；新出现的漏放类型应先补基线样例再评估规则改动。
