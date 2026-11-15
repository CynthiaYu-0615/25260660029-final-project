# 重大新闻判断规则

本文件约定 `/pypl:ping` 和 `gen-data` 在搜索 PYPL 新闻时，如何判断一条新闻是否属于「重大事件」并触发生成报告。

## 重大事件类别与判断依据

### 1. 裁员

- **判断依据**：公司宣布大规模裁员、团队缩编、人员优化、restructuring。
- **关键词**：layoff、cut jobs、workforce reduction、restructuring、eliminate positions、reduce headcount
- **触发门槛**：单次裁员超过 100 人或超过员工总数 5%（若数据可获得）。
- **示例**："PayPal to lay off 500 employees" → 触发。

### 2. 收购 / 并购

- **判断依据**：PYPL 作为买方或卖方，宣布收购、合并、被收购。
- **关键词**：acquire、acquisition、merger、takeover、buyout、to buy、to be acquired
- **触发门槛**：任何涉及 PYPL 的收购或并购公告。
- **示例**："PayPal acquires fintech startup for $500M" → 触发。

### 3. 拆分 / 业务剥离

- **判断依据**：公司宣布将某个业务单元拆分、剥离、出售。
- **关键词**：spin-off、divestiture、split、separate、sell off、business unit sale
- **触发门槛**：任何涉及 PYPL 核心业务或子品牌的拆分/剥离公告。
- **示例**："PayPal to spin off Venmo into standalone entity" → 触发。

### 4. 高管变动（CXO / 董事会）

- **判断依据**：CEO、CFO、CTO、COO、President、董事会成员等核心高管变动。
- **关键词**：appointed as CEO、steps down、resigns、new CFO、board member、chief executive、chief financial officer
- **触发门槛**：CXO 级别或董事会主席变动。
- **示例**："PayPal CEO steps down" → 触发；"PayPal hires VP of engineering" → 不触发。

### 5. 监管 / 诉讼重大进展

- **判断依据**：针对 PYPL 的重大反垄断调查、集体诉讼、SEC 调查、罚款。
- **关键词**：SEC investigation、antitrust、class action lawsuit、settlement、fine、regulatory probe
- **触发门槛**：可能导致重大财务影响或业务限制的公告。
- **示例**："PayPal faces $1B antitrust fine" → 触发。

### 6. 重大战略合作 / 产品战略转向

- **判断依据**：影响公司长期收入结构的战略合作、重大产品发布或业务退出。
- **关键词**：strategic partnership、exclusive deal、exit from、shut down、discontinue
- **触发门槛**：影响核心业务或年度收入 5% 以上。

## 不算重大事件

以下新闻**不**触发生成报告，但可纳入证据包：

- 日常股价波动、分析师评级上调/下调。
- 非 CXO 级别的人事变动。
- 常规产品功能更新（如 Venmo 新增 receipt scanning）。
- 市场营销活动、品牌合作。
- 未经验证的小道消息、 rumor 。

## 来源可信度要求

- **可信来源**：Reuters、Bloomberg、CNBC、Wall Street Journal、PayPal IR 官方、SEC 文件、Yahoo Finance、MarketWatch。
- **次级来源**：TipRanks、Seeking Alpha、Benzinga、PYMNTS（可作为补充，需交叉验证）。
- **不可信来源**：匿名论坛、未经验证的社交媒体账号。

## 同一事件去重

1. 用事件标题中的公司名 + 事件类型 + 日期作为去重 key。
2. 同一事件在 7 天内只触发一次。
3. 事件记录到 `.pypl/events.json` 的 `news_events` 列表中，状态为 `pending`、`triggered` 或 `done`。
4. 避免因为不同媒体转载同一事件而重复触发。

## 触发流程

1. `/pypl:ping` 搜索新闻，提取标题、日期、来源。
2. 按上述类别和关键词匹配。
3. 对可信来源的新闻，按去重规则判断是否已触发。
4. 满足条件时，触发 `start` skill 生成报告。
