---
name: coord-correct
description: 当用户输入 $coord-correct，或想用最终正确版本替换一条 coord 事件时使用。
---

# Coord 修正事件

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-correct <event-id> <final text>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py correct --group <group> --agent <agent> <event-id> "<final text>"
```

普通 `sync` 和 `brief` 会隐藏旧事件，只显示最终有效版本。若旧事件已经被执行或可能影响别人，先用 `impact` 暴露待处理动作。
