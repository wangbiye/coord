---
name: coord-claim
description: 当用户输入 $coord-claim，或想在 coord 协作组中认领任务或项目相对文件范围时使用。
---

# Coord 认领范围

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-claim <task> --files "path/**"
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py claim --group <group> --agent <agent> --files "path/**" "<task>"
```

只使用项目相对路径。绝对路径、`..` 和与 active claim 重叠的范围都会被拒绝。
