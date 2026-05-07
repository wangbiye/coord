---
name: coord-list-groups
description: 当用户输入 $coord-list-groups，或想查看当前已创建且未归档的 coord 协作组列表时使用。
---

# Coord 列出协作组

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-list-groups
```

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py list groups
```

只列出包含 `manifest.json` 的 active group；已归档的 group 不会显示。
