---
name: coord-sync
description: 当用户输入 $coord-sync，或想同步当前 coord 协作组状态时使用。
---

# Coord 同步状态

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-sync
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py sync --group <group> --agent <agent>
```

把输出视为当前协调上下文，并向用户概括可执行事项。
