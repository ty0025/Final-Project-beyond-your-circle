# PROJECT_SPEC — Beyond Your Circle（MGT 409 Final Project）

> 本文件是项目的需求与边界基线，由问题1（2026-10-25）建立。后续各题只在有依据时修改，并在 PROGRESS.md 记录改动原因。
> 编号规则：`C-` 课程要求（来自课程原文/Word），`U-` 用户已确定的产品决定（来自背景说明），`M-` 模型/密钥/证据规则，`I-` 我们的实现选择（不是课程规定），`P-` 等待用户补充的信息。
> 状态词只用四种：**已验证通过**（执行过检查且满足）、**失败**（执行过检查且不满足）、**未验证**（尚未实现或尚未检查）、**等待真人输入**（需要用户本人提供或操作）。

## 0. 来源与优先级

| 来源 | 位置 | 版本/时间 | 用途 |
|---|---|---|---|
| 课程原文（最高优先级） | https://zlisto.github.io/mgt_409_fa26/project_requirements.html | 2026-10-25 01:10Z 下载，HTML sha256 `a861edcd…a6`，页面无“最后更新”信息 | 课程要求 `C-` 的依据 |
| 中文整理 Word | 用户本地 `MGT409_FinalProject_要求整理(1).docx`（微信文件夹） | sha256 `dad97a8c…94`，文档无批注对象；正文注明“写 report 和 slides 时以课程网站原文为准” | 交叉核对；与原文一致，差异见 evidence/q01.md §2 |
| Lecture 11 slides | https://zlisto.github.io/mgt_409_fa26/lectures/slides/lec11-slides.html | 2026-10-25 读取 | gpt-6-luna 单价 |
| 用户背景说明 | 本对话第一条消息（问题1之前） | 2026-10-25 | 产品决定 `U-`、规则 `M-` |
| 项目 AGENTS.md | `../AGENTS.md`（repo 上一级） | 2026-10-25 | 只用 gpt-6-luna、密钥不外泄、蓝色视觉、生物类用 HTML |

冲突处理：课程原文 > Word 整理 > 我们的实现选择。用户背景中的产品决定只在不违反课程原文时生效（目前无冲突）。

## 1. 课程要求（C-，均来自课程原文，Word 一致处不再重复标注）

| 编号 | 要求 | 备注 |
|---|---|---|
| C-01 | 个人项目，Canvas 截止 **Monday, October 26, 2026, 6:00 PM** | 原文未写时区；以 Canvas 显示为准（P-03） |
| C-02 | Canvas 提交 3 样：GitHub repo 链接、`report.html`、`slides.html`；可选 2–3 分钟 demo 视频（上传 Canvas） | repo 公开，或私有并把 GitHub 用户 `zlisto` 加为 collaborator |
| C-03 | 两个 HTML 自包含：任意电脑双击打开、所有截图都显示（图片嵌入文件） | |
| C-04 | Report 10–15 页（letter、常规字体、含截图）；写给没见过 app 的聪明管理者；可用 AI 辅助，但每个字和数字须与 app 实际一致；凑页数扣分 | |
| C-05 | Report 八节按序：1 Title + links（项目名、姓名、repo 链接=Canvas 所交、在线链接如有、一句话说明）；2 Motivation；3 What is new here；4 The agents（各 agent 职责、工具、组织/交接、架构图、模型及理由、一次真实运行逐步配截图）；5 Tokenomics（典型运行的 input/cached input/output 实测；单次、每用户每月、100 与 10,000 用户成本；省钱措施及是否变差，有证据）；6 Safety（攻击、agent 故障、超支；至少一个防御真实生效的截图或测试）；7 Impact（量化并说明数字来源，最强证据是真实用户试用）；8 Limits + next steps | |
| C-06 | Slides：单个 HTML，**最多 10 页**，用 reveal.js（方向键翻页、F 全屏）；建议顺序：标题/问题/新在哪/架构图/demo 截图/成本/安全/impact 数字/下一步；完成后双击打开并逐页方向键检查 | 原文示例提示词写 “using reveal.js, loaded from a CDN” |
| C-07 | Repo：运行所需全部代码；README 写清 app 是什么、逐步运行方法（或在线链接）；`.env.example` 列出所需 key 名、不含真实值；绝不提交真实 `.env` 或 `PORTKEY_API_KEY` | |
| C-08 | 若使用大数据集，repo 内附小测试集，README 说明如何切换 | |
| C-09 | 课程 key：`PORTKEY_API_KEY` **只能用 gpt-6-luna**；其他模型须自费个人 key（OpenAI 的名为 `OPENAI_API_KEY`） | |
| C-10 | 老师运行方式二选一：在线（README 与 report 顶部放链接，保持可用至最终成绩公布；免费托管会休眠，提交当天确认），或本地 fresh clone 按 README 运行；本地配置越简单越好 | |
| C-11 | 10 分钟规则：按 README 10 分钟仍未运行 → “The teaching staff can run it” 0 分 | |
| C-12 | `.env` 先找 repo 自身目录，再找上一级；老师的 `.env` 只有 `PORTKEY_API_KEY` 与 `OPENAI_API_KEY`，名字须完全一致；**需要其他 key 的 app 必须上线并咨询教授** | Word 未写最后一点 |
| C-13 | 提交前 dry run：clone 到新文件夹、`.env` 放上一级、按 README 从头跑并使用 | |
| C-14 | 视频可保住 “It works” 与 “Look + feel”，**不能**保住 “can run it” 的 5 分 | |
| C-15 | 评分 100 分（Idea 21；App 30 = It works 15 + can run 5 + Look & feel 10；Report 41 = Motivation & new 8 + Agent design 10 + Tokenomics 8 + Safety 8 + Impact 5 + Design 2；Slides 8 = Content 6 + Design 2） | 逐项见 evidence/rubric_checklist.md |
| C-16 | 证据规则：Report 各行缺少指定证据最多得该行一半（Motivation：点名对比的现有产品；Agent design：一次真实运行逐步追踪+各 agent 截图；Tokenomics：真实运行 token 数，日志或 app 内显示，纯估算减半；Safety：防御真实拦住攻击或故障的截图/测试，只描述减半；Impact：真实用户试用（引用、截图或前后耗时），纯猜测减半） | |
| C-17 | Tier 1/2/3 定义；常见选题（简历/求职信、Chat with PDF/文档、旅行规划、邮件/会议总结、菜谱、通用学习伙伴/闪卡、课堂/作业复用无实质新增）若无真 twist，Idea 封顶 Tier 1 | |
| C-18 | （建议，非强制）先有人再有技术；找真实用户聊；随手截图；先做出能跑的再变聪明 | “Ship something that works first” 仅原文有 |

## 2. 产品定义（U-，用户已确定）

| 编号 | 决定 |
|---|---|
| U-01 | 项目名 **Beyond Your Circle**：校园活动与社群发现助手 |
| U-02 | 首版主要使用者：耶鲁 SOM 研究生；发现范围：耶鲁其他院系及 New Haven 的**公开**活动、社群和持续项目 |
| U-03 | 主要目标：找到同兴趣的人或社群，方便持续参与；次要目标：专业/主题交流机会 |
| U-04 | 测试兴趣（仅测试用例，不得硬编码成只有三个标签）：① 摄影技巧讨论、作品交流与共同拍摄；② 普通爱好者可参与的运动、休闲比赛和观赛；③ 非技术背景的 AI 普及 |
| U-05 | 用户输入：兴趣 + 具体交流目的 + 参与方式；应用输出：收集到的公开信息、为什么匹配、有哪些参与条件、下一步去哪里了解或报名 |
| U-06 | 结果分三组：本周 / 未来几周 / 长期社群或持续项目；时间按 America/New_York，窗口明确写出 |
| U-07 | 推荐以贴近兴趣为主，少量探索项须说明关联；没有合适探索项时可以为零 |
| U-08 | 差异化重点：跨来源发现、理解具体目的、解释匹配、呈现参与门槛——必须落实为**可检查的功能差异**，不能只靠文案 |
| U-09 | 诚实对比：Yale-Localist 与 YaleConnect 已提供活动查找与部分个性化，不得声称校园从未有活动聚合 |
| U-10 | 首版采用有限、已验证的公开来源；用户手动刷新触发自动收集；不要求关闭网页后的推送 |
| U-11 | 不做：私人 Slack、WhatsApp、邮件、Canvas（不需其账户或授权）；自动报名、付款、发消息、排日历、匹配个人或组队；复杂账户系统 |
| U-12 | 事实边界：页面公开≠所有学生可参加；有报名链接≠有余位；赛季进行≠仍可报名；社群存在≠正在招新。已知不满足硬条件的不能作为“可参加”匹配；未知条件标“待确认”；缺日期的记录不能冒充本周活动；空结果如实显示 |
| U-13 | 数据溯源：保留原始 URL、组织方、收集时间、关键字段依据和缺失值；区分在线刷新、缓存、固定快照、真实模型与模拟测试；不把历史或虚构数据当实时结果 |
| U-14 | 用户痛点数据仅为个人回忆估计（问朋友 10–20 分钟、Google 10–20 分钟、CampusGroups/Slack/WhatsApp 各十几分钟；频率、是否同一任务、是否重复均未实测）。**不得相加成每次/每周总耗时，不得写成应用已节省的时间**；实际效果另测 |
| U-15 | 用户本人是真实目标使用者，可做 creator n=1 真实操作记录；不等于独立试点；暂不招募他人；没有真人操作就标“等待真人输入”，不编造访谈、反馈、计时或社交成果 |
| U-16 | 页面清楚易用，功能和证据优先；所有页面采用蓝色视觉风格（AGENTS.md） |

## 3. 模型、密钥与证据规则（M-）

| 编号 | 规则 |
|---|---|
| M-01 | 应用运行时所有课程模型调用仅用 **gpt-6-luna**，经 Portkey，使用 `PORTKEY_API_KEY`。Claude Code 只是开发工具，不属于应用的模型调用 |
| M-02 | 密钥只在后端；`.env` 先查 repo 内再查父目录；不得打印、提交、传给前端或写入证据/日志 |
| M-03 | 从第一次真实调用起记录**所有**模型调用（提取、守卫、验证、重试都算）：input、cached input、output 等实际 usage，及 run_id、角色、工具、耗时、停止原因；缺失字段不冒充测得零；不重复计费 |
| M-04 | 保留调用/重试/时长/token/费用上限；公告/网页内容是不可信数据，不能改变系统指令或工具权限 |
| M-05 | 安全与 usage 基础未就绪时只做离线 mock/stub 检查，不发真实模型请求；mock 指脚本化假模型，不是其他本地或远端模型 |
| M-06 | 单价（Lecture 11 slides，每 1M tokens，gpt-6-luna）：input $0.10、cached input $0.01、cache write $0.125、output $0.50。成本按实测 token 逐次计算 |

## 4. 实现选择（I-，我们的决定，不是课程规定）

| 编号 | 选择 | 理由 / 依据 |
|---|---|---|
| I-01 | 复用现有 FastAPI 单进程 + 静态 HTML/CSS/JS 基础（无 Node 构建、无数据库），替换领域层，不重建 HW4/HW5 技术栈 | 背景要求；基础模块已有离线测试（见 §6） |
| I-02 | fresh clone 为主要交付路径；在线部署不强制 | 背景决定；C-10 二选一 |
| I-03 | 先打通**两个**已验证公开来源的一条真实推荐路径，保留运行、成本、安全证据；第三个及更多来源、额外案例、视觉扩展在核心证据齐备后再做 | 背景时间取舍 |
| I-04 | 公开来源必须**无需额外 API key** 即可读取（公开页面/公开 feed） | C-12：其他 key 会迫使上线并咨询教授，破坏 fresh clone 路径 |
| I-05 | slides 用 reveal.js CDN（课程示例允许）；报告与 slides 中须说明此网络依赖，不宣称完全离线；截图以 base64 内嵌（`scripts/inline_images.py`） | C-03、C-06 |
| I-06 | 实现 America/New_York 日期窗口时，在 `requirements.txt` 加入 `tzdata` | 问题1实测：本机 Windows Python 3.14 无 `tzdata` 时 `ZoneInfo("America/New_York")` 抛 `ZoneInfoNotFoundError`；老师的 Windows 环境同理 |
| I-07 | 验证优先离线与定向检查；整合节点再做必要回归；不反复执行无关测试或付费调用 | 背景 |
| I-08 | 既有 Harbor Bikes 运行记录（`runs/`、`evidence/tokenomics.*`、`evidence/redteam_results.json`）保留为“占位领域的基础验证历史”，**不得**作为新领域的 tokenomics/safety 证据 | U-13、C-16 |
| I-09 | 每题交接用“评分项 → 实现位置 → 验证方法 → 证据路径/版本/run_id → 状态”；维护本文件、PROGRESS.md、AI_prompts.md 与 evidence/qNN.md | 背景协作方式 |
| I-10 | 自动采集遵守 robots.txt 与 Crawl-delay；robots 禁止的站点（如 events.yale.edu）不自动采集，只可作为现有产品对比 | 问题2实测；负责任的采集姿态 |
| I-11 | 字段优先用代码确定性提取；页面没写就记为未知（`missing`），不推断免费/不限名额/人人可参加；采集阶段如需模型，必须走同一网关、预算与账本，且须先修复 F-01～F-08 | 问题2任务 5；U-12 |
| I-13 | “本周”= 从今天 00:00（America/New_York）起 7 个自然日；“后续机会”= 之后的单日期活动；项目与社群单列“长期”，显示下一场开放场次；无日期活动单列“日期不明” | 问题3；避免周末时“本周”几乎为空，窗口日期在页面写明 |
| I-14 | 界面刷新：同一时间只允许一次，完成后冷却 300 s（`REFRESH_COOLDOWN_S`）；`COLLECT_SIMULATE_OUTAGE=1` 只用于明确标注的断网演示 | 问题3；对来源站点礼貌，失败演示不伪装成真实故障 |
| I-15 | Agent 组织：规则筛查（代码）→ guard（1 次 gpt-6-luna）→ 单个 matcher agent（工具 `search_listings`/`get_listing`，最多 4 轮）→ verifier（代码，不调用模型）；退役 researcher 与 LLM verifier | 问题4；检索与核验由确定性代码完成更省调用且可复现；见 evidence/architecture.md |
| I-16 | 所有模型尝试（成功、失败、重试）逐条入账：`mode` live/mock、`served_model`、缺失 usage 记 null；每 run 最多 12 次调用、应用层最多 1 次重试 | 问题4 计量门槛 F-01～F-08 |
| I-17 | 推荐状态由服务端决定：硬条件（形式、时间窗口、受众、先修、年龄、会员、参与/观看、报名）对照用户原话，`not_met` 排除、`to_confirm` 为“check first”；事实由服务端还原并附页面原文；模型文字中页面没有的价格/时间/日期/链接等被删除；交流形式与探索关联必须有逐字引文 | 问题5；U-12 的“已知不满足不作为可参加匹配、未知待确认” |
| I-18 | 功能案例可用人工核对的公开记录（逐字抄录、标明读取时间），只作测试夹具、不进入应用数据；对照只说明同一应用内两种处理的差异 | 问题5 任务 5–6 |
| I-12 | 首批接入来源（问题2）：`caw-photo`（Creative Arts Workshop 摄影课程，社区非营利）与 `ycgs-events`（Yale Center for Geospatial Solutions 活动，耶鲁官方）；已检查未接入的候选及原因见 `app/collect/sources.py` 的 `NOT_CONNECTED` 与 evidence/q02.md §1 | 问题2实测 |

## 5. 交付清单（课程要求 → 我们的检查方法）

| 交付物 | 课程要求 | 我们的检查方法（实现选择） |
|---|---|---|
| GitHub repo | 全部代码、README、`.env.example`（无真实值）、小测试数据；公开或私有+zlisto | fresh clone 到新目录、`.env` 放上一级、按 README 计时运行；密钥扫描；记录可见性/collaborator 状态 |
| report.html | 10–15 letter 打印页、八节顺序、图片内嵌、双击可开 | 浏览器打印预览数页数；检查无外链图片；数字与证据文件逐项对照 |
| slides.html | ≤10 页、reveal.js、图片内嵌 | 双击打开、方向键逐页检查；说明 CDN 依赖 |
| demo 视频（可选） | 2–3 分钟真实演示 | 仅在用户本人录制后记录；不替代运行验收 |

## 6. 现有工程基线（问题1核对结果）

详细证据：evidence/q01.md。摘要：

- **可复用**：`app/config.py`（模型锁定、两级 `.env`）、`app/llm.py`（唯一调用点、Portkey、强制绕过响应缓存）、`app/pricing.py`/`ledger.py`/`budget.py`（计价、账本、调用前预算检查）、`app/agent.py`/`tools.py`/`events.py`（agent 循环、委派、白名单、上限、trace）、`app/safety.py`（spotlight、注入扫描、脱敏）、`app/server.py` 外壳与 `web/` 时间线/成本卡、`run.py`/启动脚本、`scripts/tokenomics.py`/`inline_images.py`。离线测试 296 passed。
- **占位（待替换）**：`app/domain/*`、`data/sample/*`、`app/orchestrator.py` 中的团队/元数据/`ALLOW_DOMAINS`/拒答文案、`web/app.js` 结果卡、`scripts/redteam.py`、依赖样例文件的测试、README/DESIGN。
- **未实现（问题1时）**：公开来源采集、来源注册表、统一记录 schema、America/New_York 日期窗口、硬条件过滤、匹配解释输出、刷新/来源状态端点、数据模式标注、采集器网络隔离测试。问题2已实现其中的采集、来源注册表、统一记录、快照/缓存标注与网络隔离测试（`app/collect/`）；日期窗口分组、硬条件过滤、匹配解释与应用内刷新仍未实现。
- **真实模型调用前的门槛**：F-01～F-08（缺失 usage 记 0、失败/重试不入账、无调用次数上限、model 字段为常量、无真实/模拟标记、`OPENAI_*` 环境变量、空格 key）。

## 7. 等待用户补充（P-）

| 编号 | 需要的信息 | 用途 | 是否阻塞当前工作 |
|---|---|---|---|
| P-01 | 报告/slides 署名（姓名写法） | Report §1、slides 标题 | 已提供：**Tongyu David Chen**（2026-10-25） |
| P-02 | 真实 GitHub repo URL、公开/私有、是否已加 `zlisto` | Report §1、Canvas 提交、“can run it” | 否（提交前需要） |
| P-03 | Canvas 实际显示的截止时区 | 时间安排 | 否；用户表示不重要（2026-10-25） |
| P-04 | creator n=1 真实操作记录（真人操作、计时、截图、原话） | Impact 证据 | 否（应用可用后需要） |
| P-05 | `.git` 目录归属另一 Windows 账户（CodexSandboxOffline），普通 git 命令报 “dubious ownership”。需用户决定：允许执行 `git config --global --add safe.directory "C:/Users/david/Desktop/Courses/my-app/final project"`，或用其他方式修正归属 | 首次提交、推送 | 否（提交前需要；只读检查可用 `git -c safe.directory=...`）；用户表示之后自行更新该配置（2026-10-25） |
| P-06 | 首批两个公开来源的最终选择是否需用户确认 | 公开采集 | 否（问题2已按候选实测选定，见 I-12） |
| P-07 | events.yale.edu 的 robots.txt 为 `Disallow: /`：保持不自动采集（默认），或由用户另行取得许可 | 来源覆盖 | 已决定：不采集（用户 2026-10-25 确认） |

## 8. 协作方式

- 用户按问题1→10 逐题发送；只完成当次问题，不提前实施后题。
- 每题结束更新 PROGRESS.md、AI_prompts.md（Initial Prompt / Follow-up Prompt / What Was Lacking，只记真实发生的内容）和 evidence/qNN.md。
- 前题缺项持续传递；依赖真实数据、计量/安全或真实模型的验收不能越过前置缺口；生成文档不等于销项。
- 中断后先读本文件、PROGRESS.md 及本题证据，核对现有修改，只补未完成或因新改动失效的部分；能复用的真实运行不为补截图付费重跑。
