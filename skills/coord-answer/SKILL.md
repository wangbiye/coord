---
name: coord-answer
description: 当用户输入 $coord-answer，或想回答一个打开中的 coord 问题时使用。
---

# Coord 回答问题

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-answer <question-id> <answer>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py answer --group <group> --agent <agent> <question-id> "<answer>"
```

只有目标 agent 可以回答；如果问题目标是 `@all`，任意 agent 都可以回答。重复回答会被拒绝。

回答内容只写最终答案和必要约束，不写重新思考、协商过程、候选方案或已被推翻的中间态。
