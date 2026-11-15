# 回滚演示：v0.2 → v0.1-baseline → v0.2

演练时间：2026-11-15。命令均为 `python3 pypl/scripts/evo.py …`。

## 步骤与结果

1. **采纳态**：`gate_rules.json` 为 v0.2（git tag `v0.2`，见 CHANGELOG「v0.2 — adopted」）。
2. **回滚**：`evo.py rollback --to v0.1-baseline` —— 从 git tag 读取规则内容写回 `gate_rules.json`，当前版本变为 v0.1-baseline。
3. **重跑基线验证**：`evo.py run --rules pypl/references/gate_rules.json --out evals/results/rollback-check.json`。
4. **一致性对比**：

| 项目 | 首次基线（evals/results/baseline.json） | 回滚后重跑（evals/results/rollback-check.json） |
| --- | --- | --- |
| fingerprint | `477a7d40fab36631f9dddc08fa3349e45a892b1642d65326db730718a2b025e7` | `477a7d40fab36631f9dddc08fa3349e45a892b1642d65326db730718a2b025e7` |
| 召回率 | 0.70 | 0.70 |
| 误拦率 | 0.00 | 0.00 |
| metrics 全等 | — | True |

结论：回滚后的规则与首次基线**逐份结果与指标完全一致**（fingerprint 相等），证明 rollback 恢复的是 tag 对应的确定内容，而非近似。

5. **恢复采纳版**：`evo.py rollback --to v0.2`，`gate_rules.json` 恢复为 v0.2（CHANGELOG 已记录回滚与恢复两条）。当前版本以 `pypl/references/gate_rules.json` 的 `version` 字段和 CHANGELOG 最后一条 adopted 记录为准。
