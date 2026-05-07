---
name: coord
description: 当用户输入 $coord 或 $coord-* 命令，想协调多个 AI agent 会话、加入或同步协作组、记录笔记、提问或回答、记录决策、认领范围、释放认领或交接工作时使用；已加入协作组的会话完成需要组内可见的工作结果时也使用。
---

# Coord

Local asynchronous coordination for multiple AI agent sessions. Use the bundled helper script as the source of truth; do not hand-edit shared coordination files.

## Safety Boundary

Allowed write scope for this skill:

```text
${COORD_ROOT:-~/.coord}/**
```

Writing coordination state is allowed only when the user explicitly uses `$coord` write commands or clearly asks to join, note, ask, answer, decide, claim, release, or hand off coordination state. This does not authorize project file edits, git writes, process cleanup, dependency installs, databases, Lark, or external APIs.

Archiving a group is a write operation. Run it only when the user explicitly asks to archive a group. It moves coordination data under the configured coord root's `archive/` directory; it does not delete data.

## Session Identity

Track the current identity in conversation after join:

```text
group=<group>
agent=<agent>
```

The helper script is stateless between invocations. For commands that require identity, pass `--group <group> --agent <agent>` using the current identity.

If identity is missing, only run `init`, `join`, `list groups`, or `brief --group <group>`. Otherwise ask the user which group and agent this session should use.

Do not reuse the same agent name for two live sessions unless the user explicitly chooses that.

## Helper

Use the `coord` skill directory that contains this `SKILL.md`; the helper is at:

```text
<coord-skill-dir>/scripts/coord.py
```

Run:

```bash
python3 <coord-skill-dir>/scripts/coord.py <command>
```

The helper stores data in `~/.coord` by default. It writes JSON/JSONL and Markdown summaries, validates group and agent names, and rejects path traversal.

Do not set `COORD_ROOT` during normal skill use unless the user explicitly asks for a custom data directory.

## Commands

User-facing commands map to helper commands:

| User says | Run |
| --- | --- |
| `$coord init group-a` | `python3 <coord-skill-dir>/scripts/coord.py init group-a` |
| `$coord join group-a frontend` | `python3 <coord-skill-dir>/scripts/coord.py join group-a frontend` |
| user confirms creating missing group during join | `python3 <coord-skill-dir>/scripts/coord.py join group-a frontend --create` |
| `$coord archive group-a` | `python3 <coord-skill-dir>/scripts/coord.py archive group-a` |
| `$coord sync` | `python3 <coord-skill-dir>/scripts/coord.py sync --group group-a --agent frontend` |
| `$coord brief` | `python3 <coord-skill-dir>/scripts/coord.py brief --group group-a` |
| `$coord status` | `python3 <coord-skill-dir>/scripts/coord.py status --group group-a` |
| `$coord list groups` | `python3 <coord-skill-dir>/scripts/coord.py list groups` |
| `$coord list agents` | `python3 <coord-skill-dir>/scripts/coord.py list agents --group group-a` |
| `$coord note "text"` | `python3 <coord-skill-dir>/scripts/coord.py note --group group-a --agent frontend "text"` |
| `$coord ask @backend "text"` | `python3 <coord-skill-dir>/scripts/coord.py ask --group group-a --agent frontend @backend "text"` |
| `$coord answer q-0001 "text"` | `python3 <coord-skill-dir>/scripts/coord.py answer --group group-a --agent frontend q-0001 "text"` |
| `$coord decision "text"` | `python3 <coord-skill-dir>/scripts/coord.py decision --group group-a --agent frontend "text"` |
| `$coord claim "task" --files "src/**"` | `python3 <coord-skill-dir>/scripts/coord.py claim --group group-a --agent frontend --files "src/**" "task"` |
| `$coord release c-0001` | `python3 <coord-skill-dir>/scripts/coord.py release --group group-a --agent frontend c-0001` |
| `$coord handoff` | inspect current context, compose a concrete summary, then run `python3 <coord-skill-dir>/scripts/coord.py handoff --group group-a --agent frontend "summary"` |

After `sync`, `brief`, or `status`, treat the helper output as current coordination context and summarize only the actionable parts for the user.

## Standalone Command Skills

The following standalone commands are equivalent to `$coord <subcommand>` forms and exist to improve discoverability/autocomplete:

| Standalone | Equivalent |
| --- | --- |
| `$coord-init <group>` | `$coord init <group>` |
| `$coord-join <group> <agent>` | `$coord join <group> <agent>` |
| `$coord-archive <group>` | `$coord archive <group>` |
| `$coord-sync` | `$coord sync` |
| `$coord-brief [group]` | `$coord brief` |
| `$coord-status [group]` | `$coord status` |
| `$coord-list-groups` | `$coord list groups` |
| `$coord-list-agents [group]` | `$coord list agents` |
| `$coord-note <text>` | `$coord note <text>` |
| `$coord-ask @agent <text>` | `$coord ask @agent <text>` |
| `$coord-answer <q-id> <text>` | `$coord answer <q-id> <text>` |
| `$coord-decision <text>` | `$coord decision <text>` |
| `$coord-claim <task> --files "path/**"` | `$coord claim <task> --files "path/**"` |
| `$coord-release <claim-id>` | `$coord release <claim-id>` |
| `$coord-handoff` | `$coord handoff` |

All standalone command skills must still follow this main coord protocol and safety boundary.

## Record Results

If this session has a current `group=<group>` and `agent=<agent>`, coordination continues to apply even when the next user request does not mention `$coord`.

Before the final response for review, analysis, implementation, verification, investigation, or planning work, write a concise coordination record unless the user explicitly says not to record it:

- Use `note` for findings, progress, review results, verification results, and "no issues found" outcomes.
- Use `decision` only for stable decisions or agreements the group should follow.
- Use `ask` when another agent must answer something before work can continue.
- Use `handoff` for longer work, task completion, session ending, or context transfer.

Do not only reply to the user with review or analysis results. If the result matters to the group, record it in coord first, then mention that it was recorded.

Review-specific default: after reviewing a spec, design doc, code, test, or PR-like change, record a note whether issues were found or not.

Examples:

```text
python3 <coord-skill-dir>/scripts/coord.py note --group group-a --agent reviewer "reviewed docs/spec.md: found 2 issues, 1 open question; no file changes made"
python3 <coord-skill-dir>/scripts/coord.py note --group group-a --agent reviewer "reviewed docs/spec.md: no blocking issues found; residual risk is missing integration test coverage"
```

## Semantic Triggers

Map clear natural language to commands:

- "加入 group-a，身份 frontend" -> join.
- "同步一下" -> sync.
- "看一下协调状态" -> status or sync.
- "归档 group-a" -> archive `group-a`.
- "问后端接口错误码怎么处理" -> ask `@backend`.
- "回答 q-0001 ..." -> answer.
- "记录一个决策 ..." -> decision.
- "认领 ..." -> claim.
- "交接一下" -> handoff.

If target, group, agent, question id, or claim files are ambiguous, ask one concise clarification before writing.

If join fails because the group does not exist, tell the user the group is missing and ask whether to create it and join. Only after confirmation run join with `--create`. Do not silently create a group from a possibly mistyped name.

## Working Rules

- Start code work with `sync` when current identity is set.
- Start review, analysis, implementation, verification, investigation, or planning work with `sync` when current identity is set.
- Use `ask` for cross-agent dependencies; do not guess another agent's decision.
- Use `answer q-id` for answers; do not bury answers in notes.
- Answer only questions targeted to the current agent or `@all`; repeated answers are rejected.
- Use `handoff` before ending a substantial task or switching topics.
- Record task results before final response when current identity is set, including review results with no findings.
- Check active claims before editing files; if there is an overlap, stop and explain the conflict.
- Use project-relative paths in `claim --files`; never use absolute paths or `..`. Ambiguous glob overlaps are treated as conflicts.
- Do not modify another agent's `agents/<agent>.md`.
- Do not treat coordination summaries as substitutes for reading actual project files.

## Communication Model

Coord is an asynchronous message board. Asking a question writes it to the group. The target agent sees it only after running `sync`; no live notification or interruption is provided.
