# campaign.json 体检报告

> 对照 `pipeline-guide` 的审查清单，对 `assets/resource/pipeline/campaign.json` 做静态审计。
> 审计日期：2026-11-24　审计对象：46 个节点 / 991 行　**本报告不修改任何代码**。
> 规范来源：`~/.dsh/skills/pipeline-guide/SKILL.md` + `field_reference.md`。
>
> **2026-11-24 更新**：第五节第 1、3 项已修复（见文末「修复记录」）。本文全部数据为**修复前基线**，用于对照。

## 一、结论速览

| 指标 | 数值 |
| --- | --- |
| 节点总数 | 46（base 18 / `_550` 14 / `_1080` 14） |
| 真识别节点 | **9**（TemplateMatch：3 组胜负指示 + 3 组推荐阵容） |
| 默认 DirectHit 节点 | **37**（省略 `recognition` = 不看画面直接执行） |
| Click 动作 | 24（其中 **21 个**是"盲点 + 只有一个后继"） |
| 显式设置 `rate_limit` | **0**（全部继承默认 1000 ms） |
| 显式设置 `pre_delay` | **0**（全部继承默认 200 ms） |
| `next` 长度 ≥ 2 的节点 | **0**（长度分布：0 个后继 14 个，1 个后继 32 个） |
| 有 `on_error` 的节点 | 12 |
| 主链固定等待 | **10.1 秒**（不含识别、不含战斗本身） |

一句话：**这是一条"盲点为主、单一后继、靠固定延迟推进"的链路**，与 `pipeline-guide` 的"识别→操作→识别"核心原则正好相反。

## 二、逐条对照审查清单

| # | 清单项 | 结论 | 依据 |
| --- | --- | --- | --- |
| 1 | 字段名拼写、类型合法 | ✅ | `python tools/check_pipeline.py` 通过；46 个节点均有 `$__mpe_code` 位置 |
| 2 | 无不必要的 `pre_delay` / `post_delay` / `timeout` | ❌ | 31 个节点显式 `post_delay`（最高 2500 ms）；另有 15 个继承默认 200 ms；主链合计 10.1 s |
| 3 | `next` 覆盖所有可能画面（弹窗/加载/异常） | ❌ | 没有一条 `next` 有 2 个以上候选，全部是"唯一后继" |
| 4 | 每次点击后有识别验证 | ❌ | 21 个盲点点击中只有 `OpenRecommended` 之后有识别；`UseFormation → StartBattle` 是连续两次盲点 |
| 5 | ROI / target 基于统一基准 | ⚠️ | 项目用 720×1280 竖屏（与 guide 举例的 1280×720 方向相反，但内部自洽）；`_1080` 那套是手录，无换算一致性 |
| 6 | JSON 格式化 | ✅ | 4 空格缩进、LF 行尾，符合 `.gitattributes` / `.prettierrc` |
| 7 | `locales/` 多语言 | N/A | 全项目无 OCR 节点 |
| 8 | OCR `expected` 写完整文本 | N/A | 同上 |
| 9 | 优先用中间节点，避免重复点击 | ⚠️ | `StartBattle` 用了 `repeat: 3`（同坐标连点三次），正是 guide 警告的"重复点击可能作用于下一界面的其他元素" |
| 10 | 不引用内部节点 | N/A | 无 `__` 前缀节点 |

## 三、重点问题

### P0-1　没有回退链：`next` 全部是单后继

- 数据：`next` 长度分布 = 0 个后继 14 个节点 / 1 个后继 32 个节点 / ≥2 个 **0** 个节点。
- 影响：`pipeline-guide` 要求"扩充 next 列表，覆盖当前操作后所有可能画面，力争一次截图命中"。现在的写法里，任何一次识别偏差都没有第二候选，只能落到 `on_error`（而 46 个节点中只有 12 个有）。
- 建议：入口类节点（`CampaignPhantomEntry` / `CampaignNormalEntry` / `OpenRecommended`）的 `next` 扩成"目标 + `[JumpBack]` 回退 + `[JumpBack]` 弹窗/加载处理"三元组。

### P0-2　主链 10.1 秒固定等待

| 节点 | `pre_delay` | `post_delay` | `repeat` 额外 | 小计 |
| --- | --- | --- | --- | --- |
| CampaignPhantomEntry | 200（默认） | 2500 | 0 | 2700 |
| OpenRecommended | 200 | 2000 | 0 | 2200 |
| TryFormation | 200 | 200（默认） | 0 | 400 |
| UseFormation | 200 | 1000 | 0 | 1200 |
| StartBattle | 200 | 2000 | 1000（3 次点击间隔） | 3200 |
| WaitBattleEnd | 200 | 200（默认） | 0 | 400 |
| **合计** | | | | **10 100 ms** |

- 这还只是"一个阵容的一次尝试"。`campaign_state` 允许 10 个阵容 × 2 种关卡类型，全部失败再整轮重试。
- `post_delay` 分布：2500 ms × 6、2000 ms × 9、1500 ms × 3、1000 ms × 6、800 ms × 6、500 ms × 1。
- 建议：这些等待本质上是在"等画面切换"，属于 guide 说的"应该用识别节点解决，而不是延迟"。可改为 `post_wait_freezes`（等画面稳定）或直接在 `next` 里放目标节点的识别。

### P0-3　盲点链：点完不验证

- 21 个节点同时满足「默认 DirectHit」+「Click」+「唯一后继」，其中包括 `UseFormation → StartBattle` 这样的连续盲点段。
- 真机日志已经证明后果：`CampaignPhantomEntry` 一次点击坐标失效 → `Actuator::click failed to get target rect` → `PipelineTask node not completed` → `Tasker.Task.Failed`，整个任务 3 秒内结束。
- 建议：至少把"再次战斗（RETRY_BUTTON）/ 使用阵容（UseFormation）/ 开始战斗（StartBattle）"三处改为模板识别定位（识别到按钮再点，`target: true` 或指向识别节点），彻底摆脱坐标依赖。

### P1-1　默认 `rate_limit: 1000` 未显式清零

- 46 个节点没有一个设置 `rate_limit`，全部继承 1000 ms。
- 后果：`next` 识别不中时，以 1 秒/次的节奏重试；配合默认 `timeout: 20000`，单个节点最坏会白等 20 秒才走 `on_error`。
- 建议：对确认"点完就该切界面"的节点显式写 `rate_limit: 0`、`pre_delay: 0`；`post_delay` 按实际需要保留。注意 `rate_limit: 0` 会让失败重试变成高频轮询，需真机看 CPU 与响应。

### P1-2　`StartBattle` 的 `repeat: 3`

- 三套分辨率各有一个 `repeat: 3` + `repeat_delay: 500` 的开始战斗节点。
- guide 明确提醒：不要对同一按钮重复点击，第二次点击可能落在下一界面的别的元素上。
- 建议：`repeat` 改回 1，用 `next` 里的重试链（配合 `max_hit`）代替连点。

### P1-3　终端节点语义藏在 Python 里

- `next` 为空的 14 个节点中，`WaitBattleEnd` / `HandleVictory` / `CampaignRecover` 是"静态图里是终点、实际流向由 `override_next` 决定"。
- 后果：JSON 静态看不出流程图；接手的人（或下一个 agent）必须读 `my_action.py` 才知道走向。
- 建议（推荐做法）：把"等战斗结束"交给框架的识别循环——`WaitBattleEnd` 的 `next` 写成 `["HandleVictory", "HandleDefeat"]`，让这两个节点各自带 `VictoryIndicator` / `DefeatIndicator` 识别并把 `timeout` 设到 300000，就可以完全删掉 `WaitForBattleEnd` 里的 Python 轮询（也顺手解决"轮询间隔 3 秒"这个硬编码）。

### P2　跨分辨率一致性与重复维护

- `_1080` 坐标与 base 之间没有可复现的映射：同为 `y=1071` 的两个节点，在 `_1080` 下分别是 `916` 和 `911`（手录试错痕迹）。
- 一套流程手工三份（18 + 14 + 14），改一处要同步三处；目前只有 `tools/check_pipeline.py` 做"成对存在 + 越界"的结构性检查，查不出坐标含义漂移。
- 建议：短期靠检查脚本兜住"漏改/越界"，中期考虑单源 + 生成（但必须先有真机校准数据，否则自动缩放会静默改变现有行为）。

## 四、已经达标的项

- `on_error → CampaignRecover`（12 个关键节点）：这是本仓库目前唯一符合 guide "失败要有兜底"精神的部分。
- `tools/check_pipeline.py`：覆盖了"引用存在性、分辨率成对、坐标越界、模板存在"，属于 guide 审查清单第 1 条的自动化落地。

## 五、建议的修复顺序

| 顺序 | 动作 | 风险 | 收益 |
| --- | --- | --- | --- |
| 1 | 全节点显式 `rate_limit: 0` / `pre_delay: 0`，`post_delay` 按需下调 | 低（只影响等待） | 主链可省约 10×200 ms，失败重试更快 |
| 2 | `StartBattle` 去掉 `repeat: 3`，改 `next` 重试 | 低 | 消除 guide 点名的重复点击隐患 |
| 3 | `WaitBattleEnd` 的轮询改由 `next` + 识别 + `timeout` 承担 | 中（要改 3 个节点的 next 与识别） | 删掉 Python 轮询，静态图完整 |
| 4 | `UseFormation` / `StartBattle` / `RETRY_BUTTON` 改模板识别 | 中（要裁模板图） | 从"盲点"变"识别驱动"，直击当前主要失败模式 |
| 5 | 入口节点扩 `next` 回退链（`[JumpBack]`） | 中 | 点偏不再整链失败 |

> 说明：本报告只做静态审计，未在真机上验证任何改动效果。第 3~5 项建议先在 720×1280 真机上做单点验证，再推全流程。

---

## 六、修复记录（2026-11-24，只做"不需要截图"的部分）

### 已完成

| 项 | 改动 | 覆盖范围 |
| --- | --- | --- |
| 第五节 1 | 所有节点显式 `pre_delay: 0`、`rate_limit: 200` | 46 个节点 |
| 第五节 3 | `WaitBattleEnd`（×3）由 Custom 轮询动作改为「next 识别循环」：`next=[VictoryIndicator, DefeatIndicator]`、`timeout: 300000`、`rate_limit: 3000`、`on_error: [CampaignStop]`；同时删除 `agent/my_action.py` 里的 `WaitForBattleEnd` 自定义动作（约 40 行） | 3 个等待节点 + 1 个 Python 类 |
| 配套 | `VictoryIndicator` / `DefeatIndicator`（×3）补 `next` → 对应 `HandleVictory` / `HandleDefeat` | 6 个节点 |

**关于 `rate_limit: 200` 而不是 guide 建议的 0**：0 会让"识别不中"时的重试变成满速截图循环（本机截图约 49 ms/次），失败路径上每秒会打二十多张图；200 ms 已经把默认的 1 秒等待压到 1/5，又不至于把截图打满。这是对 guide 的**有意偏离**，已在此记录。

**效果（静态推算）**

- 主链固定等待：`10 100 ms → 8 700 ms`（省掉 6 次 `pre_delay` 200 ms 与等待节点自身的 200 ms）。
- 识别不中时的重试节奏：`1000 ms/次 → 200 ms/次`（同 20 s 超时下，最坏重试次数从 20 次升到 100 次，属预期）。
- 战斗结算等待：由 Python 每 3 秒轮询、最多 100 次，变成框架按 `rate_limit: 3000` 轮询、最多 100 次——节奏一致，但少了一个自定义动作，且流程图在 JSON 里完整可见。

### 暂缓：第五节第 2 项（`StartBattle` 的 `repeat: 3`）

复核后**推翻我自己在报告里的"低风险"判断**：`repeat: 3` 不是随手写的冗余，而是盲点点击之间唯一的重试手段——`UseFormation` 点完就切界面，`StartBattle` 只能靠"连点 3 次、间隔 500 ms"提高命中率。在没有识别节点之前删掉它，会把出手成功率往下压。

结论：这项应该和第 4 项（按钮模板识别）一起做，届时 `repeat` 可以直接删、改用 `next` 重试链 + `max_hit`。

### 待真机验证

1. `WaitBattleEnd` 的 `timeout: 300000` 是否覆盖最长战斗（含 5 分钟以上的挂机关）。
2. `rate_limit: 3000` 在该节点上的实际节奏是否符合"3 秒看一眼"的预期（若框架把它当作别处的限流，实际可能是 1 秒一轮——不影响正确性，只影响 CPU 与识别次数）。
3. 胜负识别命中后是否立即进入 `HandleVictory` / `HandleDefeat`（`VictoryIndicator` 的 `timeout: 1000` 只约束它自己到 `HandleVictory` 的那一跳，`HandleVictory` 是 DirectHit，应立即命中）。

### 仍未解决（等截图/真机）

- 第五节第 4 项：`UseFormation` / `StartBattle` / 重试按钮改模板识别——**已在第七节做完**（真机试点）。
- 第五节第 5 项：入口节点扩 `[JumpBack]` 回退链（需回退与弹窗节点）。
- 主链里 `post_delay: 2500/2000/1000` 在改造前**是承重结构**，不能单独下调；现在 `StartBattle` / `UseFormation` / `BattleRetry` 已有识别兜底，只剩入口那两跳还在靠转场等待。

## 七、真机试点：把盲点点击换成模板识别

### 7.1 这次能做的前提（环境侧，先说清楚）

游戏是 **High 完整性**进程，而 MaaFramework / 我们这边的合成输入都要过 UIPI。实测结论：**MFAAvalonia 必须以管理员身份运行**，否则表现为"识别到了、点了没反应、日志里也没有报错"。本次试点是在 windows-mcp（管理员 DSH 下的独立进程）里点鼠标验证的，链路为：

```
主城 → 点「先锋关卡 666」→ 赛季挂机关卡界面 → 点「幻灵挑战」/「挑战」→ 编队准备界面
```

客户区正好 720×1280（窗口 742×1336），**与 pipeline 基准 1:1**，所以截图坐标 = 客户区坐标，不需要缩放换算。这一点是本次能做模板识别的基础，之前的 1280×720 云游戏窗口做不到。

### 7.2 真实界面和 pipeline 假设的对照

| 节点 | pipeline 假设 | 真实界面（2026-11 版本） |
|---|---|---|
| `CampaignPhantomEntry` / `CampaignNormalEntry` | (190,1071) / (551,1071) 盲点 | ✅ 对得上：「幻灵挑战」/「挑战」正好在这两个位置 |
| `StartBattle` | (607,1193) 盲点、`repeat: 3` | ✅ 位置对得上：绿色「战斗」按钮；但不需要 `repeat` |
| `OpenRecommended` | ROI `[111,1128,178,135]` 里点「推荐阵容」 | ⚠️ 是同一个按钮，但文案改成了「**通关阵容**」；点它弹出推荐阵容面板 |
| `UseFormation` | (424,1054) 点「使用阵容」 | ✅ 对得上：那个位置是弹窗里的「**一键采用**」；准备界面上没有它，只有弹窗里有 |

结论：**这条三段链本身是对的**，变的只是按钮文案——`推荐阵容` → `通关阵容`、`使用阵容` → `一键采用`，箭头仍是弹窗右侧那个圆形 ▶（最多翻到第 10 个推荐阵容）。所以这一节最初那版"链路不成立"的判断是错的，已按实测更正。


### 7.3 已落地：三处盲点点击改成模板识别

四个模板（全部 `tools/make_template.py` 裁的，都在 `assets/resource/image/`）：

| 模板 | 尺寸 | 客户区位置 | 用途 |
|---|---|---|---|
| `clearance_formation_720p.png` | 162×118 | (120,1138)–(282,1256) | 准备界面「通关阵容」按钮 → `OpenRecommended` |
| `recommended_apply_720p.png` | 280×102 | (250,998)–(530,1100) | 弹窗「一键采用」按钮 → `RecommendedPanel` / `UseFormation` |
| `recommended_next_720p.png` | 50×54 | (642,650)–(692,704) | 弹窗右侧 ▶ 箭头（`TryFormation` 的落点校验用，见下） |
| `battle_button_720p.png` | 154×74 | (532,1158)–(686,1232) | 准备界面绿色「战斗」按钮 → `StartBattle` |
| `retry_button_720p.png` | 370×85 | (330,1160)–(700,1245) | 战败弹窗绿色「再次挑战」按钮 → `BattleRetry` |
| `victory_challenge_720p.png` | 190×57 | (500,1168)–(690,1225) | 胜利结算页右下角绿色「挑战」按钮 → `VictoryChallenge`（点它直接进下一关） |
| `phantom_challenge_720p.png` | 160×50 | (140,1103)–(300,1153) | 关卡选择页左侧「幻灵挑战」按钮 → `CampaignPhantomEntry` |
| `normal_challenge_720p.png` | 120×50 | (450,1103)–(570,1153) | 关卡选择页右侧「挑战」按钮 → `CampaignNormalEntry` |
| `town_stage_entry_720p.png` | 40×30 | (118,1230)–(158,1260) | 主界面左下角「先锋关卡」里的「关卡」二字 → `CampaignTownEntry` |

交叉验证（同一套 UI 静态资源，跨截图应当像素级一致；"不该命中"用来确认不误报）：

| 模板 | 同界面另一张 | 不该命中的界面 |
|---|---|---|
| `battle_button_720p` | 1.0000 | 关卡界面 0.3232 / 主城底栏 0.5091 |
| `clearance_formation_720p` | 1.0000 | 主城底栏 0.2201 / 关卡界面 0.4305 |
| `recommended_apply_720p` | 1.0000 | 弹窗底缘 0.5003 |
| `recommended_next_720p` | 1.0000 | — |
| `retry_button_720p` | 1.0000（另一次独立截图） | 关卡选择界面底栏 0.1363 |
| `victory_challenge_720p` | 1.0000（ROI 内 NCC 复算，落点 client (500,1168)） | 下一关准备界面底栏 0.5308 |
| `phantom_challenge_720p` | 1.0000 | 主城底栏 0.3639；右侧「挑战」按钮区 0.1701 |
| `normal_challenge_720p` | 1.0000 | 主城底栏 0.3778；左侧「幻灵挑战」按钮区 0.1490 |
| `town_stage_entry_720p` | 1.0000 | 关卡选择页底栏 0.2865 |

顺带一个发现：旧的 `Recommended_720p.png` 在这块按钮上还能打到 **0.9681**（默认阈值 0.8 就能过），所以它不是"完全失效"，而是"一直在凑合"——新版模板是 1.0000。旧文件现在没有节点引用了，`_550` / `_1080` 变体仍在用旧图。

节点改动：

- `OpenRecommended`：`TemplateMatch(clearance_formation_720p)` + Click，`next` → `RecommendedPanel`；旧模板 `Recommended_720p.png` 换掉。
- **新增 `RecommendedPanel`**：`TemplateMatch(recommended_apply_720p)` + `DoNothing`，`next` → `TryFormation`，`on_error` → `CampaignRecover`。它的作用是**给后面那串 Python 盲点翻身做守卫**——弹窗没打开就不许点箭头。
- `UseFormation`：`TemplateMatch(recommended_apply_720p)` + Click，`post_delay` 1000 → 300（弹出窗关掉后 `StartBattle` 会自己等按钮出现）。
- `StartBattle`：`TemplateMatch(battle_button_720p)` + Click，删 `repeat: 3` / `repeat_delay: 500`，`post_delay` 2000 → 1000。
- **新增 `BattleRetry`**：`TemplateMatch(retry_button_720p)` + Click，`next` → `OpenRecommended`，`on_error` → `CampaignRecover`。战败弹窗上那颗绿色按钮的实际文案是「**再次挑战**」（不是「再次战斗」），旧代码的 `RETRY_BUTTON` 盲点坐标 (511,1207) 换成这条链路。
  - 配套改了 `agent/my_action.py`：`CampaignNextFormation` 在"换下一个阵容"分支不再自己 `_click("RETRY_BUTTON")`，改为 `override_next(["BattleRetry"])`，把点击交给 pipeline。
- `BattleRetry_550` / `BattleRetry_1080`：这两个分辨率没有模板，保留原来的盲点坐标（(395,933) / (1197,1024)，与 `coords.py` 一致）作为兜底，行为与改造前相同。
- 所有 Click **都不写 `target`**——不写时框架点识别框中心，正好是按钮中心。

真机验证（这四个点击点我都按"模板中心"实点过一遍）：点「通关阵容」弹窗打开 ✓、点 ▶ 推荐阵容从「七七四十九」翻到「姜撞大菠萝」✓、点「一键采用」弹窗关闭且阵容生效 ✓。只剩「战斗」没实点（会真开打，留给你跑）。

`_550` / `_1080` 变体**未动**：本机只有 720p 现场，没有那两个分辨率的截图，凭猜写模板比盲点更危险。


### 7.4 顺带补的工具：`tools/make_template.py`

以前模板是"从编辑器截图里手抠"，尺寸和内容都靠眼睛。现在固定成三步：

```bash
python tools/make_template.py 截图.png --crop 532,1158,686,1232 --name battle_button_720p \
    --verify 另一张同界面.png --verify 不该命中的界面.png
```

裁 → 存进 `assets/resource/image/` → 打印每张验证图的最高分与位置。只依赖 numpy + Pillow（不需要 opencv）。这次的两个模板就是它裁的。

### 7.5 还剩下的盲点

1. **`TryFormation` 里的 ▶ 点击仍是 Python 按坐标点**（`coords.RIGHT_ARROW = (658,682)`，实测箭头圆心 (667,677)，都在按钮内）。它要按阵容序号点 N-1 次，次数是动态的，pipeline 的 `repeat` 表达不了，所以留在 Python；但现在前面有 `RecommendedPanel` 兜底、后面有 `UseFormation` 兜底，点空的后果从"整轮崩"降成"多翻一页/走恢复"。它的模板 `recommended_next_720p.png` 已经裁好放进 `assets/resource/image/` 了，哪天要改成"先识别再点"，素材是现成的。
2. **`_550` / `_1080` 两套节点还是盲点**（含刚加的 `BattleRetry_550` / `BattleRetry_1080`），等有那两个分辨率的机器再补模板。
3. 观察记录（留给后续决策）：准备界面上有游戏自带的「**自动挑战**」，关卡界面右侧还有「**连续代理**」。如果这两个能连续自动打，pipeline 也许只该负责"什么时候该换阵容"，重复战斗交给游戏自己。

### 7.6 真机第一轮跑通后暴露的两个流程问题

第一次完整跑通（模板加载修好之后）拿到两个真实问题，都不是识别问题：

| 现象 | 根因 | 处理 |
|---|---|---|
| 模板一直报 `templates or threshold is empty` | MPE 用**相对路径**加载 bundle（`path=.`），模板按进程 cwd 解析；加载资源和识别时 cwd 不一样，`./image/*.png` 全部落空（源码里路径不存在是静默 `continue`） | 建目录 junction 把 `image/` 放到两个可能 cwd 下（`/image`、`assets/image`），临时方案，见 7.6 说明 |
| 战斗胜利后直接回主页面，不继续下一关 | `CampaignResetFormation` 里盲点 `NEXT_BUTTON` (494,1210)，在当前版本结算页上不是「下一关」 | 删掉这次点击；新增 `VictoryChallenge` 节点识别结算页右下角的「挑战」按钮（`victory_challenge_720p.png`）并点它，直接进下一关的准备界面 |

**关于 junction**：这是绕开 MPE"相对路径 + cwd 漂移"的权宜之计。等确认 cwd 稳定在哪一层之后，只保留对应的那一个 junction；根治要在 MPE 侧用绝对路径加载 bundle，或在 agent 启动时 `os.chdir()` 到固定目录（当前 `agent/main.py` 已经 chdir 到仓库根，但资源加载发生在 MPE 主进程里，所以管不到它）。

### 7.7 硬约束：agent 自定义动作有 5 秒响应超时

第一版"等结算 6 秒"是写在 Python 里 `time.sleep(6)` 的，结果整轮任务在胜利那一刻失败：

```
09:18:21.855 AgentClient::action_agent  [node_name=HandleVictory] [custom_action=CampaignResetFormation]
09:18:26.863 WRN Transceiver::poll socket is not alive [elapsed=5002ms] [timeout_=5000ms]
09:18:26.863 ERR Transceiver::recv recv canceled
09:18:26.863 ERR AgentClient::action_agent failed to send_and_recv [req_id=21]
09:18:26.864 Node.Action.Failed → 09:18:28.872 Tasker.Task.Failed
```

框架侧等 agent 回包的上限是 **5000 ms**，超过就判 `socket is not alive`、节点失败；之后迟到的 `override_next` 打到已销毁的 context（`context not found [context_id=...]`）。

**规则**：任何自定义动作/识别里都不能做长时间等待，等待要放在节点字段里（框架侧计时，没有这个上限）。

**最终采用的等待布局**（用户指出"胜利后等 6 秒没有意义"）：

| 节点 | 字段 | 值 | 理由 |
|---|---|---|---|
| `HandleVictory` ×3 | `post_delay` | 1000 | 胜利后不需要空等，`VictoryChallenge` 自己会一直识别「挑战」 |
| `VictoryChallenge` | `post_delay` | 500 | 点完挑战给画面一点切换时间 |
| `OpenRecommended` ×3 | `pre_delay` | **1500** | **进入关卡有入场动画，动画期间「通关阵容」能被识别到但点不动**——`pre_delay` 的语义正是"识别到后、执行动作前的延迟" |

`CampaignFormationSelect` 的翻页间隔也从 0.5 s 压到 0.4 s（翻到第 10 个阵容时 9 次点击 ≈ 4.1 s，仍在 5 s 内）。

> 更精确的做法是 `pre_wait_freezes`（等到画面静止再动作，自适应动画时长），但它的对象格式本项目还没验证过，先用固定 `pre_delay` 稳妥；1500 ms 不够时再换。

### 7.8 入口也换成模板识别，并支持两个起始页面

原来入口是全套盲点：(190,1071) 点幻灵挑战、(551,1071) 点挑战。现在三处入口都改成识别后点：

| 节点 | 识别 | 动作 | 之后 |
|---|---|---|---|
| `CampaignTownEntry`（新） | 主界面左下角「先锋关卡」里的「关卡」二字，ROI `[60,1170,200,110]` | Click 识别框中心 | → `CampaignPhantomEntry` / `CampaignNormalEntry`（按模式） |
| `CampaignPhantomEntry` | 「幻灵挑战」按钮，ROI `[60,1020,340,140]` | Click | → `OpenRecommended` |
| `CampaignNormalEntry` | 「挑战」按钮，ROI `[420,1020,300,140]` | Click | → `OpenRecommended` |

**两种起始页面怎么同时支持**：靠 `next` 的**候选列表**，不是 `on_error` 回退。`CampaignInit` 在运行时把 `AutoCampaign` 的 `next` 改写成 `[CampaignTownEntry, 入口节点]`：

- 从主界面开始：`CampaignTownEntry` 认出「关卡」→ 点它进关卡页 → 它自己的 `next` 走入口节点；
- 已经在关卡页：`CampaignTownEntry` 认不到（实测该页底栏相关度只有 0.2865）→ 框架在**同一轮**里接着试入口节点。

**这里踩过一个坑（值得记住）**：第一版把"已在关卡页"的回退写在 `CampaignTownEntry.on_error` 里，用户实测"从关卡页开始没有反应"。原因是——**经过 `next` 进入的节点识别失败时，框架不会执行它自己的 `on_error`**，只会把整个候选列表一轮轮重试，直到父节点超时（默认 20 s）。日志里就是每秒五次的 `recognize_list [list=[CampaignTownEntry]]` 反复出现。所以跨页面分派必须用候选列表，`on_error` 只用于"真正失败后的兜底"。

两点设计取舍：

1. **「关卡」只裁两个字**（40×30）——按用户说明，前面的字/数字会变（`先锋关卡 676` 的编号每天在涨），只留稳定部分。靠 ROI 把它锁在左下角那块区域，避免匹配到「赛季挂机关卡」标题里的"关卡"。
2. **「挑战」模板不能和胜利结算页那颗混用**：结算页的「挑战」在 y 1168~1225，关卡页的在 y 1103~1153，靠 ROI 的 y 区间（1020~1160 vs 1120~1280）天然隔开，不互相误伤。

`_550` / `_1080` 三套入口节点仍保留原来的盲点坐标——那两个分辨率没有模板，等有机器再说。

### 7.9 点击没生效就再点的重试链（试点）

需求：每个按钮点完之后，如果画面没有变化，就再点一次，最多重复两次。

先明确一点：**maafw 没有"前后帧差分"的原语**。`post_wait_freezes` 是"等画面停止变化"，而点击没生效时画面本来就静止，它会立刻返回"稳定"，不会告诉你这次点击没生效。所以"是否生效"只能落在**下一屏能不能被认出来**上——这也正是本项目一直在用的思路。

**为什么不用 `max_hit` 限次**：`max_hit` 是"该节点在一次任务里最多命中几次"，而我们的流程是**一个任务里无限循环推关**，`OpenRecommended` 每过一关就要命中一次，设 `max_hit: 3` 会在第 3 关之后把它永久跳过。所以次数上限只能用"镜像节点"显式串成链。

试点两个节点（都是"点完应当立刻换屏"的）：

| 节点 | 动作 | `timeout`（给下一屏多久） | `next`（下一屏锚点） | `on_error`（再点一次） |
|---|---|---|---|---|
| `OpenRecommended` | 点「通关阵容」 | 2000 | `RecommendedPanel`（弹窗里的「一键采用」） | `OpenRecommendedRetry1` |
| `OpenRecommendedRetry1` | 同上 | 2000 | 同上 | `OpenRecommendedRetry2` |
| `OpenRecommendedRetry2` | 同上 | 2000 | 同上 | `CampaignRecover` |
| `UseFormation` | 点「一键采用」 | 2000 | `StartBattle`（弹窗关掉后会露出「战斗」） | `UseFormationRetry1` |
| `UseFormationRetry1` | 同上 | 2000 | 同上 | `UseFormationRetry2` |
| `UseFormationRetry2` | 同上 | 2000 | 同上 | `StartBattle`（让它自己认一次，认不出它走 Recover） |

代价与副作用：

- 正常路径**不受影响**：锚点一出现就继续，重试节点根本不执行。
- 失败一次多花约 2.5 s（重试节点的 `post_delay: 500` + `timeout: 2000`）。
- `OpenRecommended` 若误判重试，第二次点击会落在已经打开的弹窗背景上（=「点击空白处关闭」），把弹窗关掉；紧接着的重试又会把它打开——属于自我修复，最坏多两次点击。
- 「战斗」这一跳**故意没加**：点完要打完一整场，下一屏锚点几十秒后才出现，短 `timeout` 会误判成"没生效"而连点三次。

**扩展到入口与结算链路**（同一天做的第二批，节点数 56 → 66）：同样形状，`timeout` 放宽到 3000（这些点击后面跟着转场动画，3 秒才够）：

| 节点 | 点 | 锚点 | 两级重试后兜底 |
|---|---|---|---|
| `CampaignTownEntry` | 主界面「关卡」 | 模式对应的入口节点 | `CampaignRecover` |
| `CampaignPhantomEntry` | 「幻灵挑战」 | `OpenRecommended`（准备界面的「通关阵容」） | `CampaignRecover` |
| `CampaignNormalEntry` | 「挑战」 | 同上 | `CampaignRecover` |
| `VictoryChallenge` | 结算页「挑战」 | 同上 | `CampaignRecover` |
| `BattleRetry` | 「再次挑战」 | 同上 | `CampaignRecover` |

`CampaignTownEntry` 的重试节点有一个额外约束：它的 `next` 是**运行时**由 `CampaignInit` 改成当前模式的入口节点的（幻灵 / 普通），所以 `CampaignInit` 里那次 `override_pipeline` 必须把 `CampaignTownEntry`、`CampaignTownEntryRetry1`、`CampaignTownEntryRetry2` 三个一起改，否则普通模式会串到幻灵去。

同时把 `OpenRecommended`（及 `_550`/`_1080`）的 `pre_delay` 从 1500 降到 **500**——进关卡那一下动画其实没到 1.5 秒，500ms 就够点了。

### 7.10 分辨率支持：把 550×978 归一化到 720×1280

之前每个分辨率一套节点（`_550` 15 个、`_1080` 15 个），模板靠 `tools/scale_images.py` 的 `scale = (sx*sy)**0.5` 缩放复制。这条路的问题在于 `TemplateMatch` **没有尺度参数**——缩放出来的模板在非整数倍下重采样，文字和图标像素对不齐，阈值只能放松。

根因其实是**我们自己把框架的归一化关掉了**：`CampaignInit` 里调的 `set_screenshot_use_raw_size(True)`，而绑定自己的 docstring 就写着"此选项可能导致在不同分辨率的设备上坐标不正确"。

现在竖屏改成：

```python
context.tasker.controller.set_screenshot_target_long_side(1280)
```

- 720×1280：长边本来就是 1280，不变；
- 550×978：长边 978 → ×1.3088 → **720×1280**（比例 0.56237 vs 0.5625，差 0.02%，看不出形变）。

于是识别、模板、ROI、点击坐标全部落在 720 空间，点击由框架换算回真实分辨率。配套改动：

- `coords.RESOLUTION_SUFFIX["550x978"] = ""`（与 720 共用一套节点）；
- `coords._NORMALIZED_TO = {(550, 978): (720, 1280)}`，`set_resolution()` 先把真实分辨率换算到工作空间；
- `_RES_SUFFIX` 运行期只剩 `""` 和 `"_1080"` 两种。

`_550` 那 15 个节点**暂时保留但已无引用**——先不删，万一归一化在别的机器上有问题可以立刻回退。确认稳定后再清理，同时可以一并退役 `tools/scale_images.py` / `tools/scale_pipelines.py`。

横屏 1920×1080 本次不动：`_1080` 节点和 `raw_size` 策略保持原样。真要做，得单开一套横屏资产——长边归一后是 1280×720，而游戏内容是竖屏 letterbox 在中间，模板根本对不上。

验证方法：把游戏分辨率切到 550p 跑一次，日志应打印 `[CampaignInit] 分辨率=550x978（工作空间 720x1280）` 和 `已设置截图长边缩放为 1280`；`OpenRecommended` 能命中，就说明归一化和坐标换算都对。

## 八、重试链踩到的第一个真 bug：耐心太短 + 重试反而把弹窗关掉

现象（用户）：「不管成功还是失败，第二次进入点通关阵容时都点歪了，两个分辨率都会这样。」

日志（`maafw.log`，两次任务运行）给出的机制是两条独立缺陷叠在一起：

**① 弹窗只有 2 s 耐心。** `OpenRecommended.timeout` 是 2000 ms，也就是点完「通关阵容」只给弹窗 2 s 去被认出。实测弹窗滑入后「一键采用」有时要 2 s 之后才稳定到能被匹配，于是这一跳判失败。

**② 重试把已经打开的弹窗点关掉。** 判失败后进 `OpenRecommendedRetry1`，它重新点「通关阵容」——可这时弹窗其实**已经打开并盖住了那颗按钮**，这一下点的是弹窗背景，等于「点击空白处关闭」。接着 `Retry1` 自己也识别不到按钮（被弹窗盖住），`Retry2` 同样，最后 `[ERR][PipelineTask.cpp][L80] error handling loop detected [node.name=OpenRecommended]`，整条任务直接失败。这就是"第二次进入必定失败"的来源。

调参前后：

| 字段 | 之前 | 现在 | 理由 |
|---|---|---|---|
| `OpenRecommended.pre_delay` | 500 | **1200** | 500 ms 时点击落在准备界面的入场动画里，第一轮实测连点 3 次才打开弹窗 |
| `OpenRecommended.timeout` | 2000 | **4000** | 给弹窗滑入留时间 |
| `OpenRecommendedRetry1/2.timeout` | 2000 | **4000** | 同上 |
| `OpenRecommendedRetry2.on_error` | `CampaignRecover` | **`RecommendedPanel`** | 最后一次重试若连按钮都认不到，说明弹窗已开——先再看一眼弹窗，而不是直接走恢复 |
| `OpenRecommended.post_delay` | 2000 | **500** | 耐心已经交给 `timeout` 的轮询，这里不必再固定睡 2 s |

教训：**用"下一屏能不能认出"做点击生效判定时，`timeout` 必须比目标界面自身的动画时间长；而重试动作本身必须幂等**——像「通关阵容」这种"点开一个覆盖住按钮的弹层"的按钮，重试等同于关闭，所以重试前应先确认弹层没开。本项目当前是用"最后一次重试改去看弹层"来兜的；更彻底的做法是把重试拆成"先等待再判定"和"再点一次"两步。

## 九、第二个真 bug：对"点完就离页"的按钮，重试方向是反的

现象（用户）：「这次作战成功是进下一关时点歪了。」

日志（`maafw.log` 10:55:20–28）说明**点击根本没歪**：

```
10:55:22.125 run_action Click box=[451,1152,190,57] point=(529,1161) success=true  [name=VictoryChallenge]
10:55:25.769 VictoryChallengeRetry1 失败  box=[508,1210,190,57] score=0.191394
10:55:28.849 Task timeout [pretask.name=VictoryChallenge] [reco_timeout=3000ms]
             → PipelineTask bad next → error handling loop detected → Tasker.Task.Failed
```

- 22.1 s 点下去的那一刻，命中框正是结算页右下角的「挑战」按钮，`success=true`；
- 23.1–25.1 s `OpenRecommended` 在找准备界面的「通关阵容」，分数 0.12–0.15（关卡页特征），随后出现空帧——这一轮转场比之前慢，3 s 内没等到锚点；
- 25.8 s 重试节点再去认「挑战」，**按钮已经随离页消失**（0.19 分），两级重试必然全灭；
- 链尾兜底是 `CampaignRecover`，于是一次成功的点击被判成失败，还绕成 `error handling loop detected`。

**根因是重试的方向错了**：对"点完就离页"的按钮（先锋关卡、幻灵挑战、挑战、再次挑战、结算页挑战），点成功时按钮**本来就会消失**，"按钮还在不在"不能当作"上次有没有点上"的判据。所以重试链的尾巴不能落到 `CampaignRecover`，而应该落到**下一屏的锚点**上——锚点认不出才是真失败。

修法：

| 字段 | 之前 | 现在 |
|---|---|---|
| 五个导航类节点 `timeout` | 3000 | **4000**（给转场动画留时间） |
| `XRetry2.on_error` | `CampaignRecover` | 该族的 `next[0]`（下一屏锚点） |
| `CampaignTownEntry*` 的运行时 override | 只改 `next` | `Retry2` 连 `on_error` 一起改成当前模式的入口 |

这样三种情形都收敛到正确行为：

1. 点击成功、转场慢 → 重试认不到按钮（已经走人）→ 落回锚点，接着往下走；
2. 点击真的没点上、按钮还在 → 重试再点一次（用户要的机制）；
3. 两次都没点上 → 锚点也认不出 → 走各自的恢复链路。

顺带一个环境结论：**游戏窗口位置每次启动都会变**（本轮 `hwnd 27398256`，window `(1368,25)-(2110,1361)`、client 原点 `(1379,70)`；早先是 `(1714,0)` / `(1725,45)`）。但客户区始终是 720×1280，模板与 client 坐标系一一对应，**模板不需要跟着窗口位置改**——只有用桌面截图做辅助测量时才要重新读原点。

### 9.1 补刀：这次"点歪"还有第二个原因——模板没完整落在按钮内部

用户随后确认「点到了挑战按钮上面一点，导致返回了选关页面」，对照日志就能算出为什么：

- 旧模板 `victory_challenge_720p.png` 是 190×57，裁的时候**带进了按钮上方的页面空白**（按钮实际在 client y 1170~1265，模板覆盖 1160~1217 附近）；
- 命中框 `box=[451,1152,190,57]` 的中心是 `(546,1180)`，正好压在按钮**上边缘**；
- 实际点击点是 `(529,1161)`——比按钮上边缘还高 9 px，落在按钮外面的背景上。

也就是说：模板只要"跨在按钮边上"，命中框中心就可能落在按钮外面；此时即使识别分数满分（0.99），点击也会落空。

修法：把模板换成**完全位于按钮内部**的文字裁片——`victory_challenge_720p.png` 重裁为 160×60，取 client `(450,1172)-(610,1232)`，只含绿底 + 「挑战」二字（不含战力数字、不含按钮边），整页自匹配 1.0000；阈值同步放宽到 **0.80**（这张来自 719×1274 的截图，经 LANCZOS 重采样到 720×1280）。

通用规则（比"裁掉会变的东西"更进一步）：**模板必须完整落在按钮内部，并且四周留出容错边距**。这样即使点击点相对命中框中心有 ±20 px 的系统性偏差（本项目的 Win32 点击就有这个现象），也仍然落在按钮上。

## 十、1920×1080 横屏：另起一套，不与 720 共用模板

### 10.1 先测清楚：1080 是**真横屏 UI**，不是竖屏 letterbox

早先 1280×720 那次（`log_20260825_221853`）游戏把竖屏内容用黑边塞进横屏窗口，导致 `failed to get target rect`。这次把客户端调到 1920×1080 后实测是**另一种情况**：整屏都是游戏内容，UI 重新排版过——底栏在正中、先锋关卡在左下、世界在右下。

所以 1080 **不能**复用 720 的模板，也不能靠缩放模板凑合（`TemplateMatch` 没有尺度参数）。`_1080` 那 14 个盲点节点是逐个换成真机模板重建的。

窗口几何（`ctypes` + `EnumWindows` / `GetClientRect` / `ClientToScreen`，开头先 `SetProcessDpiAwarenessContext(-4)`）：hwnd 会变、窗口位置每次启动都会变，但**客户区恒为 1920×1080**，所以模板与客户区坐标一一对应，不需要跟着窗口位置改。

### 10.2 九张 1080 模板

客户端坐标，与 `campaign.json` 里的 ROI 同一坐标系：

| 模板 | 尺寸 | 位置 | 用途 |
|---|---|---|---|
| `town_stage_entry_1080p.png` | 82×20 | (30,1034) | 主界面左下「先锋关卡」 |
| `phantom_challenge_1080p.png` | 130×40 | (655,890) | 关卡页「幻灵挑战」 |
| `normal_challenge_1080p.png` | 105×42 | (1195,888) | 关卡页「挑战」 |
| `clearance_formation_1080p.png` | 87×84 | (545,958) | 准备界面「通关阵容」 |
| `start_battle_1080p.png` | 130×48 | (1215,968) | 准备界面绿色「战斗」 |
| `recommended_apply_1080p.png` | 158×52 | (940,864) | 推荐阵容弹窗「一键采用」 |
| `recommended_next_1080p.png` | 52×52 | (1188,556) | 弹窗右侧 ▶ 翻页箭头 |
| `victory_challenge_1080p.png` | 90×40 | (1135,994) | 结算页绿色「挑战」 |
| `retry_button_1080p.png` | 150×50 | (1118,1012) | 战败页「再次挑战」 |

取证方法：游戏必须在前台，用 `mcp__windows__Screenshot(region=客户区)` 截 1:1 帧，再用 `tools/make_template.py` 裁。**这个 Unity 窗口不支持 `PrintWindow`**（`GetLastError()=5`），后台抓图只会拿到被遮挡的桌面；进入关卡瞬间还有黑色斜线转场，要等 2~3 s 再截。

### 10.3 移植时踩到的五个坑（都是"720 有、1080 漏了"）

1. **候选列表少一项**：`CampaignInit` 里用 `[_task("CampaignTownEntry"), entry]` 才支持"主界面/关卡页"两种起步；1080 早期只走了 `entry`，主界面起步时 20 秒空转到超时，表现是"点了没反应"。
2. **`VictoryChallenge_1080` 不存在**：720 的 `VictoryChallenge` 是后来才加的，1080 没跟着建，而 `_task("VictoryChallenge")` 在 1080 下会拼出这个名字 → 断链。
3. **`CampaignResetFormation` 的分支**：原来 1080 走 `_entry_node(mode)`（关卡页入口模板），在结算页上认不出来 → 通关后卡住。现在三种分辨率统一走 `VictoryChallenge`。
4. **弹窗锚点漏配**：`OpenRecommended_1080.next` 直接写了 `TryFormation_1080`（无识别的 Custom 动作），点空也不会失败 → 重试链根本不触发。必须对齐 720：`next` 指向 `RecommendedPanel_1080`（认「一键采用」），认不出才算这次点击没生效。
5. **`pre_delay` 漏配**：720 的 `OpenRecommended` 有 `pre_delay: 1200`（进关卡有入场动画，动画期间能识别到按钮但点不动），1080 写成 0 → 必然点空。这条最容易漏，因为它是"数字"不是"结构"。

`tools/compare_families.py` 就是为第 5 类问题写的：逐字段比对 720 与 `_1080` 两个家族（动作类型、识别类型、`next`/`on_error` 的对应关系、`timeout`/`pre_delay`/`post_delay`/`rate_limit`/`repeat`），把"结构没对齐"一次性列出来。

### 10.4 重试链的收敛规则（两个分辨率共用）

```
主节点 --next(下一屏锚点)--> 成功
   \--timeout / 识别失败--> Retry1 --> Retry2 --> CampaignRecover
```

- **点击没生效**（按钮还在）→ 重试节点能重新识别到按钮 → 再点一次；
- **点击生效了**（按钮消失、页面已切走）→ 重试识别不到 → 落到 `CampaignRecover`。

**链尾绝不能指回祖先节点**（例如 `VictoryChallenge_1080Retry2 → OpenRecommended_1080`），否则框架判 `error handling loop detected`，整个任务瞬间失败。

### 10.5 超时统一为 12 s

除两类例外，所有"点完等下一屏"的节点（主节点与重试节点，720 与 1080 共 44 个）`timeout` 统一 **12000 ms**：

| 节点 | 值 | 为什么不能跟着统一 |
|---|---|---|
| `WaitBattleEnd` ×3 | 300000 | 要覆盖最长战斗，12 s 会在战斗中途判失败 |
| `VictoryIndicator` / `DefeatIndicator` ×6 | 1000 | 是"胜负命中后跳往 HandleVictory/Defeat"的一跳，不是在等界面 |

### 10.6 部署侧还有一个坑：目录联接会被"材料化"

MPE 用**相对路径**加载资源（`MaaResourcePostBundle [path=.]`），所以模板按 `<cwd>/image/` 找、agent 按 `<assets>/agent/main.py` 启动。开发树里靠两个目录联接把真实位置接过去：

```
image          -> assets/resource/image
assets/image   -> assets/resource/image
assets/agent   -> agent
```

它们一旦被某个工具还原成普通目录，就会留下陈旧副本：模板加载不到（报 `templates or threshold is empty`，其实是"文件没找到"）、agent 跑的是旧代码（**改了代码但完全没有效果**，而且没有任何报错）。

排查一句话：

```bash
powershell -NoProfile -Command "Get-Item image,assets\image,assets\agent | Select-Object Name,LinkType"
```

`LinkType` 不是 `Junction` 就是被还原了。修复：`python tools/fix_image_links.py` 重建两个 image 联接；`assets/agent` 需要手动 `New-Item -ItemType Junction -Target <绝对路径>`（用 `..\agent` 会被解析成上一级目录而失败）。

