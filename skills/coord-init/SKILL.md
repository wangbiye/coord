---
name: coord-init
description: 当用户输入 $coord-init，或想初始化一个新的 coord 协作组时使用。
---

# Coord 初始化协作组

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-init <group>
```

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py init <group>
```

如果 group 已存在，helper 只会提示已存在，不会覆盖数据。
