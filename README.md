# Coord

`$coord` 是一个本地异步协作 skill，用来让多个 AI agent 会话通过本地文件共享状态、提问、回答、记录决策、认领文件范围和交接进展。

它不是实时聊天系统，也不会主动打断其他会话。它更像一个本地留言板：一个会话写入信息，另一个会话通过 `sync` 读取。

## 适用场景

- 多个 agent 会话并行处理同一个项目。
- 需要明确谁负责哪些文件或任务。
- 需要把跨会话问题、回答、决策和交接记录留在本地。
- 需要异步协作，但不想引入远程服务、数据库或外部 API。

## 仓库结构

```text
skills/
  coord/
    SKILL.md
    scripts/
      coord.py
      test_coord.py
  coord-init/
  coord-join/
  coord-archive/
  coord-sync/
  coord-brief/
  coord-status/
  coord-list-groups/
  coord-list-agents/
  coord-note/
  coord-ask/
  coord-answer/
  coord-decision/
  coord-claim/
  coord-release/
  coord-handoff/
install.sh
README.md
```

`skills/coord/` 是主协议和 helper 脚本。`skills/coord-*` 是独立子命令入口，用于更容易触发和补全。

## 安装

进入仓库根目录后执行：

```bash
./install.sh
```

默认安装到：

```text
~/.agents/skills
```

也可以指定安装目录：

```bash
./install.sh /path/to/skills
```

安装后，重启或重新加载你的 agent 环境，让它重新发现这些 skills。

## 数据目录

默认协调数据写入：

```text
~/.coord
```

正常使用时不需要设置环境变量。测试或隔离运行时可以设置：

```bash
COORD_ROOT=/tmp/coord-test python3 skills/coord/scripts/coord.py list groups
```

不要把密钥、token、隐私信息写入 `$coord`。

## 核心概念

- `group`：协作组，是隔离边界。不同 group 默认互不共享。
- `agent`：某个 AI agent 会话在 group 里的身份，例如 `frontend`、`backend`、`reviewer`。
- `event`：协作事件，例如 note、question、answer、decision、claim、handoff。

一个 group 可以有多个 agent，不限两个会话。

## 快速开始

第一个会话：

```text
$coord init checkout-flow
$coord join checkout-flow frontend
```

第二个会话：

```text
$coord join checkout-flow backend
```

如果 group 不存在，`join` 不会自动创建。agent 应先询问是否创建并加入；用户确认后才创建。

同步状态：

```text
$coord sync
```

提问：

```text
$coord ask @backend 接口错误码最终按哪套处理
```

回答：

```text
$coord answer q-0001 按 ApiErrorCode 统一处理
```

结束前交接：

```text
$coord handoff
```

## 命令总览

`$coord` 支持两种写法：

```text
$coord join group-a frontend
$coord-join group-a frontend
```

两者等价。`$coord-xxx` 形式是为了方便联想和减少输入错误。

| 独立命令 | 等价写法 | 用途 |
| --- | --- | --- |
| `$coord-init <group>` | `$coord init <group>` | 创建 group |
| `$coord-join <group> <agent>` | `$coord join <group> <agent>` | 加入 group |
| `$coord-archive <group>` | `$coord archive <group>` | 归档 group |
| `$coord-sync` | `$coord sync` | 同步当前 group |
| `$coord-brief [group]` | `$coord brief` | 查看 group 简报 |
| `$coord-status [group]` | `$coord status` | 查看紧凑状态 |
| `$coord-list-groups` | `$coord list groups` | 列出 active group |
| `$coord-list-agents [group]` | `$coord list agents` | 列出 group 成员 |
| `$coord-note <内容>` | `$coord note <内容>` | 记录进展或 review 结果 |
| `$coord-ask @agent <问题>` | `$coord ask @agent <问题>` | 向 agent 提问 |
| `$coord-answer <q-id> <回答>` | `$coord answer <q-id> <回答>` | 回答问题 |
| `$coord-decision <内容>` | `$coord decision <内容>` | 记录决策 |
| `$coord-claim <任务> --files "path/**"` | `$coord claim <任务> --files "path/**"` | 认领任务或文件范围 |
| `$coord-release <claim-id>` | `$coord release <claim-id>` | 释放认领 |
| `$coord-handoff` | `$coord handoff` | 交接当前进展 |

## 常用命令

列出已创建且未归档的 active group：

```text
$coord list groups
$coord-list-groups
```

创建 group：

```text
$coord init <group>
$coord-init <group>
```

加入 group：

```text
$coord join <group> <agent>
$coord-join <group> <agent>
```

查看 group 成员：

```text
$coord list agents
$coord-list-agents
```

同步状态：

```text
$coord sync
$coord-sync
```

查看中途加入所需的简报：

```text
$coord brief
$coord-brief
```

查看紧凑计数状态：

```text
$coord status
$coord-status
```

记录进展：

```text
$coord note <内容>
$coord-note <内容>
```

已加入 group 后，即使用户没有再次输入 `$coord`，review、分析、实现、验证、排查、规划这类任务完成前也应该写一条 `note`，除非用户明确说不要记录。

提问：

```text
$coord ask @<agent> <问题>
$coord ask @all <问题>
$coord-ask @<agent> <问题>
$coord-ask @all <问题>
```

回答：

```text
$coord answer <question-id> <回答>
$coord-answer <question-id> <回答>
```

回答规则：

- 只能由目标 agent 回答。
- `@all` 问题可以由任意 agent 回答。
- 已回答的问题默认不能重复回答。

记录决策：

```text
$coord decision <决策内容>
$coord-decision <决策内容>
```

认领任务或文件范围：

```text
$coord claim <任务说明> --files "<项目相对路径>"
$coord-claim <任务说明> --files "<项目相对路径>"
```

`--files` 必须使用项目相对路径。不允许绝对路径，不允许 `..`。模糊 glob 会按保守冲突处理。如果和其他 active claim 重叠，命令会失败，需要先协调。

释放认领：

```text
$coord release <claim-id>
$coord-release <claim-id>
```

交接：

```text
$coord handoff
$coord-handoff
```

交接内容应包含已完成工作、当前判断和依据、未完成事项、阻塞点、建议下一步。

归档 group：

```text
$coord archive <group>
$coord-archive <group>
```

归档是移动，不是删除：

```text
~/.coord/groups/checkout-flow
-> ~/.coord/archive/checkout-flow-YYYYmmdd-HHMMSS
```

归档后，`$coord list groups` 不再显示该 group。

## 语义触发

可以不用严格输入命令，agent 应能理解这些说法：

```text
加入 checkout-flow，身份 frontend
同步一下
看一下协调状态
问后端接口错误码怎么处理
回答 q-0001 按 ApiErrorCode 统一处理
记录一个决策：错误态按 ApiErrorCode 映射
认领登录页 UI，文件 src/login/**
交接一下当前进展
归档 checkout-flow
```

语义不明确时，agent 应先问一个澄清问题，不应该猜。

## 场景示例

两个会话协作，一个做前端，一个做后端：

```text
$coord init checkout-flow
$coord join checkout-flow frontend
$coord claim "登录页 UI 调整" --files "src/login/**"
$coord ask @backend 接口错误码最终按哪套处理
```

另一个会话：

```text
$coord join checkout-flow backend
$coord sync
$coord answer q-0001 按 ApiErrorCode 统一处理
$coord decision 登录接口错误态统一按 ApiErrorCode 映射
```

中途加入 reviewer：

```text
$coord join checkout-flow reviewer
$coord brief
$coord claim "review 登录接口 contract 和测试" --files "src/api/login.ts,test/login/**"
$coord note "reviewed login contract and tests: no blocking issues found; residual risk is manual end-to-end usage not exercised"
```

claim 冲突时先沟通：

```text
$coord ask @frontend 我需要改 src/login/form.ts 接口调用，能否释放或拆分 claim？
```

## 人应该做什么

- 给每个会话指定 group 和 agent。
- 在关键节点触发 `sync`、`ask`、`handoff`。
- 对分工不清或 claim 冲突做裁决。
- 不手动编辑 coord 数据目录里的 JSON/JSONL 文件。
- 不把密钥、token、隐私信息写入 `$coord`。

## Agent 应该做什么

- 解析 `$coord` 和明确的自然语言触发。
- 通过 helper 脚本读写协调数据。
- 已加入 group 后，开始 review、分析、实现、验证、排查、规划前先 `sync`。
- 跨 agent 依赖用 `ask`，不要猜。
- 阶段性完成后写 `note` 或 `handoff`。
- review 或分析任务完成后，先写 `note` 记录结果，再回复用户；没有发现问题也要记录。
- 回答问题必须用 `answer q-id`。
- 发现 claim 冲突时停下来说明。
- 不把 `$coord` 当作修改项目文件、git、进程或外部系统的授权。

## 常见问题

### `$coord list groups` 看不到某个 group

可能原因：

- group 从未创建。
- group 已被 archive。
- group 目录残缺，没有 `manifest.json`。

### `$coord join` 提示 group 不存在

这是正常保护。确认名字没拼错后，让 agent 创建并加入。

### 问题发出后对方没有反应

`$coord` 不会实时通知。对方会话需要执行：

```text
$coord sync
```

才能看到问题。

### answer 被拒绝

可能原因：

- 当前 agent 不是问题目标。
- 问题已经被回答过。
- question id 写错。

### claim 被拒绝

可能原因：

- 路径和其他 active claim 重叠。
- 使用了绝对路径。
- 使用了 `..`。
- glob 过于模糊，被保守判定为冲突。

## 直接运行 helper

一般情况下不需要直接运行底层脚本。调试时可以在仓库根目录执行：

```bash
python3 skills/coord/scripts/coord.py list groups
```

## 开发与验证

运行单元测试：

```bash
python3 skills/coord/scripts/test_coord.py
```

测试会使用临时目录，不会写入默认协调数据目录。
