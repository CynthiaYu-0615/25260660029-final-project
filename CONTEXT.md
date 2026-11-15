## 第 1 条 · 2026-11-15 17:35:14
~~~~
update agents.md

content
这个仓库是 《金融人工智能编程》期末作业
提交人：于欣荷
学号：25260660029

github repo needs commit and push frequently, you can decide when to commit and add file and commit and push accordingly without the needs of asking permission.

i will use either chinese or english with you but you need to response in chinese,
and use chinese in agents md and other skills, prompts, and code comments.
~~~~

## 第 2 条 · 2026-11-15 17:36:24
~~~~
continue update @AGENTS.md 

about github, 

all commits shall be made on behalf of 
git config user.name "于欣荷"
git config user.email "cynthiayu615@gmail.com"
~~~~

## 第 3 条 · 2026-11-15 17:38:47
~~~~
copy /Users/guchen/Documents/notes/02-projects/wife/attachments/20261107-金融AI长程智能体工作流/作业要求.pdf into assets/ folder of this repo and refer it in agents saying this is 作业要求

and make a README.md saying briefly about this repo (only necessary info for human reviewer) and say details goes to @AGENTS.md
~~~~

## 第 4 条 · 2026-11-15 17:50:05
~~~~
我们要做一个 Kimi Code 插件,叫 pypl,用来持续研究美股 PayPal(PYPL)。这是《金融人工智能编程》的期末作业,要把课上讲的「完整架构」做出来:Orchestrator、Generator、Critic 三个角色。我负责管理整个系统,具体的活由 agent 干。系统只做研究,不会买卖任何东西。

先看一下 AGENTS.md 和 assets/作业要求.pdf,了解一下约定和作业要求。

插件本身放在仓库的 pypl/ 子目录里,仓库根目录留给作业的其他材料(设计文档、示例、证据、README)。先只把骨架搭起来,结构是这样:

pypl/
  kimi.plugin.json          # commands, skills, agents
  commands/{start,trade,evo}.md
  skills/{start,evo}/       # Orchestrator 工作流
  agents/                   # 两个负责人 + 六个专项
  references/               # schema、角色卡、规则
  runtime/pypl/             # 状态机和数值关卡
  scripts/{pypl,check}.py   # 控制器动作和测试入口
  tests/                    # 测试数据和回归测试
design/                     # 任务定义、设计说明、工作流图
examples/                   # 示例输入输出
evidence/                   # 运行、核验、恢复的证据

只建目录、manifest 和占位文件就行,先不要写具体逻辑,后面我一步步跟你讲。

占位文件也要符合 Kimi Code 插件的格式,保证 /plugins install pypl 之后能被正常加载,不能报错:command 和 agent 文件要有 frontmatter(agent 要有 name 和 description,command 要有 description),skill 目录里要放带 name 和 description 的 SKILL.md,manifest 里把 commands、skills、agents 的路径都声明好。其他文件每个写一行中文注释说明用途就行。

README.md 和 AGENTS.md 已经有了,别覆盖。
~~~~

## 第 5 条 · 2026-11-15 17:53:51
~~~~
我装了一下这个插件,/plugins info pypl 报错了:kimi.plugin.json 里 skills、agents、commands 的路径必须以 ./ 开头,现在 skills 是 0 个,agents 全是 error,commands 是 warn。先把这个修掉,建议直接写目录:"commands": "./commands/"、"skills": "./skills/"、"agents": "./agents/"。

agent 文件的 name 也要用小写加连字符(kebab-case),现在 Analyst 这种写法会被跳过。

另外角色要和课上的完整架构对上,现在多了几个对不上的。请这样调整:

- Orchestrator 是主 agent,不是子 agent。把 agents/orchestrator.md 删掉,它的职责放在 skills/start 里,用 sessionStart 在会话开始时注入。
- agents/ 里只留两个负责人和六个专项:
  - generator(Generator 负责人,协调下面三个专项,做整合和测试)
  - gen-data(取数)、gen-fundamentals(财务指标和关键驱动)、gen-valuation(估值与情景)
  - critic(Critic 负责人,协调下面三个专项,做合并和覆盖检查)
  - critic-evidence(数据与证据)、critic-robustness(稳健性)、critic-risk(风险与控制,也负责检查有没有越界给买卖建议)
- 把 researcher、analyst、writer、reviewer、verifier 这五个文件删掉。
- 两个负责人的 frontmatter 要写 tools 里带 Agent,再加 subagents 列出各自的三个专项,不然它们没法派活。
- 六个专项的 tools 先只给 Read,不要给 Write 和 Bash。

这一步还是只改骨架和 frontmatter,不写具体内容。
~~~~

## 第 6 条 · 2026-11-15 17:58:44
~~~~
接下来讲一下这个插件到底给用户做什么。用户只有四类操作:

1. 登记持仓变化:我买入或卖出了 PYPL,告诉系统数量和价格。系统只是登记,不会真的交易。命令 /pypl:trade。
2. 要求生成报告:手动让系统现在跑一次研究。命令 /pypl:start。
3. 登记财报日期:我告诉系统下一次财报哪天发,系统自动登记两个事件:财报前两天、财报发布后。命令 /pypl:event。
4. 每日检查:每天跑一次,看今天有没有到登记的事件日;同时搜一下 PYPL 的新闻,如果有重大事件(裁员、收购、并购、拆分、换 CXO 这类)就触发生成。命令 /pypl:ping。

Kimi Code 自己没有定时器,所以「每日」就是我每天(演示时手动)运行一次 /pypl:ping,不是后台自动跑,这点要在文档里如实写清楚。

触发生成报告的情况一共五种:财报前两天、财报发布后、每日检查发现重大新闻、登记了持仓变化、上一版被 Critic 打回要修。

每份报告必须有明确结论:增持、减持、还是持有不动,并写出理由,以及对我当前持仓意味着什么。这只是研究观点,不执行任何买卖。报告写完之后必须经过 Critic 验证才算数。

持仓变化由控制器脚本写进 .pypl/holdings.json,Generator 生成报告时去读,不自己改。

请你做这几件事:
- 改 pypl/commands/:留 start、trade、event、ping、evo 五个文件,frontmatter 里的 description 按上面写准确,正文先只写一两句话。
- 在 kimi.plugin.json 里加 "sessionStart": {"skill": "start"},并把 skills/start/SKILL.md frontmatter 里那个 sessionStart: true 去掉。
- 写 design/task.md:任务描述、目标用户(持有 PYPL 的个人投资者)、现在人是怎么做的、各个阶段和依赖、上面这五种触发条件、允许使用的资料来源和信息截止时点(as-of)规则、产出和验收标准(要能逐条判定通过或不通过)、为什么需要持久化的工作流而不是一次性脚本。

先不要写 agent 的细节和脚本。
~~~~

## 第 7 条 · 2026-11-15 18:04:07
~~~~
我想把我在这个项目里每一次发给你的话都记下来,方便以后回看我是怎么一步步指挥你做这个作业的。请这样做:

1. 在 AGENTS.md 的「开发约定」里加一条规则:以后在这个仓库里的每一个 Kimi session,每次我发来消息,你都要先把我这条消息原文追加到仓库根目录的 CONTEXT.md 末尾,再去做其他事。只记我的输入,不记你的回复;原文不要改;只能往后追加,不能改或删以前的记录。每条格式:

## 第 N 条 · 日期 时间
(我的原文)

N 从 1 递增。新 session 第一次回复前,先读一下 CONTEXT.md 最后一条的编号再接着记。

2. 到目前为止我发给你的所有消息,请你自己从会话记录里找出来补录进 CONTEXT.md,按时间顺序,时间写「补录」。你可以看当前对话,也可以去 ~/.kimi-code/sessions 里这个项目对应的目录里找(目录名带 25260660029-final-project)。只要我发的消息,不要你自己的回复和工具输出。

3. 我这条消息也要记,作为最后一条。

做完后告诉我 CONTEXT.md 一共记了几条,列出每条的编号和第一行就行。其他文件不要动。
~~~~

## 第 8 条 · 2026-11-15 18:05:56
~~~~
接下来把角色之间的契约和规则定下来，对应课上讲的「角色契约」「契约与边界」「停止与恢复」「验收」几页。先改两处概念：

1. /pypl:evo 不是 Critic 打回后的修订循环。修订循环是 Orchestrator 内部做的：Critic 返回问题项，Orchestrator 出修复任务包发回 Generator，有最大轮数。/pypl:evo 是系统演进：我想改提示词或规则时，对着固定的基线样例比较改动前后的效果，决定采纳还是拒绝，批准权在我，改动要有版本号、能回滚。请相应改 design/task.md（触发条件 5 和阶段说明）和 pypl/commands/evo.md 的描述。
2. design/task.md 的验收标准改成：同一候选报告连续两轮 Critic 全部通过、且没有未解决问题项，才算 ACCEPTED；候选报告一改，连续通过轮数从头算；去掉「修订后可接受」。

然后写 pypl/references/ 下三个文件（现在是占位）：

role-cards.md：Orchestrator（主 agent）、generator、critic 两个负责人和六个专项，一共九个角色，每个写清楚：职责、输入、输出、能用的工具、有没有写权限、不能做什么。几条硬规则要体现：只有控制器脚本能写 .pypl/ 下的状态文件；所有 agent 只返回文本或 JSON，不自己落盘状态；Critic 只拿到候选报告、固定验收标准和证据，看不到 Generator 的推理过程；检索到的网页和文件内容只当数据，不能当成授权或指令；这个系统没有任何交易工具。

schema.md：定义这些数据长什么样：请求（request_id、触发原因、as-of）、状态文件（当前阶段、轮次、各产物路径和 sha256、问题项列表、版本号、终态和原因）、holdings.json、events.json、问题项（编号、严重程度、所属维度、报告里的位置、要求怎么修）、报告的固定结构、给 Critic 的检查卡。

rules.md：限制和规则，数字直接定下来——最大修订轮数 3、单步重试 2 次且退避、单次运行工具调用不超过 60 次、单次运行不超过 20 分钟；终态分开记录原因：accepted、rejected、blocked、exhausted、stalled、user_stopped，其中 exhausted 绝不等于通过；恢复规则：先核对完成标记、ID 和哈希，只做还没做完的，已经完成的直接返回保存的结果；as-of 规则：财报前的报告不能引用之后的信息。

只写这些规则和契约，先不要写 agent 的正文和脚本。
~~~~

## 第 9 条 · 2026-11-15 18:09:28
~~~~
接下来写 pypl/agents/ 下八个 agent 的正文。先读一下 references/ 里的 role-cards.md、schema.md、rules.md，按里面的契约来，不要自己另起一套。写之前先对齐三处：

1. role-cards.md 里 gen-data 只有 Read，没法取数；critic-evidence 只有 Read，没法独立核对来源。工具以我下面写的为准，请同步改 role-cards.md 的「可用工具」。
2. schema.md 的 Request.trigger 里有 evo，evo 不生成报告，把它去掉。
3. schema.md 的 Critic 检查卡七项没写谁负责，请在每一项后面标出负责角色：结论、理由、来源核对、as-of 泄露归 critic-evidence 或 critic-risk（你按内容分），稳健性归 critic-robustness，交易指令和风险提示归 critic-risk，格式（第 7 项，对应 format 维度）归 critic 负责人在覆盖检查时核对。保证每一项都有人负责。

然后写八个 agent。每个文件的正文用中文，包括：你是谁、输入什么、做什么、输出格式（严格按 schema.md，只返回 JSON 或固定结构的文本）、不能做什么、信息不够时怎么办（明确返回「信息不足」，不要编）。frontmatter 的 tools 按下面来：

- generator 和 critic（两个负责人）：tools 是 Agent 和 Read；subagents 分别列各自的三个专项。正文里要写死：必须真的去调用三个专项，不能自己编专项的回答；产物和证据用文件路径加 sha256 传给专项和 Critic，不要复述内容；最后返回的内容里要列出你实际调用了哪几个专项，方便控制器核对；如果派活失败就直接返回错误，不要假装成功。
- gen-data：Read、WebSearch、FetchURL、mcp__kimi-datasource__*。只能用 design/task.md 里允许的资料来源，每条数据都要带来源链接和获取时间，超过 as-of 的一律不用。
- gen-fundamentals 和 gen-valuation：只给 Read，输入是 gen-data 整理好的数据文件，不要自己上网。
- critic-evidence：Read、FetchURL，要自己去核对报告里的关键数字是不是和来源对得上。
- critic-robustness 和 critic-risk：只给 Read。critic-risk 要检查：有没有买入、卖出、下单这类执行性指令；有没有引用 as-of 之后的信息；结论是不是增持、减持、持有不动三选一；有没有风险提示。

所有 agent 都不给 Write、Edit、Bash。最后一条消息必须是完整、自成一体的结果，因为调用你的上级只能看到这一条。

写完后列一张表：角色、tools、subagents，我对着 role-cards.md 核一下。脚本这一步还是不写。
~~~~

## 第 10 条 · 2026-11-15 18:13:43
~~~~
先处理一下 CONTEXT.md，现在有几个问题：
1. 全部写成了「补录」，包括你后来追加的第 8、9 条。其实每条都有真实时间：会话记录里 ~/.kimi-code/sessions/wd_25260660029-final-project_5d5444b88f59/session_*/agents/main/wire.jsonl 中，type 是 turn.prompt 且 origin.kind 是 user 的事件，time 字段是毫秒时间戳，转成本地时间，格式 2026-11-15 17:35:14。请把第 1 到第 9 条的「补录」都换成对应的真实时间，并用 wire.jsonl 核对条数和顺序对得上。
2. 有些原文里本身带「## 」开头的行（比如第 7 条里有一行 ## 第 N 条 · 日期 时间），会和真正的标题混在一起。把每条原文放进用 ~~~~ 围起来的块里，原文一个字不改。
3. 同步更新 AGENTS.md 里那条会话记录规则：以后新增的每条都用当前真实时间（可以用 date 命令取），不要再写「补录」；格式是标题 ## 第 N 条 · 时间，下面是 ~~~~ 围起来的原文。
4. 这条消息本身记为第 10 条，时间用真实时间，不要写补录。

接着改一个设计问题：现在 agent 的输出里让它们自己返回产物的 path 和 sha256，但是它们都没有写权限，也算不了哈希，这些值只会是编的。改成这样：
- agent（generator、critic 和各专项）只返回内容，不返回 path 和 sha256。专项之间、负责人和专项之间直接传内容。
- 候选报告和证据包由 Orchestrator 调用控制器脚本落盘，由脚本算 sha256，再把脚本返回的路径和哈希交给下游。Critic 用 Read 读控制器写好的文件，控制器在派 Critic 之前先核对哈希。
请据此修改 generator、critic、gen-data 的输出格式和说明，schema.md 里 artifacts 的写法保持不变（那是控制器写的），role-cards.md 如有相关描述也一起改。

然后更正「没有定时器」的说法。Kimi 有会话内定时工具 CronCreate、CronList、CronDelete：会话开着才会触发，循环任务 7 天后过期，创建需要我批准。所以：
- /pypl:event 登记财报日期时，除了控制器写 events.json，还用 CronCreate 登记两个一次性提醒（财报前两天、财报发布后），提醒触发时让会话去跑 ping 流程。
- /pypl:ping 第一次运行时，可以用 CronCreate 登记一条每天循环的检查。
- 文档里如实写明局限：会话关了就不触发，循环任务 7 天后要重新登记；演示时也可以手动运行。
请改 design/task.md 里「没有定时器」的相关说法。

接着写 references/controller.md：约定控制器脚本 pypl/scripts/pypl.py 有哪些动作（子命令）、入参、返回的 JSON，至少包括：初始化、登记持仓、登记事件、新建请求、落盘产物并算哈希、核对哈希、记录问题项、推进阶段、写终态、恢复。只定义契约，还不要写代码。

最后写命令和 skill 的正文（中文）：
- pypl/skills/start/SKILL.md：Orchestrator 的完整工作流，用 sessionStart 注入。从收到触发到终态的每一步：新建请求、派 generator、落盘并核对哈希、派 critic、判断本轮是否通过、问题项汇总成修复任务包发回 generator、最多 3 轮、连续两轮通过才 accepted、各种终态怎么处理。accepted 之后要问我是否批准归档（用 AskUserQuestion）。调脚本时用 skill 所在目录推出来的绝对路径，不要写相对路径；.pypl/ 放在我启动 Kimi 的目录下。Orchestrator 自己不写 .pypl/，不做交易。
- pypl/skills/evo/SKILL.md：系统演进流程：固定基线样例、改动前后对比、我批准、版本号、回滚。
- pypl/commands/ 五个文件的正文：每个说明它做什么，并让 Orchestrator 按对应 skill 的流程执行，用 $ARGUMENTS 接收参数。

脚本代码这一步还不写。写完告诉我改了哪些文件。
~~~~


## 第 11 条 · 2026-11-15 18:19:01
~~~~
现在写控制器的代码和测试。先把契约里几处不合理的地方改了，然后实现，只用 Python 标准库，不要装任何依赖。

契约调整（同步改 references/controller.md 和 skills/start/SKILL.md）：
1. 所有子命令统一从 stdin 读一个 JSON，把结果 JSON 打到 stdout，不用命令行参数传内容（报告全文含引号和换行）。调用方式写成 python3 <脚本绝对路径> <子命令> 配 heredoc 传 JSON。
2. 脚本绝对路径固定写 ${KIMI_CODE_HOME:-$HOME/.kimi-code}/plugins/managed/pypl/scripts/pypl.py，不要再用 skill 目录推导。.pypl/ 放在运行时的工作目录下。
3. record_event 不要碰 Cron。脚本只写 events.json，并把两个提醒该触发的日期时间返回给 Orchestrator，由 Orchestrator 自己调用 CronCreate。
4. 新增 record_review：Orchestrator 把 Critic 这一轮的结论和问题项交给它，由脚本更新 consecutive_passes、round，并返回 next_action，取值只有：revise（带修复任务包）、review_again（同一候选再审一轮）、await_approval（连续两轮通过，等我批准）、final（带终态和原因，比如 exhausted）。候选报告哈希变了就把 consecutive_passes 清零。修订轮数、终态规则全部按 references/rules.md。skill 里改成「照 next_action 走」，Orchestrator 不自己算轮数。
5. 新增 gate_report：候选报告送 Critic 之前先过一道确定性检查，返回通过与否和失败项，至少检查：六个部分齐全；结论是增持、减持、持有不动三选一；理由不少于三条；有风险提示；正文里没有买入、卖出、下单这类执行性指令词；封面的 as-of 不晚于请求的 as-of；证据包里每条来源都有 URL 和获取时间，且获取时间不晚于 as-of。
6. 新增 check_limits：传入已用工具调用次数和开始时间，超 60 次返回 blocked，超 20 分钟返回 stalled。

实现放在：pypl/scripts/pypl.py（只做入口和分发）、pypl/runtime/pypl/ 下按职责拆几个模块（状态机、产物与哈希、关卡检查等，已有的 state_machine.py 和 levels.py 你读着合并或改名）。要求幂等：同一个 request_id 重复落盘相同内容不重复写；终态写入后不可被覆盖；recover 只返回未完成的步骤。

测试放 pypl/tests/，用 test_data.json 或新增 fixtures 做测试数据，pypl/scripts/check.py 一条命令跑完所有测试，打印每条用例 PASS 或 FAIL，失败退出码非零。至少覆盖：落盘幂等；哈希被篡改后 verify_hash 失败；候选报告改动后连续通过清零；连续两轮通过才 await_approval；达到 3 轮仍未通过是 exhausted 而不是 accepted；终态不能被覆盖；recover 不重复已完成步骤；gate_report 对「含买入指令」「as-of 泄露」「结论不是三选一」各拦住一次；check_limits 两种超限。

写完自己跑一遍 check.py，把输出贴给我。agent 和命令这一步不要动，只改 skill 里调用控制器的那几处。
~~~~

## 第 12 条 · 2026-11-15 18:30:19
~~~~
已经reload了，还是没有么
~~~~
## 第 13 条 · 2026-11-15 18:38:14
~~~~
这是一个新会话。上一轮取数时 Datasource 的 MCP 工具没法调用，现在补做。

1. 先确认你现在能用的取数相关工具有哪些，看看 mcp__plugin-kimi-datasource_data__get_data_source_desc 和 mcp__plugin-kimi-datasource_data__call_data_source_tool 在不在。如果不在，直接告诉我，不要用别的办法绕。
2. 在的话，先调 get_data_source_desc 看 Datasource 到底有哪些数据源、每个数据源有哪些工具、入参是什么。把它真实返回的数据源名和工具名列给我。
3. 然后用 Datasource 补取 PYPL 的这几项：当前股价和最近 30 天涨跌；最近 30 天新闻（带日期和来源）；下一次财报日期；最近一份 8-K 的标题。总共不超过 15 次调用，失败了如实记录，不要编。
4. pypl/references/data-sources.md 里之前写的 Datasource 数据源名（sec_edgar、stock_finance_data、yahoo_finance、xhcj、cls 这些）是没实测就写的，按第 2 步真实返回的内容更正，没验证过的一律删掉，不要保留猜的。把第 3 步实测的结果、成功与否、调用次数写进去，并更新 examples/input/ 里对应的样例（只留摘要、数字、来源 URL 和获取时间）。
5. 把 pypl/agents/gen-data.md 的 tools 里的 mcp 工具名按真实情况核对一遍。Bash 这一步先不动，我下一步单独处理。

做完告诉我：Datasource 实际有哪些数据源、第 3 步每项拿到没有、调用了几次。其他文件不要动。
~~~~

## 第 14 条 · 2026-11-15 18:49:26
~~~~
下一步把财报数字的获取从 gen-data 里拿出来，做成控制器的确定性代码，对应作业里「在适当环节用确定性代码完成计算」和「agent 不拿 Bash」。请这样做：

1. 控制器新增子命令 fetch_sec（实现放 pypl/runtime/pypl/fetch.py，入口仍在 pypl/scripts/pypl.py），只用 Python 标准库 urllib。输入 as_of。访问 SEC XBRL 接口 https://data.sec.gov/api/xbrl/companyconcept/CIK0001633917/us-gaap/{概念}.json，概念先取 Revenues、NetIncomeLoss、EarningsPerShareDiluted 三个。要求：
   - 只允许访问 data.sec.gov 和 www.sec.gov，别的域名直接拒绝；
   - 带声明的 User-Agent，写项目名加联系邮箱，邮箱就用 AGENTS.md 里已经有的那个；
   - 每次请求间隔不少于 1 秒，超时 30 秒，失败按 rules.md 重试 2 次并退避；
   - 只取 form 是 10-Q 或 10-K、且 filed 日期不晚于 as_of 的最近一期，单季数据要用 start 到 end 大约三个月的那条；as-of 过滤必须在代码里做，不能靠提示词；
   - 返回结构化 JSON：概念、数值、单位、期间起止、accession、filed 日期、来源 URL、获取时间；
   - 取不到就返回 error，不要悄悄用录制数据。只有入参里显式带 allow_recorded 才允许退到 examples/input/ 的录制数据，并且返回里必须标 recorded=true。
2. skills/start/SKILL.md 加一步：新建请求之后、派 generator 之前，Orchestrator 先调 fetch_sec，拿到的 JSON 作为 sec_facts，和持仓一起放进任务包，并用 persist_artifact 落盘留证据（schema.md 的 artifacts 里相应加一项 sec_facts）。
3. gen-data：去掉 Bash，也不再自己取财报数字，直接用任务包里的 sec_facts。它只负责 Datasource 能取的东西：股价、新闻、8-K 条目、补充材料，按 data-sources.md 里实测过的 API 来。如果它整理的数字和 sec_facts 不一致，以 sec_facts 为准。同步改 role-cards.md 里 gen-data 的工具栏和 data-sources.md 里财报数字的首选来源。
4. 报告固定结构里加一个 key_figures JSON 块（收入、净利润、稀释 EPS，带单位和期间），由 generator 写，方便机器核对。改 schema.md 的报告结构和 generator.md 的输出说明。
5. gate_report 增加数值交叉核对：key_figures 里的收入、净利润、EPS 必须和 sec_facts 一致（单位换算后比较，四舍五入容差 0.5%），不一致就返回失败项 numeric_mismatch，并说明哪个数不一致。
6. 测试：把上面三个概念的 SEC 返回结构（取最近几期，摘要即可）存成 pypl/tests/fixtures/sec_xbrl_sample.json，fetch 的网络部分要能注入假的 fetcher，默认测试不联网。新增用例：非白名单域名被拒绝；as_of 早于最近一期 filed 日期时返回上一期（演示防未来信息泄露）；数值一致通过；数值不一致被拦；取不到时不悄悄用录制数据。再做一个可选的联网自检 python3 pypl/scripts/check.py --live，默认不跑。check.py 全部通过再告诉我。

写完把 check.py 的完整输出贴给我，再用 --live 真实跑一次 fetch_sec 把返回结果贴出来（as_of 用今天）。agent 其他部分和命令不要动。
~~~~

## 第 15 条 · 2026-11-15 21:21:50
~~~~
接下来给插件加一个 PreToolUse hook，防止两件事：状态文件被控制器以外的人改，以及碰到交易相关的接口。参考官方文档，插件的 hooks 写在 kimi.plugin.json 里，hook 命令运行时工作目录是插件根目录，脚本通过 stdin 收到 JSON，退出码 2 表示拦截，stderr 是拦截原因，其他退出码默认放行。

1. 新增 pypl/hooks/pre_tool_use.py，只用标准库。规则：
   - Write、Edit 的目标路径落在任何 .pypl/ 目录下（路径字段名 path 或 file_path 都要兼容，要先 resolve 成绝对路径再判断，防止 .. 绕过）就拦截，提示「状态文件只能由控制器脚本写入」。
   - Bash 命令里如果有往 .pypl/ 写、改、删文件的操作（重定向、tee、sed -i、rm、mv、cp 目标在 .pypl/ 之类），并且这条命令不是调用 plugins/managed/pypl/scripts/pypl.py 的，就拦截。
   - Bash 和 FetchURL 里出现券商或下单相关的主机名（alpaca、robinhood、interactivebrokers、ibkr、schwab、tdameritrade、etrade、futunn、tigerbrokers 这些）或明显的下单请求特征（place order、submit order、/v2/orders 这类），就拦截，提示「本系统只做研究，不执行交易」。
   - 其他一律放行，退出码 0。不要写太宽的规则，宁可漏拦也不要误伤正常的 git、测试、读文件命令。
   - 每次拦截往运行时工作目录下的 .pypl/guard-log.jsonl 追加一行（时间、工具名、被拦的内容摘要、规则名），留作证据。日志目录不存在就创建。
2. 在 pypl/kimi.plugin.json 里加 hooks：event 是 PreToolUse，matcher 是 ^(Write|Edit|Bash|FetchURL)$，command 是 python3 ./hooks/pre_tool_use.py，timeout 5。其他字段保持不变。
3. 测试：新增 pypl/tests/test_hook.py，用 subprocess 把 JSON 喂给脚本，覆盖：Write 写 .pypl/state.json 被拦；用 .. 绕路的路径也被拦；Write 写普通文件放行；Bash 用 echo 重定向写 .pypl/ 被拦；Bash 调用控制器脚本放行；Bash 跑 git status 和 python3 pypl/scripts/check.py 放行；FetchURL 访问 alpaca 的下单接口被拦；FetchURL 访问 data.sec.gov 放行；脚本收到坏的 JSON 时放行并且不崩溃。把它加进 check.py 一起跑，全部通过再告诉我。
4. 检查 .gitignore 里有没有 .pypl/ 和 __pycache__/，没有就加上。运行时产生的状态不要入库，需要作证据的我们之后手动复制到 evidence/。
5. 在 design/ 下的设计笔记里（design/design.md，现在是占位，先写一小节就行）记一下：hook 是第二道防线，Kimi 的 hook 是 fail-open，不能当作唯一的安全屏障；第一道防线是 agent 的 tools 白名单和系统里没有任何交易工具。

写完把 check.py 的完整输出贴给我。agent、命令、skill 这一步不要动。
~~~~
