---
name: coord-brief
description: 当用户输入 $coord-brief，或想查看 coord 协作组简报，特别是中途加入时使用。
---

# Coord 查看简报

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-brief
$coord-brief <group>
```

如果已知当前 group 就使用当前 group，否则先询问 group。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py brief --group <group>
```

把输出视为当前协调上下文。简报会包含各 agent 的角色摘要；中途加入时先理解这些角色分工，再概括可执行事项。
