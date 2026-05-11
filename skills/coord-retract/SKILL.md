---
name: coord-retract
description: 当用户输入 $coord-retract，或想撤回一条未被消费的错误 coord 事件时使用。
---

# Coord 撤回事件

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-retract <event-id> <reason>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py retract --group <group> --agent <agent> <event-id> "<reason>"
```

仅用于未被消费、无需其他 agent 知道纠错过程的错误记录。已经被执行或可能影响别人时使用 `impact`。
