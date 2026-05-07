---
name: coord-status
description: 当用户输入 $coord-status，或想查看 coord 协作组的紧凑状态摘要时使用。
---

# Coord 查看状态

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-status
$coord-status <group>
```

如果已知当前 group 就使用当前 group，否则先询问 group。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py status --group <group>
```
