---
name: coord-release
description: 当用户输入 $coord-release，或想释放一个 active coord 认领时使用。
---

# Coord 释放认领

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-release <claim-id>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py release --group <group> --agent <agent> <claim-id>
```
