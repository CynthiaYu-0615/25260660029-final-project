# 数据来源与取法

本文件约定 gen-data 专项允许使用的数据来源、具体取法、备选方案、失败处理和 as-of 规则。

## 当前会话可用工具

经过实测，当前 Kimi Code 会话中可见的取完工具有：

- `Read`：读取本地文件。
- `FetchURL`：抓取公开网页。
- `Bash`：执行 `curl` 等命令行工具。
- `mcp__plugin-kimi-datasource_data__get_data_source_desc`
- `mcp__plugin-kimi-datasource_data__call_data_source_tool`

其中 MCP 工具属于 `kimi-datasource` 插件；安装后需要重新加载会话（`/new` 或 `/reload`）才能在该会话使用，否则调用不到。在插件不可用或额度耗尽时，降级到 `FetchURL` / `Bash`。

## 数据类别与取法

### 1. 财报核心数字（收入、净利润、EPS、指引）

**首选来源**：SEC EDGAR 10-Q / 10-K
- 主页：https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001633917
- 取法：
  1. 用 `curl` + `User-Agent` 访问 `https://data.sec.gov/submissions/CIK0001633917.json` 拿到最近申报列表。
  2. 筛选 `form` 为 `10-Q` 或 `10-K` 的条目，获取 `accessionNumber` 和 `primaryDocument`。
  3. 构造 `https://www.sec.gov/Archives/edgar/data/1633917/{accession}/{primaryDocument}`，抓取 HTML。
  4. 用 Python 标准库解析 HTML，搜索 "Total net revenues"、"Net income"、"Diluted earnings per share" 等关键字。
- as-of：SEC 申报中的 period end date；数据获取时间为当前时间。
- **已知失败情况**：SEC 对未声明的自动化工具有限制，可能返回 "Your Request Originates from an Undeclared Automated Tool"。解决方式：在 `User-Agent` 中声明项目邮箱，并控制访问频率。
- **备选**：`kimi-datasource` 的 `sec_edgar` 数据源（需要新会话）。

### 2. 财报发布日期

**首选来源**：SEC EDGAR 申报列表
- 取法：同 1，查看 `filingDate` 字段即可。
- **已知失败情况**：下一次财报日期不在 SEC 历史文件中；只能根据历史发布节奏推断。
- **备选**：`kimi-datasource` 的 `stock_finance_data` / `yahoo_finance`。

### 3. 8-K 标题和日期

**首选来源**：SEC EDGAR 申报列表
- 取法：筛选 `form` 为 `8-K` 的条目，读取 `filingDate` 和 `primaryDocument`。
- **已知失败情况**：8-K HTML 内容抓取容易被 SEC 拦截；标题通常只能从申报索引页或 8-K 文本中解析。
- **备选**：`kimi-datasource` 的 `sec_edgar`。

### 4. 当前股价和近期涨跌

**首选来源**：Yahoo Finance / Nasdaq / 券商公开行情
- 取法：
  - Yahoo Finance API：`https://query1.finance.yahoo.com/v8/finance/chart/PYPL?interval=1d&range=1mo`
  - Nasdaq API：`https://api.nasdaq.com/api/quote/PYPL/info?assetClass=stocks`
- **已知失败情况**：Yahoo Finance API 和 Nasdaq API 对无 Cookie/Token 的请求返回空或 403；公开行情页面（如 stockanalysis.com）价格由 JavaScript 渲染，无法直接解析。
- **备选**：`kimi-datasource` 的 `stock_finance_data` 或 `yahoo_finance`。
- **降级**：若无法获取，在报告中明确标注「股价数据暂不可获得」，使用录制样例时需标注「使用录制数据」。

### 5. 最近新闻标题

**首选来源**：财经新闻聚合页面
- 取法：
  - `stockanalysis.com/stocks/pypl` 的新闻区段落文本。
  - 未来可尝试 `kimi-datasource` 的 `xhcj`、`cls` 或通用新闻源。
- **已知失败情况**：Google News RSS 对程序化访问有限制；通用搜索结果页多为 JavaScript 重定向，难以解析。
- **备选**：`kimi-datasource` 的新闻类数据源。

## as-of 规则

1. 每条数据必须记录：数值、来源 URL、获取时间（ISO 8601）、原始 as-of（若有）。
2. 财报数据 as-of 为财报截止日期（如 2026-09-30）。
3. 股价/新闻 as-of 为获取时间。
4. 超过请求 as-of 的数据一律不使用。
5. 若使用 `examples/input/` 中录制的样例，报告必须明确标注「使用录制数据」及录制时间。

## 额度与调用限制

- `kimi-datasource` 每次调用消耗额度，单个会话中累计调用不超过 20 次。
- 对 SEC 的请求间隔不小于 1 秒，避免触发速率限制。
- 优先使用本地录制样例做回归测试，只有真实生成报告时才调用外部数据源。
