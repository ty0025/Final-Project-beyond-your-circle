# PROGRESS — Beyond Your Circle

> 增量更新的进度与状态记录。需求基线见 PROJECT_SPEC.md；逐项评分状态见 evidence/rubric_checklist.md；每题证据见 evidence/qNN.md。
> 状态词：已验证通过 / 失败 / 未验证 / 等待真人输入。

最后更新：2026-10-26（问题8交接；A 等待真人输入）

## 1. 题目进度

| 题目 | 内容 | 状态 | 证据 |
|---|---|---|---|
| Q1 | 核对现有工程，固定评分与验收基线 | 已交接 | evidence/q01.md |
| Q2 | 有限公开来源采集，真实小样本 | 已交接 | evidence/q02.md |
| Q3 | 可浏览的基础发现流程（确定性，无模型） | 已交接 | evidence/q03.md |
| Q4 | 理解目的的 Agent 与领域工具（含计量门槛修复与首次真实运行） | 已交接 | evidence/q04.md |
| Q5 | 有依据的匹配、参与门槛与探索推荐 | 已交接 | evidence/q05.md、q05_cases.md、alternatives.md |
| Q6 | 最终用户操作流程（Find 页、条件、分组结果、失败恢复、运行详情折叠） | 已交接 | evidence/q06.md |
| Q7 | 安全与预算边界（采集 SSRF、恶意公告、显示安全、终止与计量、红队） | 已交接 | evidence/q07.md、q07_redteam.json |
| Q8 | 真实计量（B）、费率与规模成本（C）、fresh clone（D）；真人任务（A）已准备 | 已交接（A 等待真人输入） | evidence/q08.md、q08_tokenomics.*、q08_clone/ |
| Q9–Q10 | — | 未开始 | — |

## 2. 当前能力快照

| 能力 | 状态 | 依据 |
|---|---|---|
| 基础层离线测试 | 已验证通过 | 434 passed（Q7 后全量） |
| 开发目录启动、读取上一级 `.env` | 已验证通过 | q01 §7 |
| 密钥不外泄（工作区、`.git`、runs、evidence、采集原始页） | 已验证通过 | q02 §8（177 个文件 0 命中） |
| 两个不同来源的真实自动采集（CAW 摄影课程、YCGS 活动） | 已验证通过 | q02 §5–6；`data/snapshots/` |
| 采集失败回退 / 不抹除最后成功 | 已验证通过（仅模拟故障） | q02 §7；q03 §3（界面上的模拟断网） |
| 网页浏览真实记录（本周/后续/长期，ET 日期，出处链接，刷新与失败状态） | 已验证通过 | q03 §3–4，截图 6 张 |
| 目标领域的 AI 推荐（目的理解、匹配解释） | 已验证通过（5 次真实运行） | Q4 `r_b79bfbda45ad`；Q5 `r_8aad4fe5a302`、`r_c588d02ea0b5`、`r_835194ffb88a`；Q6 `r_ce638df7cf6e` |
| 最终用户流程：短输入 + 可选条件（SOM/参与方式/时间）→ 分组结果 → 打开出处；失败/取消/超时/预算可恢复 | 已验证通过（真实运行 1 次 + 模拟故障） | q06 §3–4；真实 Tab 键顺序、429 未验证 |
| 参与条件（服务端判定 match / check first / excluded）、事实出处、无来源细节删除 | 已验证通过 | q05 §1、§3；真实运行中未触发排除 |
| 计量门槛 F-01～F-08 | 已验证通过 | q04 §1，11 个测试；真实运行账本字段完整 |
| 新领域安全证据（应用自身拦截、红队、采集 SSRF、显示安全、时长上限） | 已验证通过 | q07 §2（真实 3 次 + 网页 1 次 + 47 个测试）；供应商过滤未发生 |
| 目标领域 tokenomics（真实 usage、费率核实、单次/每月/100/10,000 用户、优化对照） | 已验证通过 | q08 B/C；n=5，规模为情景估算，优化为同批数据计算对照 |
| fresh clone 10 分钟运行 | 已验证通过（本机） | q08 D：第 1 次因缺 httpx 失败，修复后第 2 次 clone → 可用约 49 s、首个 AI 结果约 2 min；GitHub clone 未验证（无远端） |

## 3. 持续传递的缺口（后续题目必须处理或明确保留）

| 编号 | 缺口 | 来源 | 影响 |
|---|---|---|---|
| G-01 | ~~计量门槛 F-01～F-08~~ Q4 已修复并测试 | q04 §1 | — |
| G-02 | ~~领域层、提示词、结果卡~~ Q4 已替换；~~红队样例仍是 Harbor~~ Q7 新增 `scripts/redteam_q7.py`（旧 `redteam.py` 保留为历史） | q07 | — |
| G-03 | ~~`ALLOW_DOMAINS`~~ Q4 已改为 yale.edu、creativeartsworkshop.org；卡片链接来自存储，不经模型输出 | q04 §2 | — |
| G-04 | ~~网页数据工具未标不可信~~ Q4 两个工具均为 `untrusted_output`；真实运行中未产生误报 | q04 §2 | — |
| G-05 | 运动/观赛兴趣尚无接入来源；社群类记录为 0（Q5 只用人工核对的案例记录做功能验证，不进入应用） | q02 §9、q05 §3 | Idea、It works 的覆盖面 |
| G-06 | ~~应用内没有刷新入口与来源状态展示~~ Q3 已解决（Discover 标签页） | q03 | — |
| G-10 | 真实数据中暂无“日期不明”“社群”“报名截止/已满”记录，这些展示只由合成测试验证 | q03 §6 | It works 的展示面 |
| G-07 | README/DESIGN 仍写占位领域，且“只有模型调用需要联网”在接入采集后将不成立 | q01 §3.2 | can run it、repo 质量 |
| G-08 | ~~仓库无提交~~ Q8 已本地提交（`eaf71fc`、`9a625b9`，未推送）；**仍无远端**；`.git` 归属另一账户，提交用单条命令 `-c safe.directory` | q08 D | 推送、GitHub URL（P-02） |
| G-11 | 问题5逻辑已知问题（冻结未改）：“Open to Yale students” 在未知身份时判为 met；规则未识别的资格文字不生成待确认条件（前端已展示原文） | q06 §8 | Safety/诚实性 |
| G-09 | 历史 Harbor Bikes 账本含 2 条缓存重放记录；`evidence/tokenomics.*`、`redteam_results.json` 不能用作本项目证据 | q01 §3.5 | Tokenomics、Safety（只能作历史） |

## 4. 等待用户补充（不阻塞独立工作）

| 编号 | 内容 | 状态 |
|---|---|---|
| ~~P-01~~ | 报告/slides 署名写法 | 用户已提供（2026-10-25）：**Tongyu David Chen**。报告与 slides 暂不开始写 |
| P-02 | 真实 GitHub repo URL、公开/私有、`zlisto` 访问状态 | 等待真人输入（用户：最后完成） |
| ~~P-03~~ | Canvas 显示的截止时区 | 用户表示不重要（2026-10-25）；按 2026-10-26 18:00 安排 |
| P-04 | creator n=1 真实操作记录 | 等待真人输入（用户：之后由 Claude 主动询问截图与原话） |
| P-05 | 是否允许把本仓库加入 git `safe.directory`（或其他修正 `.git` 归属的方式） | 等待真人输入（用户：之后自己更新该配置；Portkey key 已有） |
| ~~P-07~~ | events.yale.edu 的 robots.txt 禁止所有自动访问 | 用户确认不采集（2026-10-25） |

## 5. 模型调用累计（应用运行时）

| 题目 | 真实 gpt-6-luna 调用 | 说明 |
|---|---|---|
| Q1 | 0 | 只读核对与离线测试 |
| Q2 | 0 | 采集全部为确定性代码提取 |
| Q3 | 0 | 浏览与分组全部为确定性代码；界面刷新 1 次真实采集（无模型） |
| Q4 | 4（1 次运行） | `r_b79bfbda45ad`：guard 1 + matcher 3；9,325 tokens；$0.000926；账本 95 → 99 行 |
| Q8 | 4（fresh clone 中 1 次运行） | `r_af384cbce5e9` $0.001519，记在 clone 自己的账本（副本 `evidence/q08_clone/`）；本项目真实调用合计 32 行 $0.008269（正常 19 行 $0.004625 + 红队 9 行 $0.002125 + clone 4 行 $0.001519） |
| Q7 | 9（3 次红队运行，独立账本） | `r_0c89b3881d73` $0.001075、`r_6dff5fbf9fb4` $0.0000726、`r_7c9a61b04778` $0.000978；合计 $0.002125；`runs/redteam_q7/usage.jsonl` 9 行；正常账本仍 114 行；网页拦截演示 0 次调用 |
| Q6 | 4（1 次运行） | `r_ce638df7cf6e` $0.001309（guard 1 + matcher 3）；账本 110 → 114 行；演示服务器 0 行 |
| Q5 | 11（3 次运行） | `r_8aad4fe5a302` $0.000936、`r_c588d02ea0b5` $0.001075、`r_835194ffb88a` $0.000380；合计 $0.002390；账本 99 → 110 行 |
| 历史（问题1之前） | 账本 95 条 + 红队 38 条 | Harbor Bikes 占位领域，只作基础层历史（I-08） |

## 6. 变更日志

### Q1（2026-10-25）
- 新增：`PROJECT_SPEC.md`、`PROGRESS.md`、`AI_prompts.md`、`evidence/rubric_checklist.md`、`evidence/q01.md`、`evidence/real_use_log.md`。
- 未修改任何应用代码。

### Q2（2026-10-25）
- 新增：`app/collect/`（`__init__.py`、`htmltree.py`、`fetch.py`、`records.py`、`sources.py`、`store.py`）、`scripts/collect.py`、`data/snapshots/caw-photo.json`、`data/snapshots/ycgs-events.json`、`tests/test_collect.py`、`tests/fixtures/collect/*.html`（7 个裁剪的真实页面）、`evidence/q02.md`。
- 修改：`tests/conftest.py`（自动夹具 `no_real_network`）、`requirements.txt`（`tzdata>=2024.1`）、`PROJECT_SPEC.md`（I-10～I-12、P-07）、`evidence/rubric_checklist.md`、`AI_prompts.md`。
- 本机 venv 已安装 `tzdata 2026.5`。

### Q3（2026-10-25）
- 新增：`app/discover.py`、`web/discover.js`、`tests/test_discover.py`、`evidence/q03.md`、`evidence/screenshots/q03_*.png`（6 张）。
- 修改：`app/server.py`（`/api/discover`、`/api/sources`、`/api/refresh`）、`app/collect/fetch.py`（模拟断网传输；robots 不可达时报告真实错误）、`app/collect/store.py`（`simulated` 标记）、`app/orchestrator.py`（仅页眉标题/标语）、`web/index.html`、`web/styles.css`、`web/app.js`（1 行）、`../.claude/launch.json`（新增 outage 演示配置，不在仓库内）。

### Q4（2026-10-25）
- 新增：`app/metering.py`、`app/domain/verify.py`、`app/domain/prompts/matcher.md`、`tests/test_metering.py`、`tests/test_domain.py`、`evidence/architecture.md`、`evidence/q04.md`、`evidence/q04_run/`（trace 与账本副本）、`evidence/screenshots/q04_real_run_r_b79bfbda45ad.png`。
- 重写：`app/domain/__init__.py`、`models.py`、`tools.py`。
- 修改：`app/llm.py`、`app/pricing.py`、`app/ledger.py`、`app/budget.py`、`app/config.py`、`app/agent.py`、`app/safety.py`、`app/orchestrator.py`、`app/discover.py`（not_available 带 id）、`web/app.js`、`web/discover.js`、`web/index.html`、`web/styles.css`、`.env.example`、`tests/conftest.py`、`tests/test_ledger_budget.py`、`tests/test_server.py`、`tests/test_safety.py`、`tests/test_tools.py`。
- 删除：`app/domain/prompts/coordinator.md`、`researcher.md`、`verifier.md`；`data/sample/` 移到 `tests/fixtures/safety/`。

### Q8（2026-10-26）
- 新增：`scripts/tokenomics_q8.py`、`evidence/q08.md`、`evidence/q08_tokenomics.json/.md`、`evidence/q08_clone/`、`evidence/q08_clone_attempt1_start_log.txt`、`evidence/screenshots/q08_clone_*`（2 张）；`evidence/real_use_log.md` §D（真人任务与记录表）。
- 修改：`requirements.txt`（加 `httpx`，fresh clone 发现）。
- git：首次本地提交 `eaf71fc`，修复提交 `9a625b9`，未推送；`my-app/fresh-clone-q8`（失败）与 `fresh-clone-q8-2`（成功）为仓库外的测试目录，可删除。

### Q7（2026-10-26）
- 新增：`scripts/redteam_q7.py`、`tests/test_q7_safety.py`、`evidence/q07.md`、`evidence/q07_redteam.json`、`evidence/q07_redteam/`、`evidence/screenshots/q07_app_input_screen_block_*.jpg`。
- 修改：`app/collect/fetch.py`（畸形 URL 不再崩溃）、`app/config.py` + `app/orchestrator.py`（`RUN_TIMEOUT_S`、`n_failed_attempts`）、`app/server.py`（CSP `script-src 'self'`）、`web/app.js`（文案）、`tests/conftest.py`（环境隔离）。

### Q6（2026-10-25/26）
- 新增：`tests/test_flow.py`、`evidence/q06.md`、`evidence/q06_run/`、`evidence/screenshots/q06_*`（6 张）。
- 修改：`app/domain/models.py`（RunOptions）、`conditions.py`（effective_understood、“you told us”）、`verify.py`（分组/来源/also_read/可打开的剔除项）、`app/orchestrator.py`、`app/server.py`、`app/llm.py`（SimulatedFailureLLM）、`app/config.py`（每日预算可为 0）、`app/safety.py`（模拟标签）、`web/index.html`、`web/app.js`、`web/discover.js`、`web/styles.css`；`../.claude/launch.json`（8772/8773，8771 加模拟失败）。
- 撤回：复审建议的问题5判定逻辑修改（冻结规则），记为 G-11。

### Q5（2026-10-25）
- 新增：`app/domain/conditions.py`、`scripts/compare_cases.py`、`tests/test_cases.py`、`tests/fixtures/cases/`（`manual_cases.py`、`specs.py`）、`evidence/q05.md`、`evidence/q05_cases.md`、`evidence/q05_cases.json`、`evidence/alternatives.md`、`evidence/q05_runs/`、`evidence/screenshots/q05_*.png`（3 张）。
- 修改：`app/domain/models.py`、`verify.py`、`tools.py`、`prompts/matcher.md`、`app/orchestrator.py`、`app/discover.py`（URL + 标题去重、报名日期范围、截止年份）、`web/app.js`、`web/styles.css`、`tests/test_domain.py`。

## 7. 非阻塞待办（按价值安排）

- 第三来源：Yale Campus Recreation 研究生/专业学院校内联赛（补“运动”兴趣）；NHCC 摄影俱乐部 Atom feed（补摄影社群）。
- YCGS 描述中的叙述性地点（如 “at the Yale Peabody Museum”）目前保持未知；如需提取，应由后续带证据的提取步骤处理并标为待确认。
- 本周窗口采用“今天起 7 天”（I-13）；如用户更想要自然周，可改为周一到周日。
- ~~verifier 不改写模型 summary~~ Q6：界面在 AI 摘要前显示代码统计，并标注摘要未经代码核对。
- 提示词调优候选：模型把“go back regularly”推断成 `when=ongoing`；只读了 1 个 listing。等有多次真实运行再决定是否调整（避免为单次现象改动）。
- ~~timeline 中 `verification` 事件用通用样式~~ Q6 已加专门显示。
- `HEAD /` 返回 405（仅影响探活工具）；DESIGN.md 浏览器延迟描述轻微过时。
- 新对话只读核对（2026-10-25）发现、尚未处理：① `scripts/tokenomics.py` 默认读整份 `runs/usage.jsonl`（95 行 Harbor 历史 + 15 行新领域），不按 mode/run 过滤，且把 null usage/费用当 0（第 68、70 行），直接运行会混入历史并覆盖 `evidence/tokenomics.*`；② 本文件 §2 tokenomics 行、rubric A2/A7（“1 次真实运行”）、B3/B8/B9/B10、C8 与 PROJECT_SPEC §6 的状态停在 Q4 或更早；③ `evidence/architecture.md` 仍写 `watch_out`，缺 Q5 的服务端 match / check first / excluded 判定；④ `app/config.py:120` 与 `.env.example:31` 的 `data/sample` 默认值已失效（无代码引用）；⑤ `app/safety.py:552` guard 提示仍写 “help-desk”；⑥ `web/index.html` 静态标题为 “Agent Workbench”（运行时由 app.js 替换）。
