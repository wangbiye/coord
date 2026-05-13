---
name: coord
description: 当用户输入 $coord 或 $coord-* 命令，想协调多个 AI agent 会话、加入或同步协作组、记录或调整角色卡、记录笔记、提问或回答、记录决策、认领范围、释放认领、归档一个或所有协作组，或交接工作时使用；已加入协作组的会话完成需要组内可见的工作结果时也使用。
---

# Coord

Local asynchronous coordination for multiple AI agent sessions. Use the bundled helper script as the source of truth; do not hand-edit shared coordination files.

## Safety Boundary

Allowed write scope for this skill:

```text
${COORD_ROOT:-~/.coord}/**
```

Writing coordination state is allowed only when the user explicitly uses `$coord` write commands or clearly asks to join, adjust a role card, note, ask, answer, decide, claim, release, archive, or hand off coordination state. This does not authorize project file edits, git writes, process cleanup, dependency installs, databases, Lark, or external APIs.

Archiving one group or all groups is a write operation. Run it only when the user explicitly asks to archive. It moves coordination data under the configured coord root's `archive/` directory; it does not delete data.

## Session Identity

Track the current identity in conversation after join:

```text
group=<group>
agent=<agent>
```

The helper script is stateless between invocations. For commands that require identity, pass `--group <group> --agent <agent>` using the current identity.

If identity is missing, only run `init`, `join`, `list groups`, or `brief --group <group>`. Otherwise ask the user which group and agent this session should use.

Do not reuse the same agent name for two live sessions unless the user explicitly chooses that. If `join` warns that the same agent already exists, suggest a unique name for the new session.

## Role Profiles

`agent` identifies the current session. `role` describes how that session should work. Users do not need to manage this distinction: `join group-a reviewer` should both set `agent=reviewer` and, because `reviewer` is a built-in role, attach the reviewer role profile.

Built-in roles are inherited by exact names and by suffixed session names. `reviewer-*` / `reviewer_*`, `executor-*` / `executor_*`, `frontend-*` / `frontend_*`, and `backend-*` / `backend_*` automatically inherit the matching built-in role profile. Use this for extra live sessions, such as `executor-2` or `executor_hotfix`, instead of reusing `executor`.

Built-in role names:

- `reviewer`: reviews spec, plan, code, tests, and delivery results. In spec/plan phases, check requirement completeness, consistency, risks, acceptance criteria, and execution clarity. In code phases, check bugs, regressions, API contracts, test gaps, maintainability, and whether user requirements are met. Do not edit files by default unless the user explicitly asks. Record a final review note even when there are no blocking issues.
- `executor`: executes changes from confirmed specs, plans, user requests, or reviewer feedback. In spec/plan phases, update the document until reviewer feedback is resolved. In code phases, implement, fix, test, and verify. Stop for confirmation when requirements change, plans conflict, cross-agent dependencies appear, or risky operations are needed. Record change summary, verification result, and remaining risk before handing back for review.
- `frontend`: executes frontend work with focus on UI, interaction flow, state changes, responsive behavior, accessibility, and visual consistency. In spec/plan phases, define user-visible behavior, feedback states, page states, edge cases, and acceptance criteria. In code phases, implement frontend changes and verify real interface behavior where possible.
- `backend`: executes backend work with focus on API contracts, data models, permissions, error handling, idempotency, compatibility, migrations, and test coverage. In spec/plan phases, define interface boundaries, data flow, failure cases, and validation strategy. In code phases, implement backend changes, tests, and contract verification.

Do not use `executer`. If the user types it, tell them to use `executor`.

After `join`, read the helper's role output aloud in concise form. If the user adjusts the role, check that the adjustment does not conflict with coord safety boundaries or stable group decisions, then record it:

```bash
python3 <coord-skill-dir>/scripts/coord.py role --group <group> --agent <agent> "<confirmed role profile>"
```

`sync` prints the current agent role profile. Treat it as active instructions for this session.

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
| `$coord archive group-a` | `python3 <coord-skill-dir>/scripts/coord.py archive group-a` |
| `$coord archive-all` | `python3 <coord-skill-dir>/scripts/coord.py archive-all` |
| `$coord sync` | `python3 <coord-skill-dir>/scripts/coord.py sync --group group-a --agent frontend` |
| `$coord brief` | `python3 <coord-skill-dir>/scripts/coord.py brief --group group-a` |
| `$coord status` | `python3 <coord-skill-dir>/scripts/coord.py status --group group-a` |
| `$coord list groups` | `python3 <coord-skill-dir>/scripts/coord.py list groups` |
| `$coord list agents` | `python3 <coord-skill-dir>/scripts/coord.py list agents --group group-a` |
| `$coord note "text"` | `python3 <coord-skill-dir>/scripts/coord.py note --group group-a --agent frontend "text"` |
| `$coord role "text"` | `python3 <coord-skill-dir>/scripts/coord.py role --group group-a --agent frontend "text"` |
| `$coord retract e-0003 "reason"` | `python3 <coord-skill-dir>/scripts/coord.py retract --group group-a --agent frontend e-0003 "reason"` |
| `$coord correct e-0003 "final text"` | `python3 <coord-skill-dir>/scripts/coord.py correct --group group-a --agent frontend e-0003 "final text"` |
| `$coord impact e-0003 @backend "action needed"` | `python3 <coord-skill-dir>/scripts/coord.py impact --group group-a --agent frontend e-0003 @backend "action needed"` |
| `$coord resolve-impact i-0001 "result"` | `python3 <coord-skill-dir>/scripts/coord.py resolve-impact --group group-a --agent frontend i-0001 "result"` |
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
| `$coord-join <group> <agent>` | `$coord join <group> <agent>` |
| `$coord-archive <group>` | `$coord archive <group>` |
| `$coord-archive-all` | `$coord archive-all` |
| `$coord-sync` | `$coord sync` |
| `$coord-brief [group]` | `$coord brief` |
| `$coord-status [group]` | `$coord status` |
| `$coord-list-groups` | `$coord list groups` |
| `$coord-list-agents [group]` | `$coord list agents` |

Other commands remain available through `$coord <subcommand>` but do not have standalone command skills.

## Record Final State

Coord records are durable shared state, not a transcript of the conversation. Before writing `note`, `decision`, `answer`, or `handoff`, first filter the current conversation down to the final effective outcome.

Record only:

- final findings, final review verdicts, completed progress, verification results, current valid risks, current blockers, and stable agreements;
- the latest stable version when a topic changed across several discussion turns;
- obsolete context only when another agent needs it to avoid following a superseded result, and mark it clearly as obsolete in one short sentence.

Do not record:

- reasoning process, negotiation process, drafts, options that were not chosen, temporary review conclusions, superseded judgments, or labels like "revised review conclusion";
- statements still waiting for user confirmation or another agent's answer;
- intermediate states that would mislead another session reading the coord record later.

If the content is not stable yet, ask a question, wait, or skip recording until there is a stable result. Use `ask` for unresolved cross-agent dependencies instead of turning uncertainty into a note.

Review record shape:

```text
reviewed <target>: verdict=<final verdict>; issues=<currently valid issues>; agreed_changes=<stable agreed changes>; residual_risk=<currently valid risk>
```

## Corrections And Effective View

Use `retract` only when an incorrect event has not been consumed and the correction process does not need to be visible to other agents.

Use `correct` when an event should be replaced by a final effective version. Normal `sync` and `brief` output hide the superseded event and show the replacement.

Use `impact` when the incorrect event has already been executed, referenced, or may have affected another agent. Do not silently retract these cases. `sync` and `brief` show open impacts under `Needs Attention`.

Use `resolve-impact` after the target agent has handled the impact. If consumption is unclear, ask one concise question; if still unclear, prefer `impact`.

## Record Results

If this session has a current `group=<group>` and `agent=<agent>`, coordination continues to apply even when the next user request does not mention `$coord`.

Before the final response for review, analysis, implementation, verification, investigation, or planning work, write a concise final-state coordination record unless the user explicitly says not to record it:

- Use `note` for findings, progress, review results, verification results, and "no issues found" outcomes.
- Use `decision` only for stable decisions or agreements the group should follow.
- Use `ask` when another agent must answer something before work can continue.
- Use `handoff` for longer work, task completion, session ending, or context transfer.

Do not only reply to the user with review or analysis results. If the result matters to the group, record it in coord first, then mention that it was recorded.

Review-specific default: after reviewing a spec, design doc, code, test, or PR-like change, record a note whether issues were found or not.

## Backfill After Join

If the user asks after `join` to record "刚才", "前面", "当前会话", review results, conclusions, or agreements, inspect the relevant current conversation before and after the join. Do not record only the latest user message or the latest assistant message.

Extract the final stable conclusions using the Record Final State rule. If the pre-join conversation contains several versions of the same review result or agreement, record the last stable version only. If the final conclusion is unclear from the current conversation, ask one concise clarification before writing.

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
- "归档所有协作组" -> archive-all.
- "把刚才的 review 结果记录下来" -> inspect current conversation, extract final stable review result, then note.
- "角色改成 ..." or "这个角色应该 ..." -> inspect for conflicts, then record the confirmed role profile with `role`.
- "问后端接口错误码怎么处理" -> ask `@backend`.
- "回答 q-0001 ..." -> answer.
- "记录一个决策 ..." -> decision.
- "认领 ..." -> claim.
- "交接一下" -> handoff.
- "`<agent>` 已完成" -> sync, inspect the latest effective note/handoff/decision/claim activity from that agent, then continue according to the current role. A reviewer should review the completed work; an executor should apply required changes or report no action needed.
- "`<agent>` 已回复" -> sync, inspect the latest answer by that agent relevant to the current agent, then continue according to the current role.

If target, group, agent, question id, or claim files are ambiguous, ask one concise clarification before writing.

For "`<agent>` 已完成" or "`<agent>` 已回复", if sync does not show a relevant record, do not infer one. Say that no matching coord record was found and ask the user to identify the target or ask the other agent to write a note, handoff, or answer.

If the group does not exist during `join`, the helper creates it automatically and joins the current agent. Do not ask for a separate creation confirmation.

## Working Rules

- Start code work with `sync` when current identity is set.
- Start review, analysis, implementation, verification, investigation, or planning work with `sync` when current identity is set.
- Follow the current role profile shown by `join` and `sync`; when the user changes it, record the confirmed version with `role`.
- Use `ask` for cross-agent dependencies; do not guess another agent's decision.
- Use `answer q-id` for answers; do not bury answers in notes.
- Answer only questions targeted to the current agent or `@all`; repeated answers are rejected.
- Use `handoff` before ending a substantial task or switching topics.
- Record task results before final response when current identity is set, including review results with no findings.
- Record final effective state only; do not write intermediate or superseded conversation states.
- Check active claims before editing files; if there is an overlap, stop and explain the conflict.
- Use project-relative paths in `claim --files`; never use absolute paths or `..`. Ambiguous glob overlaps are treated as conflicts.
- Do not modify another agent's `agents/<agent>.md`.
- Do not treat coordination summaries as substitutes for reading actual project files.

## Communication Model

Coord is an asynchronous message board. Asking a question writes it to the group. The target agent sees it only after running `sync`; no live notification or interruption is provided.
