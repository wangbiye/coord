---
name: coord-join
description: 当用户输入 $coord-join，或想以某个 agent 身份加入 coord 协作组时使用。
---

# Coord 加入协作组

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-join <group> <agent>
```

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py join <group> <agent>
```

如果 group 不存在，helper 会自动创建 group 并加入当前 agent；不要再单独询问用户是否创建。

成功加入后，记住当前会话身份：`group=<group>` 和 `agent=<agent>`。

如果 agent 名是 `reviewer`、`executor`、`frontend`、`backend`、`planner` 或 `stabilizer`，helper 会输出匹配到的内置角色卡。带后缀的新会话名也会自动继承内置角色：`reviewer-*` / `reviewer_*`、`executor-*` / `executor_*`、`frontend-*` / `frontend_*`、`backend-*` / `backend_*`、`planner-*` / `planner_*`、`stabilizer-*` / `stabilizer_*`。连接符支持中划线和下划线，例如 `executor-2`、`executor_hotfix`。

`planner` 角色做规划时依赖 gstack，写 spec/plan 时依赖 superpowers；`reviewer` 在适合的方案、交互、工程、devex 或 PR-like review 中依赖 gstack review skills。加入角色前不需要由 coord 检查安装状态，但向用户说明：如果当前 agent 环境没有安装并发现对应 skills，相关规划、审查或写 spec/plan 工作流无法正确执行。

如果 helper 提示同名 agent 已存在，建议用户为新会话改用唯一名称，并告知用户类似 `executor-* 自动继承 executor 内置角色` 的规则；只有用户明确要恢复同一会话身份时才继续复用同名 agent。

向用户简要说明当前角色指令，并提醒用户如果不符合当前任务可以调整。不要使用 `executer`；用户写错时提示改用 `executor`。

如果用户调整角色定位，先判断是否与 coord 安全边界、当前任务或稳定 group 决策冲突。确认无冲突后，使用主协议中的 `role` 命令记录自定义角色卡。

如果用户随后要求把“刚才”“前面”“当前会话”的 review 结果、结论或约定记录下来，必须回看当前会话中 join 之前和之后的相关内容，提炼最终稳定结论；不能只记录最近一条消息，也不能记录中间态。
