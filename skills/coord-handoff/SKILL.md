---
name: coord-handoff
description: 当用户输入 $coord-handoff，或想交接当前 coord 工作、总结进展、结束任务或切换任务时使用。
---

# Coord 交接

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-handoff
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行前先检查当前上下文，并整理具体摘要：已完成工作、最终有效结论、仍有效风险、未完成事项、阻塞点和下一步。不要复述推理过程、协商过程、草稿或已被推翻的中间态。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py handoff --group <group> --agent <agent> "<summary>"
```
