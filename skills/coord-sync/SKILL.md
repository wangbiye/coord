---
name: coord-sync
description: 当用户输入 $coord-sync，或想同步当前 coord 协作组状态时使用。
---

# Coord 同步状态

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-sync
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py sync --group <group> --agent <agent>
```

把输出视为当前协调上下文和当前角色指令，并向用户概括可执行事项。

如果用户说“`<agent>` 已完成”，先同步，再查找该 agent 最近的 note、handoff、decision 或 claim 变化；当前 agent 是 reviewer 时默认开始审查，当前 agent 是 executor 时默认读取结论并继续修改或收尾。

如果用户说“`<agent>` 已回复”，先同步，再查找该 agent 最近且与当前 agent 相关的 answer；找到后按当前角色继续。找不到相关记录时，不要猜，说明 coord 中没有看到对应完成记录或回复。
