---
name: coord-archive
description: 当用户输入 $coord-archive，或明确要求归档某个 coord 协作组时使用。
---

# Coord 归档协作组

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

只有用户明确要求归档 group 时才使用：

```text
$coord-archive <group>
```

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py archive <group>
```

归档会把数据移动到 `<coord-root>/archive/` 下，不会删除数据。
