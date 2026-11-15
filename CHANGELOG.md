# CHANGELOG

PYPL 插件的版本记录。每次采纳（adopted）、拒绝（rejected）、回滚（rollback）由 `pypl/scripts/evo.py` 追加一条，包含版本号、日期、改动、指标、决定和批准人；规则版本同时用 git tag 标记，可 `git show <tag>:pypl/references/gate_rules.json` 查看对应内容。

## v0.1-baseline — 初始基线

- 日期：2026-11-15
- 改动：把 gate 写死的规则抽成 `pypl/references/gate_rules.json`（违禁词：买入/卖出/下单；数值容差 0.005；最少理由 3 条），版本 v0.1-baseline
- 指标：基线集 12 份样例，召回率 0.70，误拦率 0.00（case-08/09/10 的加仓/清仓/抄底漏放）
- 决定：初始版本（git tag v0.1-baseline）

## v0.2 — adopted

- 日期：2026-11-15
- 改动：违禁词增加：加仓、抄底、清仓（v0.1-baseline → v0.2）
- 指标：召回率 0.70 → 1.00，误拦率 0.00 → 0.00
- 决定：采纳（批准人 于欣荷，候选 sha256 8711905c0b94…，记录于 evals/approvals.json）

## v0.3 — rejected

- 日期：2026-11-15
- 决定：拒绝（未写入门户规则）
- 理由：数值容差放宽到 5% 导致 case-04（EPS 偏差 1.6%）漏放，召回率 1.00→0.90，违反 min_recall_gain；误拦率虽未升但不足以采纳

## v0.1-baseline — rollback（自 v0.1-baseline 恢复）

- 日期：2026-11-15
- 改动：gate_rules.json 恢复到 v0.1-baseline 对应内容（版本 v0.1-baseline）
- 指标：召回率 0.70，误拦率 0.00，fingerprint 477a7d40fab3…
- 决定：回滚（由演示/用户发起）

## v0.2 — rollback（自 v0.2 恢复）

- 日期：2026-11-15
- 改动：gate_rules.json 恢复到 v0.2 对应内容（版本 v0.2）
- 指标：召回率 1.00，误拦率 0.00，fingerprint 3b3bd951035a…
- 决定：回滚（由演示/用户发起）
