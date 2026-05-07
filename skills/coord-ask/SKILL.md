---
name: coord-ask
description: 当用户输入 $coord-ask，或想向另一个 coord agent 或所有 agent 提问时使用。
---

# Coord 提问

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-ask @<agent> <question>
$coord-ask @all <question>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。目标不明确时，先澄清。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py ask --group <group> --agent <agent> @<target> "<question>"
```
