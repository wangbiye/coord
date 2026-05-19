# Coord

`coord` 是一个本地异步协作 skill，用来让多个 LLM 会话共享少量协作状态。

它不是实时聊天，也不会主动通知其他会话。它更像一个本地留言板：一个会话写入状态，另一个会话在需要时同步读取。

日常使用很简单：

1. 每个 LLM 会话先 `join` 到同一个 group。
2. 用户给不同会话指派任务。
3. A 做完后，用户去告诉 B：`A 已完成`。
4. B 处理完后，用户再去告诉 A：`B 已完成`。

底层数据默认写入 `~/.coord`。不要把密钥、token 或隐私信息写进 coord。

## 环境检查

在仓库根目录执行：

```bash
pwd
python3 --version
python3 skills/coord/scripts/coord.py list groups
```

确认：

- 当前目录是 `coord-skill` 仓库。
- 本机有 `python3`。
- helper 能运行；没有 group 时输出 `(none)` 是正常的。

查看当前仓库包含哪些 coord skills：

```bash
find skills -maxdepth 2 -name SKILL.md | sort
```

## 如何安装

默认安装到 `~/.agents/skills`：

```bash
./install.sh
```

指定安装目录：

```bash
./install.sh /path/to/skills
```

安装后，重启或重新加载你的 agent 环境，让它重新发现这些 skills。

安装脚本会同步安装当前仓库里的 `coord` 和 `coord-*` skills，并清理目标目录里旧的 coord 入口。它不会清理 `lark-*`、`superpowers`、`blueprinter` 或其他非 coord skill。

### 规划与 spec/plan 写作的前置依赖

coord 内置角色本身只记录协作状态，但规划和文档写作会调用其他 skill 体系：

- `planner`：用于方案设计、体验设计和工程规划时，需要当前 agent 环境已安装并能发现 gstack skills；用于创建或更新 superpowers spec 和 implementation plan 时，需要能发现 superpowers skills。
- `reviewer`：用于方案、交互、工程、devex 或 PR-like review 时，适合的场景需要当前 agent 环境已安装并能发现 gstack review skills。

coord 本身不会安装 gstack 或 superpowers。缺少这些依赖时，仍然可以加入对应角色并记录协作状态，但相关规划、审查或写 spec/plan 工作流不能完整执行。

升级也是同一个命令：

```bash
./install.sh
```

已有协作数据默认保留在 `~/.coord`，安装 skill 不会删除这些数据。

## 日常使用

### 1. 每个会话先加入同一个 group

第一个会话：

```text
$coord join checkout-flow planner
```

第二个会话：

```text
$coord join checkout-flow reviewer
```

`join` 的 group 不存在时会自动创建。常用 agent 名：

- `planner`：用 gstack 做方案设计、体验设计和工程规划；用 superpowers 写 spec/plan。
- `reviewer`：审查 spec、计划、代码、测试和交付结果；适合的方案、交互、工程、devex 或 PR-like review 使用 gstack review skills。
- `executor`：按已审查通过的 plan 或明确用户请求执行实现、修复、验证。
- `stabilizer`：实现审查后协助测试、复现问题、查 bug、修 bug，并记录最终交付状态。
- `frontend`：前端实现或审查。
- `backend`：后端实现或审查。

如果需要再开一个同类新会话，不要复用同一个 agent 名。可以使用带后缀的唯一名称：

```text
$coord join checkout-flow executor-2
$coord join checkout-flow reviewer_hotfix
$coord join checkout-flow planner-design
$coord join checkout-flow stabilizer_2
```

`reviewer-*` / `reviewer_*`、`executor-*` / `executor_*`、`frontend-*` / `frontend_*`、`backend-*` / `backend_*`、`planner-*` / `planner_*`、`stabilizer-*` / `stabilizer_*` 会自动继承对应内置角色卡。连接符支持中划线和下划线。如果 join 时同名 agent 已存在，helper 会建议改名，并提示 `executor-* 自动继承 executor 内置角色` 这类规则。

不要使用 `executer`，应使用 `executor`。

### 2. 用 planner、reviewer、executor 和 stabilizer 流转

需要先确认当前 agent 环境已安装 gstack 和 superpowers。然后按任务规模选择要开的会话：

```text
$coord join checkout-flow planner
$coord join checkout-flow reviewer
$coord join checkout-flow executor
$coord join checkout-flow stabilizer
```

推荐流转：

1. `planner` 理解需求并使用适用的 gstack skills 产出方案/spec；涉及 UI/交互时，spec 中必须先写「UI/交互需求说明」。写完后记录 spec 路径和 `status=ready_for_review`。
2. `reviewer` 审查 spec，记录 `verdict=approved` 或 `verdict=changes_requested`。审查通过后才进入写 plan；如果 spec 和 plan 一次写完，也可以一次 review。
3. `planner` 或 `planner-2` 根据已通过的 spec 写 implementation plan，记录 plan 路径和 `status=ready_for_review`。
4. `reviewer` 或 `reviewer-2` 审查 plan，记录 gate 结论。通过后，`executor` 按确认后的计划执行开发。
5. `executor` 完成实现后记录 implementation handoff，包含改动文件、验证结果、未验证原因、偏差和 UI/交互证据。
6. `reviewer` 或 `reviewer-3` 审查代码和结果是否对齐原始 spec/plan；涉及 UI/交互时，需要尽量实际运行界面或用截图/浏览器证据对照「UI/交互需求说明」。
7. `stabilizer` 接手收尾：协助测试、复现问题、查根因、修 bug、补验证，直到最终可交付或需要用户决策。

实际开发中不必固定三轮 review；小需求可以压缩流程，但作者记录产物和变更、reviewer 记录 gate 结论、stabilizer 记录最终状态这三条不变。

### 3. 用户直接指派任务

在 executor 会话里说：

```text
实现 checkout-flow 的登录态处理，完成后记录结果。
```

executor 做完后会记录 note 或 handoff。

### 4. A 做完后去告诉 B

在 reviewer 会话里说：

```text
executor 已完成
```

reviewer 会先同步 coord，读取 executor 最新记录，然后开始 review。

### 5. B 做完后回到 A

reviewer 完成后会记录 review 结果。然后在 executor 会话里说：

```text
reviewer 已完成
```

executor 会同步 reviewer 的结论，继续修改、验证，或说明无需处理。

### 6. 两个执行角色互相协作

frontend 会话：

```text
$coord join checkout-flow frontend
```

backend 会话：

```text
$coord join checkout-flow backend
```

如果 frontend 需要 backend 确认接口：

```text
$coord ask @backend 登录接口错误码按哪套返回？
```

然后去 backend 会话说：

```text
frontend 已提问
```

backend 同步后回答：

```text
$coord answer q-0001 按 ApiErrorCode 统一返回
```

再回到 frontend 会话说：

```text
backend 已回复
```

### 7. 中途加入一个新会话

新会话加入后先看简报：

```text
$coord join checkout-flow executor-2
$coord brief
```

`brief` 会输出当前 group 的成员、开放问题、活跃认领、待处理影响项和有效摘要。

## 高阶用法

日常只需要记住 `join`、`A 已完成`、`B 已完成`。下面这些命令在需要更精确协作时再用。

独立入口只保留常用查看和生命周期命令：`$coord-join`、`$coord-sync`、`$coord-brief`、`$coord-status`、`$coord-list-groups`、`$coord-list-agents`、`$coord-archive`、`$coord-archive-all`。其他高阶命令统一使用 `$coord <subcommand>`。

### 状态查看

```text
$coord sync
$coord brief
$coord status
$coord list groups
$coord list agents
```

- `sync`：当前会话开始工作前同步状态。
- `brief`：中途加入时查看 group 简报。
- `status`：看紧凑计数。
- `list groups` / `list agents`：查看已有 group 和成员。

### 记录结果

```text
$coord note "reviewed src/login: no blocking issues found; residual risk is manual E2E not run"
$coord handoff
$coord decision "登录接口错误态统一按 ApiErrorCode 映射"
```

记录时只写最终有效结论、当前状态、阻塞点和仍有效风险。不要写推理过程、草稿、临时判断或已经被推翻的结论。

### 提问和回答

```text
$coord ask @backend "接口错误码最终按哪套处理？"
$coord ask @all "谁负责 review 登录接口？"
$coord answer q-0001 "按 ApiErrorCode 统一处理"
```

`ask` 是异步留言。对方只有在 `sync` 后才会看到。

### 认领文件范围

```text
$coord claim "登录页 UI 调整" --files "src/login/**"
$coord release c-0001
```

`--files` 使用项目相对路径；不要用绝对路径或 `..`。如果和其他 active claim 重叠，命令会失败，需要先协调。

### 纠错

普通 `sync` 和 `brief` 默认只显示当前有效视图。

```text
$coord retract e-0003 "记录有误，未被消费"
$coord correct e-0003 "最终正确结论"
```

- `retract`：撤回未被消费、无需其他 agent 知道过程的错误记录。
- `correct`：用最终正确版本替换旧记录。

如果旧记录已经被执行或可能影响别人，不要静默撤回，改用 impact：

```text
$coord impact e-0003 @executor "旧结论已被执行，请重新检查相关改动"
$coord resolve-impact i-0001 "已重查，无需改动"
```

### 归档

```text
$coord archive checkout-flow
$coord archive-all
```

归档是移动，不是删除：

```text
~/.coord/groups/checkout-flow
-> ~/.coord/archive/checkout-flow-YYYYmmdd-HHMMSS
```

归档后，`$coord list groups` 不再显示该 group。

### 调整角色卡

```text
$coord role "只审查 spec/plan，不审查代码；发现需求歧义时先提问。"
```

只有当 join 后的角色定位不符合当前任务时才需要调整。

### 直接运行 helper

一般不需要直接运行底层脚本。调试时可以在仓库根目录执行：

```bash
python3 skills/coord/scripts/coord.py list groups
```

隔离测试可指定数据目录：

```bash
COORD_ROOT=/tmp/coord-test python3 skills/coord/scripts/coord.py list groups
```

### 开发验证

```bash
python3 -m unittest skills.coord.scripts.test_coord -v
python3 -m unittest test_install -v
```
