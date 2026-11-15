---
name: critic
description: Critic 负责人，协调 critic-evidence、critic-robustness、critic-risk 三个专项，完成评估、合并与覆盖检查。
tools:
  - Agent
subagents:
  - critic-evidence
  - critic-robustness
  - critic-risk
---

# critic

Critic 负责人，协调并整合三个评估专项的反馈。
