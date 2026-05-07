---
name: coord-list-agents
description: 当用户输入 $coord-list-agents，或想查看某个 coord 协作组中的 agent 成员列表时使用。
---

# Coord 列出成员

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-list-agents
$coord-list-agents <group>
```

如果已知当前 group 就使用当前 group，否则先询问 group。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py list agents --group <group>
```
