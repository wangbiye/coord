---
name: coord-impact
description: 当用户输入 $coord-impact，或错误 coord 事件已经被执行、被引用、可能影响其他 agent，需要创建待处理影响项时使用。
---

# Coord 记录影响项

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-impact <event-id> @agent <action needed>
$coord-impact <event-id> @all <action needed>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py impact --group <group> --agent <agent> <event-id> @<agent|all> "<action needed>"
```

用于不能静默隐藏的错误：旧记录已经被执行、被引用，或是否已被消费不确定。目标 agent 会在 `sync` 的 `Needs Attention` 中看到该影响项。
