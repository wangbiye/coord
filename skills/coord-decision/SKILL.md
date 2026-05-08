---
name: coord-decision
description: 当用户输入 $coord-decision，或想为 coord 协作组记录一个稳定决策时使用。
---

# Coord 记录决策

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-decision <decision>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py decision --group <group> --agent <agent> "<decision>"
```

只用于记录 group 应该遵循的稳定决策或约定。不要记录候选方案、协商过程、临时判断或尚未确认的中间态。
