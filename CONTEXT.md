## 第 1 条 · 补录
update agents.md

content
这个仓库是 《金融人工智能编程》期末作业
提交人：于欣荷
学号：25260660029

github repo needs commit and push frequently, you can decide when to commit and add file and commit and push accordingly without the needs of asking permission.

i will use either chinese or english with you but you need to response in chinese,
and use chinese in agents md and other skills, prompts, and code comments.

## 第 2 条 · 补录
continue update @AGENTS.md 

about github, 

all commits shall be made on behalf of 
git config user.name "于欣荷"
git config user.email "cynthiayu615@gmail.com"

## 第 3 条 · 补录
copy /Users/guchen/Documents/notes/02-projects/wife/attachments/20261107-金融AI长程智能体工作流/作业要求.pdf into assets/ folder of this repo and refer it in agents saying this is 作业要求

and make a README.md saying briefly about this repo (only necessary info for human reviewer) and say details goes to @AGENTS.md

## 第 4 条 · 补录
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

## 第 5 条 · 补录
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

## 第 6 条 · 补录
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

## 第 7 条 · 补录
我想把我在这个项目里每一次发给你的话都记下来,方便以后回看我是如何一步步指挥你做这个作业的。请这样做:

1. 在 AGENTS.md 的「开发约定」里加一条规则:以后在这个仓库里的每一个 Kimi session,每次我发来消息,你都要先把我这条消息原文追加到仓库根目录的 CONTEXT.md 末尾,再去做其他事。只记我的输入,不记你的回复;原文不要改;只能往后追加,不能改或删以前的记录。每条格式:

## 第 N 条 · 日期 时间
(我的原文)

N 从 1 递增。新 session 第一次回复前,先读一下 CONTEXT.md 最后一条的编号再接着记。

2. 到目前为止我发给你的所有消息,请你自己从会话记录里找出来补录进 CONTEXT.md,按时间顺序,时间写「补录」。你可以看当前对话,也可以去 ~/.kimi-code/sessions 里这个项目对应的目录里找(目录名带 25260660029-final-project)。只要我发的消息,不要你自己的回复和工具输出。

3. 我这条消息也要记,作为最后一条。

做完后告诉我 CONTEXT.md 一共记了几条,列出每条的编号和第一行就行。其他文件不要动。
