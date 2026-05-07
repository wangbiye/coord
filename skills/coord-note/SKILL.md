---
name: coord-note
description: 当用户输入 $coord-note，或想记录 coord 笔记、进展、发现、review 结果或验证结果时使用。
---

# Coord 记录笔记

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-note <text>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py note --group <group> --agent <agent> "<text>"
```

用 note 记录发现、进展、review 结果、验证结果，以及“没有发现问题”的结果。
