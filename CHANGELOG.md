# CHANGELOG

PYPL 插件的版本记录。每次采纳（adopted）、拒绝（rejected）、回滚（rollback）由 `pypl/scripts/evo.py` 追加一条，包含版本号、日期、改动、指标、决定和批准人；规则版本同时用 git tag 标记，可 `git show <tag>:pypl/references/gate_rules.json` 查看对应内容。

## v0.1-baseline — 初始基线

- 日期：2026-11-15
- 改动：把 gate 写死的规则抽成 `pypl/references/gate_rules.json`（违禁词：买入/卖出/下单；数值容差 0.005；最少理由 3 条），版本 v0.1-baseline
- 指标：基线集 12 份样例，召回率 0.70，误拦率 0.00（case-08/09/10 的加仓/清仓/抄底漏放）
- 决定：初始版本（git tag v0.1-baseline）
