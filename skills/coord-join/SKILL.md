---
name: coord-join
description: 当用户输入 $coord-join，或想以某个 agent 身份加入 coord 协作组时使用。
---

# Coord 加入协作组

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-join <group> <agent>
```

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py join <group> <agent>
```

如果 group 不存在，先告诉用户该 group 缺失，并询问是否创建并加入。只有用户确认后才执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py join <group> <agent> --create
```

成功加入后，记住当前会话身份：`group=<group>` 和 `agent=<agent>`。
