---
name: coord-archive-all
description: 当用户输入 $coord-archive-all，或明确要求归档所有当前 active coord 协作组时使用。
---

# Coord 归档所有协作组

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

只有用户明确要求归档所有 active group 时才使用：

```text
$coord-archive-all
```

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py archive-all
```

归档会把所有包含 `manifest.json` 的 active group 移动到 `<coord-root>/archive/` 下，不会删除数据；没有 `manifest.json` 的目录不会被当作 group 归档。
