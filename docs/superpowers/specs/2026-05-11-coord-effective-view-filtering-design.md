# Coord Effective View Filtering Design

Date: 2026-05-11

## UI/交互需求说明

`coord` 继续作为多个 LLM 会话之间的本地异步中转站。用户和 LLM 日常看到的仍然是少数命令：同步、简报、记录、提问、回答、决策、认领和交接。

新增纠错能力后，用户能让 LLM 做三类事情：

- 撤回一条还没有被消费的错误记录。
- 用一条最终正确记录替换旧记录。
- 当旧记录已经被执行或可能影响别人时，生成一条需要处理的影响项。

操作后，普通 `sync` 和 `brief` 默认只展示当前有效信息：被撤回的旧记录不出现，被替换的旧记录不出现，只显示最终版本；如果错误记录已经进入执行链路，则显示一条明确的 `Needs Attention` 待处理项，而不是把历史伪装成没有发生过。

整体流程保持简单：LLM 不需要在每次同步时读完整历史，也不需要自己推理哪些旧记录失效。脚本负责过滤和聚合，LLM 只按普通视图继续工作。完整历史保留在事件日志中，但不进入日常同步入口。

## Goal

解决当前 append-only 设计的一个协作问题：错误记录只能再追加纠错说明，导致其他会话在 `sync` 或 `brief` 中看到不该看到的错误过程。

新的设计要同时满足：

- 底层历史仍可追溯，不直接删除共享数据。
- 普通视图默认只暴露当前有效状态。
- 已经被执行过的错误不能被静默隐藏，必须变成可处理的影响项。
- LLM 日常使用成本低，不把复杂状态机暴露给用户。

## Non-Goals

- 不实现任意编辑历史记录。
- 不让 LLM 手动修改 `~/.coord` 下的 JSON、JSONL 或 Markdown 文件。
- 不把 `coord` 变成实时聊天、审批系统或任务管理系统。
- 不在普通 `sync` 和 `brief` 中展示纠错过程。
- 本次不新增完整历史浏览命令；如需排查历史，可在后续单独设计受控的 `history` 入口。

## User-Facing Commands

新增四个命令，命名保持动作明确：

```text
$coord retract <event-id> <reason>
$coord correct <event-id> <final text>
$coord impact <event-id> @<agent|all> <action needed>
$coord resolve-impact <impact-id> <result>
```

命令含义：

- `retract`：撤回错误记录。适用于无人基于该记录行动、也不需要其他 agent 知道纠错过程的情况。
- `correct`：用最终正确内容替换旧记录。脚本把旧事件标记为被替代，并新增一条有效 replacement 事件。
- `impact`：旧记录已经被执行、被引用，或不确定是否被消费时，创建一个待处理影响项。
- `resolve-impact`：影响项处理完成后关闭它，避免永久占用普通视图。

LLM 默认判断规则：

- 只是写错且未被执行：用 `correct` 或 `retract`。
- 明确已经被执行：用 `impact`。
- 不确定是否已经被执行，但可能影响别人：问一句；仍不确定时按 `impact` 处理。

## Data Model

保留 append-only 原则。纠错动作不删除旧事件，而是追加元事件。

事件新增可选字段：

```json
{
  "id": "e-0011",
  "type": "note",
  "agent": "reviewer",
  "text": "old text"
}
```

新产生的 question、answer、note、decision、handoff 等可展示记录都应能和 event id 对齐。已有历史数据没有 event id 时按旧行为保留，但默认视图迁移后不再直接输出旧 Markdown summary 原文。

撤回事件：

```json
{
  "id": "e-0012",
  "type": "retract",
  "agent": "reviewer",
  "target_event_id": "e-0011",
  "reason": "wrong conclusion"
}
```

替换事件：

```json
{
  "id": "e-0013",
  "type": "note",
  "agent": "reviewer",
  "text": "final correct text",
  "replaces_event_id": "e-0011"
}
```

影响项事件：

```json
{
  "id": "e-0014",
  "type": "impact",
  "impact_id": "i-0001",
  "agent": "reviewer",
  "target_event_id": "e-0011",
  "target": "executor",
  "status": "open",
  "text": "Recheck work based on the old conclusion."
}
```

处理完成事件：

```json
{
  "id": "e-0015",
  "type": "resolve-impact",
  "impact_id": "i-0001",
  "agent": "executor",
  "status": "resolved",
  "text": "Rechecked; no changes needed."
}
```

脚本从事件流派生当前有效状态：

- `retracted_event_ids`
- `superseded_event_ids`
- `replacement_events`
- `open_impacts`
- `resolved_impacts`

## View Rules

`sync` 默认展示：

- 当前 group、当前 agent、agent 列表。
- 当前 agent 的角色卡。
- 指向当前 agent 或 `@all` 的 open questions。
- 最近有效 answers。
- active claims。
- `Needs Attention`：指向当前 agent 或 `@all` 的 open impact。
- `Recent Effective Events`：过滤掉撤回、被替代和纠错元事件后的最近有效事件。

`brief` 默认展示：

- group 和 agent 列表。
- agent profiles 摘要。
- 全部 open questions。
- active claims。
- 全部 open impacts。
- 从有效 note/handoff 事件渲染出的 agent summaries。
- 最近有效事件。

普通视图不展示：

- `retract` 元事件。
- 被 `retract` 撤回的旧事件。
- 被 `correct` 替代的旧事件。
- `correct` 的纠错过程，只展示 replacement 事件。
- 已 resolved 的 impact。

完整历史排查不是本次默认视图的一部分。本次只保证底层事件日志保留足够信息，便于未来增加受控排查入口。

## Agent Summaries

当前 `brief` 会直接读取 `agents/<agent>.md`，这会泄漏历史 note/handoff。新设计中：

- 新写入的 note/handoff 仍可保留 Markdown 文件，便于人工排查。
- 普通 `brief` 不再直接输出 Markdown 原文。
- 普通 `brief` 从有效事件渲染 agent summaries。
- 对历史旧 Markdown 块，如果没有 event id，脚本不做猜测性删除；普通视图迁移为事件渲染后，旧块不再影响默认输出。

## Boundary Cases

### 多条记录中只有一条错误

只对目标事件执行 `correct` 或 `retract`。其他事件保持有效。普通视图只隐藏或替换目标事件，不影响同一轮沟通产生的其他记录。

### 错误记录已经被执行

不能只 `retract`。应创建 `impact`，让普通视图显示待处理动作。处理完成后用 `resolve-impact` 关闭。

### 错误记录是否被执行不确定

先问用户一句。如果仍不确定，按已可能影响执行链路处理，创建 `impact`。

### 旧记录被替换后又发现 replacement 有问题

可以继续 `correct <replacement-event-id> <final text>`。有效视图只显示最后一版。历史链路通过 `replaces_event_id` 保留。

### 已回答的问题需要修正

如果只是回答文本写错且未被消费，用 `correct` 替换 answer 事件。若对方已经基于回答执行，用 `impact` 通知需要重新检查。

### active claim 写错

active claim 不通过 `retract` 静默隐藏。应使用现有 `release` 释放，再重新 `claim`。如果别人已经受影响，补 `impact`。

### role 写错

role 使用现有 `role` 命令覆盖当前角色卡，不通过 `correct`。如果错误角色已经导致错误执行，补 `impact`。

### decision 写错

未被消费时可 `correct`。已被执行或被引用时用 `impact`，必要时再写新的 `decision` 表达当前稳定决策。

## Safety

- 所有纠错命令只写入 `${COORD_ROOT:-~/.coord}`。
- 禁止路径穿越，沿用现有 group、agent、event id 校验。
- 默认不删除历史文件。
- 普通视图过滤由脚本完成，不依赖 LLM 自行判断。
- 对 claim、role、join、archive 这类结构性状态，优先使用已有状态命令，不提供静默历史编辑。

## Testing

实现时按 TDD 增加覆盖：

- `retract` 后，目标事件不出现在 `sync` 和 `brief` 的普通事件区。
- `correct` 后，旧事件不出现，replacement 正常出现。
- `brief` 的 agent summaries 不再泄漏被撤回或被替代的 note/handoff。
- `impact` 出现在目标 agent 的 `Needs Attention`。
- `resolve-impact` 后，影响项从普通视图消失。
- active claim、role 等边界按设计拒绝静默撤回或走现有命令。
- 未撤回、未替代的现有记录行为不变。

## Acceptance Criteria

- LLM 日常只需使用 `sync/brief`，默认得到当前有效视图。
- 错误但未消费的记录可被隐藏或替换，不污染其他 agent。
- 已经进入执行链路的错误会转成明确待处理项。
- 完整历史仍存在于事件日志中，但不污染普通 `sync/brief`。
- 文档和 skill command table 覆盖新增命令及默认判断规则。
