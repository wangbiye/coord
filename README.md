# Coord

Coord 用来让多个 AI 会话在本机共享协作状态。适合把同一个任务分给 planner、reviewer、executor 等不同会话，让它们通过同一个 group 交接结果。

不要把密钥、token 或隐私信息写进 coord。

## 环境检查

把本仓库下载到本地后，在终端进入仓库目录，执行：

```bash
python3 skills/coord/scripts/coord.py list groups
```

能正常输出 group 列表即可；没有 group 时输出 `(none)` 是正常的。这个检查只确认本仓库里的 Python helper 能运行。

## 如何安装

Codex：

```bash
./install.sh codex
```

默认安装到 `~/.agents/skills`。

Claude Code：

```bash
./install.sh claude
```

默认安装到 `~/.claude/skills`。

安装后重启对应 agent，让它重新发现 skills。

## 内置角色

- `planner`：整理需求、写方案、写 spec/plan。
- `reviewer`：审查方案、计划、代码和交付结果。
- `executor`：按明确任务或已审查计划执行实现。
- `stabilizer`：接手测试、复现、修 bug 和收尾。
- `frontend`：处理前端实现或审查。
- `backend`：处理后端实现或审查。

同一个 group 里，每个会话的 agent 名必须唯一。比如已经有一个 `executor`，第二个执行会话就用 `executor-2` 或 `executor_hotfix`；它们会按前缀继承 `executor` 的角色。

## 基本用法

每个会话先加入同一个 group：

```text
$coord-join <group> <agent>
```

例子：

```text
$coord-join shop-query planner
```

常用命令：

```text
$coord-sync                 # 同步当前 group 状态
$coord-status               # 看紧凑状态
$coord-brief                # 看完整摘要
$coord note "..."           # 记录当前稳定结论
$coord handoff              # 交接当前任务结果
```

## 普通多人协作

适合你手动开多个会话，分别做 planner、reviewer、executor。

1. planner 会话：

```text
$coord-join shop-query planner
帮我写商品查询的 spec。
```

2. reviewer 会话：

```text
$coord-join shop-query reviewer
审查 planner 写的 spec。
```

3. 回到 planner 会话：

```text
根据 reviewer 结论修 spec。
```

4. executor 会话：

```text
$coord-join shop-query executor
根据 spec/plan 实现。
```

## 中等需求：planner 调度

适合 spec 定型后，让 root planner 帮你调度 reviewer、executor、stabilizer。

root planner 会话：

```text
$coord-join shop-query planner
帮我写商品查询 spec。spec 定型后，启用 planner 调度模式。
```

spec 定型后，继续对 root planner 说：

```text
spec 没问题，继续推进后续流程。
```

root planner 完成后，回到 root planner 会话：

```text
同步结果，给我最终交付状态。
```

## 大需求：分 phase

适合一个需求要拆成多个 phase。完整 phase 目标写在 spec，coord 只写当前 phase 的启动说明。

root planner 会话：

```text
$coord-join big-work planner
帮我写 root spec 和 phase map。
```

phase map 确认后，继续对 root planner 说：

```text
phase map 没问题，写 phase-01 kickoff。
```

你新开 phase planner 会话时只需要说：

```text
$coord-join big-work phase-01-planner
执行 phase-01。
```

phase 完成后，回到 root planner 会话：

```text
phase-01 已完成，确认结果并准备下一个 phase。
```

## 注意事项

- 同一个 group 里 agent 名必须唯一。
- sub-agent 必须自己 join，不要让 planner 代替它 join。
- reviewer 的 verdict 必须由 reviewer 自己记录。
- coord 只放交接和当前状态；长期目标、范围、验收标准写进 spec。
- 不要把密钥、token 或隐私信息写进 coord。
