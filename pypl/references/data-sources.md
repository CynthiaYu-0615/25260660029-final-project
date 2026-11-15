# 数据来源与取法

本文件约定 gen-data 专项允许使用的数据来源、具体取法、备选方案、失败处理和 as-of 规则。
本章所有数据源名与 API 名均以 2026-11-15（本会话第 13 条）通过 `mcp__plugin-kimi-datasource_data__get_data_source_desc` / `call_data_source_tool` 实测返回为准，未实测验证过的一律不写入。

## 当前会话可用工具

经过实测，当前 Kimi Code 会话中可见的取数相关工具有：

- `Read`：读取本地文件。
- `FetchURL`：抓取公开网页。
- `Bash`：执行 `curl` 等命令行工具。
- `mcp__plugin-kimi-datasource_data__get_data_source_desc`
- `mcp__plugin-kimi-datasource_data__call_data_source_tool`

其中 MCP 工具属于 `kimi-datasource` 插件；安装后需要重新加载会话（`/new` 或 `/reload`）才能在该会话使用，否则调用不到。在插件不可用或额度耗尽时，降级到 `FetchURL` / `Bash`。

## 已实测验证的数据源（2026-11-15）

以下 6 个数据源名均通过 `get_data_source_desc` 实测返回确认存在（带 ★ 的还完成了真实取数）：

| 数据源 | desc 实测 | 真实取数实测 | 已确认可用的 API |
| --- | --- | --- | --- |
| `yahoo_finance` ★ | 成功 | 成功（新闻接口失败，见下） | `get_stock_info`、`get_historical_stock_prices`、`get_yahoo_finance_news`、`get_financial_statement`、`get_recommendations`、`get_option_expiration_dates`、`get_option_chain`、`get_stock_actions`、`get_holder_info` |
| `sec_edgar` ★ | 成功 | 成功 | `sec_edgar_get_company_info`、`sec_edgar_get_financial_statements`、`sec_edgar_get_xbrl_facts`、`sec_edgar_get_filings`、`sec_edgar_get_insider_trades`、`sec_edgar_get_institutional_holdings`、`sec_edgar_get_company_events` |
| `xhcj`（新华财经）★ | 成功 | 成功（但无 30 天内结果） | `get_newsflash_foreign_currency`、`search_prodinfo`、`get_newsflash_stock`、`get_AStock_News_byStockName`、`get-las-vector`、`xhcj-mcp-announce-search`、`search_prodinfo_stockSector_news`、`get_xhcj_hotNews`、`get_newsflash_Commodities` |
| `dongcai`（东方财富妙想）★ | 成功 | 成功 | `dongcai_mx_finance_data`、`dongcai_mx_finance_search`、`dongcai_mx_financial_assistant` 等 30 个（以 desc 返回为准） |
| `stock_finance_data` | 成功 | 未实测取数 | `stock_finance_data_get_stock_info`、`stock_finance_data_get_price`、`stock_finance_data_get_stock_realtime_price`、`stock_finance_data_get_financial_statements`、`stock_finance_data_get_stock_financial_index`、`stock_finance_data_get_stock_business_segmentation`、`stock_finance_data_get_holder_info`、`stock_finance_data_get_stock_announcement`（仅 A 股）、`stock_finance_data_get_forecast`（仅 A 股） |
| `cls`（财联社） | 成功 | 未实测取数 | `cls_telegraphs`、`cls_depth_news` |

注意：

- 美股代码格式各源不同：`yahoo_finance` / `sec_edgar` 用 `PYPL`；`stock_finance_data` 用 `PYPL.O`；`stock_finance_data_get_stock_realtime_price` 用 `PYPL.US`。
- `yahoo_finance` 与 `stock_finance_data` 的历史行情最长 2 年 / 3 年，足够覆盖 30 天窗口。
- `sec_edgar` 内部从数据库提供数据，不含未来财报日期。

## 数据类别与取法

### 1. 财报核心数字（收入、净利润、EPS、指引）

**首选来源**：`kimi-datasource` 的 `sec_edgar` ★ 已实测
- `sec_edgar_get_financial_statements`：按 10-K/10-Q 取完整报表（ticker=PYPL）。
- `sec_edgar_get_xbrl_facts`：按关键字取多年单指标时间序列（keyword 支持 revenue、netincome、eps 等）。
- 原始页面：https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001633917
- **降级**：`Bash` + `curl` 访问 `https://data.sec.gov/submissions/CIK0001633917.json` 拿申报列表，再解析 10-Q/10-K HTML；SEC 对未声明的自动化工具有拦截风险，需在 `User-Agent` 声明项目邮箱并控制频率。
- as-of：财报 period end date；数据获取时间为当前时间。

### 2. 财报发布日期 / 下一次财报日期

**首选来源**：`sec_edgar` ★ 已实测（只能看到已发生申报的 filing date）
- `sec_edgar_get_filings`（ticker=PYPL，可筛 form_type）返回 filing_date、report_date、accession、sec_url。
- **实测结论：下一次财报日期取不到官方值**——SEC 只存历史申报；`yahoo_finance` 的 `get_stock_info` 中 earningsTimestamp 字段实测指向已过去的 2026-10-27（上一次 Q3 财报）；`dongcai_mx_finance_data` 实测两次查询（"下一次财报发布日期"、"四季度及全年财报预计什么时候披露"）都只返回历史披露日期表（2026-02-03 / 2026-05-05 / 2026-07-28 / 2026-10-27）。
- 只能按历史节奏推断（Q4/全年报在 2 月初，推断约 2027-02-02），引用时必须标注「推断」，不得当作实测值。

### 3. 8-K 事项和日期

**首选来源**：`sec_edgar` ★ 已实测
- `sec_edgar_get_filings`（ticker=PYPL，form_type=8-K）返回申报列表：accession、filing_date、sec_url，但**不含标题**。
- `sec_edgar_get_company_events`（ticker=PYPL，start_date/end_date）返回每条 8-K 的 Item 编号和事项描述（如 "2.02 Results of Operations and Financial Condition"），这是最接近「标题」的字段。
- **实测**：最近一份 8-K 为 2026-10-27（accession 0001633917-26-000086，Q3 2026 业绩，Item 2.02 + 9.01）。调用 2 次（filings + company_events），均成功。

### 4. 当前股价和近期涨跌

**首选来源**：`yahoo_finance` ★ 已实测
- `get_stock_info`（ticker=PYPL）：currentPrice、previousClose、52 周高低等。
- `get_historical_stock_prices`（ticker=PYPL，period 最长 2y，interval=1d）：日线收盘价序列，自行计算区间涨跌。
- **实测**：2026-11-13 收盘 59.28 USD；30 天前（2026-10-14）收盘 56.10，区间 +3.18（+5.67%）。调用 2 次，均成功。
- **备选**：`stock_finance_data_get_price` / `stock_finance_data_get_stock_realtime_price`（美股用 PYPL.US，realtime_price 支持美股；desc 已验证存在，取数未实测）。
- **降级**：`FetchURL` 公开行情页面；仍失败则在报告中标注「股价数据暂不可获得」，使用录制样例时标注「使用录制数据」。

### 5. 最近新闻（带日期和来源）

**首选来源**：`yahoo_finance` 的 `get_yahoo_finance_news`（ticker=PYPL）——**本次实测失败**（接口返回 "YAHOO! FINANCE IS CURRENTLY DOWN!"，属上游故障，可稍后重试）。
**已实测可用的替代**：
- `dongcai` 的 `dongcai_mx_finance_search` ★：query="PayPal 最新消息"，返回带 date、source、jumpUrl 的资讯列表（本次 30 天窗口内取得 7 条：财联社评级快讯 4 条、21 世纪经济报道专访 1 条、智通财经 Q3 财报报道 1 条、《商学院》杂志 1 条；部分条目无原文 URL）。调用 1 次，成功。
- `xhcj` 的 `search_prodinfo` ★：query 用 contentTxt="PayPal"，调用成功但按相关度返回的多为旧闻（本次命中条目均为 2026-02 至 2026-07，30 天窗口内无结果），不适合作为近期新闻主源。
- `cls` 的 `cls_telegraphs` / `cls_depth_news`：desc 已验证存在，取数未实测；快讯可按 Unix 时间戳范围分页。
- **降级**：`FetchURL` 财经新闻聚合页（如 stockanalysis.com/stocks/pypl 新闻区）。

## 2026-11-15 第 3 步实测结果汇总

针对 PYPL 四项需求，Datasource 调用情况（`call_data_source_tool` 共 9 次，另加 `get_data_source_desc` 6 次）：

| 数据项 | 结果 | 成功次数/调用次数 | 数据源与 API |
| --- | --- | --- | --- |
| 当前股价 + 近 30 天涨跌 | 成功 | 2/2 | yahoo_finance get_stock_info、get_historical_stock_prices |
| 最近 30 天新闻（日期+来源） | 部分成功 | 2/3 个来源成功（yahoo_finance 失败 1 次） | yahoo_finance get_yahoo_finance_news 失败；xhcj search_prodinfo 成功但无窗口内结果；dongcai_mx_finance_search 成功取得 7 条 |
| 下一次财报日期 | 未取到官方值 | 0/2（yahoo_finance 1 次 + dongcai 2 次均只给历史日期） | 只能推断，报告中必须标注「推断」 |
| 最近一份 8-K 标题（事项） | 成功 | 2/2 | sec_edgar_get_filings、sec_edgar_get_company_events |

## as-of 规则

1. 每条数据必须记录：数值、来源 URL、获取时间（ISO 8601）、原始 as-of（若有）。
2. 财报数据 as-of 为财报截止日期（如 2026-09-30）。
3. 股价/新闻 as-of 为获取时间。
4. 超过请求 as-of 的数据一律不使用。
5. 若使用 `examples/input/` 中录制的样例，报告必须明确标注「使用录制数据」及录制时间；推断值（如下一次财报日期）必须与实测值明确区分。

## 额度与调用限制

- `kimi-datasource` 每次调用消耗额度，单个会话中累计调用不超过 20 次（本次会话已用 15 次：desc 6 次 + 取数 9 次）。
- 对 SEC 的请求间隔不小于 1 秒，避免触发速率限制。
- 优先使用本地录制样例做回归测试，只有真实生成报告时才调用外部数据源。
