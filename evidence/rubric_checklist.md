# 评分与交付检查表（rubric_checklist）

> 建立：问题1（2026-10-25）。每题交接时更新“状态”和“证据”列，并在 PROGRESS.md 记录变化。
> 状态只用：**已验证通过** / **失败** / **未验证** / **等待真人输入**（定义见 PROJECT_SPEC.md 开头）。
> “课程要求”列来自课程原文（PROJECT_SPEC.md `C-`）；“实现选择”列是我们的做法（`I-`/`U-`），不是课程规定。
> 本表只记录事实状态，不做分数预测；自评不替代老师评分。

## A. 100 分评分项

| # | 评分项（分值） | 课程要求与证据规则 | 实现选择 | 实现位置 | 验证方法 | 证据路径 / 版本 / run_id | 状态（问题1） |
|---|---|---|---|---|---|---|---|
| A1 | Idea：Novelty + real-world value（21） | 非常 clever、clearly new，解决真实人的真实问题、真的能用；常见选题无真 twist 封顶 Tier 1（C-15、C-17） | 跨来源 + 具体参与目的 + 参与门槛 + 匹配解释，须是可检查的功能差异；诚实承认 Yale-Localist、YaleConnect 已有活动查找与部分个性化（U-08、U-09） | 跨来源采集（Q2）；目的理解与匹配解释（Q4）；参与门槛判定、事实出处、探索规则（Q5） | 功能逐项对照现有产品，能在 app 中演示 | evidence/q05.md、q05_cases.md、alternatives.md；真实运行 `r_c588d02ea0b5` 等 | **未验证**（功能差异已可演示；Idea 分由老师评定，且缺真实用户证据） |
| A2 | App：It works（15） | 端到端真干活：agent 用真工具、真数据，产出有用结果、不崩；repo 干净、不提交密钥 | 至少两个已验证公开来源的一条真实推荐路径（I-03） | `app/domain/`、`app/collect/`；Find / Browse 页（Q6） | 目标领域真实运行 + trace；离线测试 | Q1：离线基线 296 passed；Q2：真实采集 2 来源 11 条（`data/snapshots/`，collected 2026-10-25 01:32–01:33Z），320 passed | **未验证**（Q6 后：真实数据浏览〔q03〕+ 5 次真实 AI 运行；Q6 `r_ce638df7cf6e` 完成从网页输入、条件、分组结果到打开出处的完整路径，失败/取消/超时/预算状态已用模拟故障验证〔q06〕；仍缺陌生用户使用与 fresh clone） |
| A3 | App：The teaching staff can run it（5） | 在线可用，或 fresh clone 按 README 运行，`.env` 在上一级；大数据集附小测试集；10 分钟未运行 = 0（C-10、C-11、C-12） | fresh clone 为主（I-02）；不引入额外 API key（I-04） | `run.py`、`start.sh`、`start.bat`、`app/config.py`、README | 新目录 fresh clone + `.env` 放上一级 + 按 README 计时 | 问题1只验证了开发目录现有 venv 能启动（evidence/q01.md §7）；尚无 repo 远端，无法 clone | **未验证** |
| A4 | App：Look + feel（10） | 好看易用：布局干净、按钮清晰，陌生人能自己摸会 | 蓝色视觉（AGENTS.md）；功能与证据优先（U-16） | `web/`：Discover 标签页（Q3） | 陌生用户/本人操作截图与问题记录 | `evidence/screenshots/q03_*.png`、`q06_*`（开发者截图；375 px 无横向溢出） | **未验证**（Q6 完成界面、窄屏、链接安全检查；真实键盘 Tab 顺序未查；尚无真人使用记录） |
| A5 | Report：Motivation + what's new（8） | 真实的人与问题；诚实对比现有产品；**证据：点名对比过的现有产品**（缺证据最多一半） | 对比 Yale-Localist、YaleConnect 及其他实际查过的服务；用户耗时只作回忆估计（U-14） | report.html §2–3（未创建） | 逐条核对对比结论可在对方产品公开页面复查 | `evidence/alternatives.md`（带状态、URL、核查时间，独立复核） | **未验证**（点名对比证据已具备；报告章节未写） |
| A6 | Report：Agent design（10） | 每个 agent 与工具讲清、架构图、组织方式；**证据：一次真实运行逐步追踪 + 各 agent 截图** | guard（模型）→ matcher（模型 agent，2 个只读工具）→ verifier（代码）；不为“多 agent”强行委派（I-15） | `app/orchestrator.py`、`app/domain/`、`evidence/architecture.md` | 目标领域真实运行 trace + UI 截图 | `evidence/q04_run/r_b79bfbda45ad.trace.json`、`evidence/screenshots/q04_real_run_r_b79bfbda45ad.png` | **未验证**（证据已具备；报告章节与图片版架构图未写） |
| A7 | Report：Tokenomics（8） | 单次、每用户每月、100 与 10,000 用户成本；省钱措施及是否变差；**证据：真实运行 token 数（日志或 app 内显示）**，纯估算减半 | 逐次记录 input/cached/cache-write/output/reasoning，缺失不记 0（M-03）；单价 M-06 | `app/llm.py`、`app/pricing.py`、`app/ledger.py`、`scripts/tokenomics.py` | 目标领域真实运行 → `runs/usage.jsonl` → `scripts/tokenomics.py` | 计量门槛已修复（q04 §1）；1 次真实运行的账本 `evidence/q04_run/r_b79bfbda45ad.usage.jsonl`；旧 `evidence/tokenomics.*` 属 Harbor Bikes | **未验证**（5 次真实运行；规模化成本与优化对照属 Q8） |
| A8 | Report：Safety（8） | 针对本 app 的真实风险，防御真的建出来；**证据：防御真实拦住攻击或故障的截图/测试**，只描述减半 | 网页/公告内容按不可信数据处理（M-04）；资格/日期/名额不得臆断（U-12）；花费与循环上限 | `app/safety.py`、`app/budget.py`、`app/agent.py` | 新领域攻击样例（如活动页内注入）与故障样例的测试/截图 | `evidence/q07.md`、`q07_redteam.json`、`screenshots/q07_app_input_screen_block_r_0e716bd1db78.jpg`；旧 `redteam_results.json` 只作历史 | **已验证通过**（应用自身拦截：网页输入筛查 $0 截图 + 真实运行中 LLM guard 拦截；间接注入被标记且未被推荐；正常对照通过；供应商过滤未发生，单独分类；局限见 q07 §4） |
| A9 | Report：Impact + metrics（5） | 可信数字 + 来源；诚实 limits；**证据：真实用户试过（引用、截图、前后耗时）**，纯猜测减半 | creator n=1 真实操作（U-15）；回忆估计不加总（U-14） | `evidence/real_use_log.md` | 真人操作记录、实测耗时、截图 | 无记录 | **等待真人输入** |
| A10 | Report：Design（2） | 好看、易读，截图和图表清晰且位置得当 | 图片 base64 内嵌（`scripts/inline_images.py`） | report.html（未创建） | 打印预览检查 | 无 | **未验证** |
| A11 | Slides：Content（6） | 几分钟讲清全故事：架构图、截图、关键数字 | 关键数字须能追溯到证据文件 | slides.html（未创建） | 逐页核对数字来源 | 无 | **未验证** |
| A12 | Slides：Design（2） | 大号可读文字、风格统一、视觉讲故事 | 与 app 一致的蓝色风格 | slides.html（未创建） | 双击打开 + 方向键逐页检查 | 无 | **未验证** |

## B. 基础能力子项（支撑 A2、A3、A7、A8；问题1核对）

| # | 子项 | 实现位置 | 验证方法 | 证据路径 / 版本 | 状态 |
|---|---|---|---|---|---|
| B1 | 模型锁定 gpt-6-luna（请求侧） | `app/config.py`、`app/llm.py` `build_request` | 审计 + 复核；离线测试 | evidence/q01.md §3.2 | **已验证通过** |
| B2 | SDK 环境变量不能改路由/头部 | `app/llm.py` 客户端构造 | `tests/test_metering.py` | q04 §1 | **已验证通过** |
| B3 | 两级 `.env`（repo → 上一级） | `app/config.py` | `tests/test_config.py`；实际启动显示 `.env (parent)` | q01 §6、§7 | **已验证通过**（空格 key 边角缺陷 F-08，失败即关闭） |
| B4 | 密钥隔离（API、前端、trace、账本、evidence） | `app/server.py`、`app/events.py`、`app/safety.py` | 全库字节扫描 + `/api/health` 实测 + 审计 | q01 §5 | **已验证通过** |
| B5 | usage 映射与计价（input/cached/cache-write/output） | `app/pricing.py`、`app/ledger.py` | 审计重算 133 条历史记录 0 差异；离线测试 | q01 §3.2 | **已验证通过** |
| B6 | 缺失 usage 不记 0 | `app/pricing.py`、`app/ledger.py` | `tests/test_metering.py` | q04 §1 | **已验证通过** |
| B7 | 所有调用入账（含失败、超时、重试） | `app/llm.py`、`app/metering.py` | `tests/test_metering.py` | q04 §1 | **已验证通过** |
| B8 | 预算/循环上限 | `app/budget.py`、`app/agent.py`、`app/server.py` | 离线测试 + 审计 | q01 §3.2 | **已验证通过**（缺每 run 模型调用次数上限 F-04，待修） |
| B9 | 运行追踪 trace | `app/events.py`、`runs/traces/` | 审计 + 历史 trace 结构检查 | q01 §3.1 | **已验证通过**（账本缺服务模型 F-05、真实/模拟标记 F-06） |
| B10 | 离线测试基线 | `tests/` | `pytest` | q01 §6：296 passed | **已验证通过** |
| B11 | 开发目录启动 | `run.py` | 预览服务器启动 + 端点检查 | q01 §7 | **已验证通过**（fresh clone 未验证） |

## C. 最终交付要求

| # | 交付要求 | 课程要求 | 实现选择 / 检查方法 | 实现位置 | 证据路径 / 版本 | 状态（问题1） |
|---|---|---|---|---|---|---|
| C1 | GitHub repo 链接（与 report §1 一致） | C-02、C-05 | 记录真实 URL | — | — | **等待真人输入**（P-02；当前仓库无提交、无远端） |
| C2 | repo 公开，或私有并加 `zlisto` 为 collaborator | C-02、C-07 | 记录可见性与邀请状态 | GitHub 设置 | — | **等待真人输入**（P-02） |
| C3 | 包含运行所需全部代码 | C-07 | fresh clone 后运行 | 整个 repo | — | **未验证** |
| C4 | README：app 是什么 + 逐步运行（或在线链接） | C-07 | 写给老师 10 分钟内跑起来 | `README.md` | evidence/q01.md §4 | **失败**（已检查：README 仍写占位领域并带 TODO） |
| C5 | `.env.example` 列出所需 key 名、无真实值 | C-07、C-12 | 只用 `PORTKEY_API_KEY`（I-04） | `.env.example` | evidence/q01.md §5（密钥扫描） | **已验证通过**（问题1：仅含空的 `PORTKEY_API_KEY=` 与注释；新增设置时需复查） |
| C6 | 不提交真实 `.env` / key | C-07、C-15 | `.gitignore` + 提交前扫描 | `.gitignore` | evidence/q01.md §5 | **已验证通过**（问题1：尚无提交；工作区与 `.git` 内未发现 key 值；推送前须复验） |
| C7 | `.env` 先找 repo 再找上一级；key 名完全一致 | C-12 | — | `app/config.py` | evidence/q01.md §5、§7 | 见 B 表 |
| C8 | 大数据集附小测试集与切换说明 | C-08 | 新领域固定快照小数据集（如需要） | `data/snapshots/`（Q2，真实采集快照 37 KB） | evidence/q02.md §5 | **未验证**（快照已提交并有测试；README 切换说明与应用读取尚未实现） |
| C9 | fresh clone dry run，10 分钟内可用 | C-11、C-13 | 新目录 + 上一级 `.env` + 按 README 计时 | — | — | **未验证** |
| C10 | report.html：10–15 letter 页、八节按序、图片内嵌、双击可开 | C-03、C-04、C-05 | 打印预览数页 | — | — | **未验证** |
| C11 | slides.html：≤10 页、reveal.js、图片内嵌、方向键检查 | C-03、C-06 | reveal.js CDN 并说明网络依赖（I-05） | — | — | **未验证** |
| C12 | 课程 key 只调 gpt-6-luna | C-09 | 代码锁定模型（M-01） | `app/config.py`、`app/llm.py` | 见 B 表 | 见 B 表 |
| C13 | token 成本来自真实运行（input / cached input / output） | C-16 | M-03 | 见 A7 | — | **未验证**（目标领域） |
| C14 | 至少一个安全防御真实生效的截图或测试 | C-05、C-16 | 新领域样例 | 见 A8 | `q07_app_input_screen_block_r_0e716bd1db78.jpg`、`r_6dff5fbf9fb4` | **已验证通过** |
| C15 | impact 数字有来源，最好有真实用户引用或截图 | C-16 | creator n=1 | 见 A9 | — | **等待真人输入** |
| C16 | Canvas 提交：repo 链接 + report.html + slides.html（+ 可选视频） | C-02 | 截止时区以 Canvas 为准（P-03） | Canvas | — | **等待真人输入** |
| C17 | demo 视频（可选） | C-02、C-14 | 只在本人录制后记录；不替代 C9 | — | — | **未验证**（可选） |
