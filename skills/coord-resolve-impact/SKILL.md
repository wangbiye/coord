---
name: coord-resolve-impact
description: 当用户输入 $coord-resolve-impact，或想关闭一个已处理的 coord impact 待处理项时使用。
---

# Coord 解决影响项

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-resolve-impact <impact-id> <result>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py resolve-impact --group <group> --agent <agent> <impact-id> "<result>"
```

影响项处理完成后使用。关闭后普通 `sync` 和 `brief` 不再展示该 impact。
