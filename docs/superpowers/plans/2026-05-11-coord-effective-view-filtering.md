# Coord Effective View Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a current-effective coordination view so `sync` and `brief` hide corrected noise while surfacing execution-impacting mistakes.

**Architecture:** Keep `events.jsonl` append-only and derive visible state in `coord.py` before rendering `sync` and `brief`. Add small command handlers for `retract`, `correct`, `impact`, and `resolve-impact`; keep LLM-facing usage simple by making the helper decide what ordinary views show.

**Tech Stack:** Python 3 standard library, `unittest`, existing single-file helper `skills/coord/scripts/coord.py`, existing skill Markdown files.

---

## File Structure

- Modify `skills/coord/scripts/coord.py`: add event id validation, effective-event derivation, correction/impact commands, and filtered render paths.
- Modify `skills/coord/scripts/test_coord.py`: add TDD coverage for retract, correct, impact, summaries, and boundary behavior.
- Modify `skills/coord/SKILL.md`: add main protocol entries and working rules for the new commands.
- Modify `README.md`: document commands, examples, and current-effective view behavior.
- Create `skills/coord-retract/SKILL.md`: standalone command trigger for retract.
- Create `skills/coord-correct/SKILL.md`: standalone command trigger for correct.
- Create `skills/coord-impact/SKILL.md`: standalone command trigger for impact.
- Create `skills/coord-resolve-impact/SKILL.md`: standalone command trigger for resolve-impact.

## Task 1: Retract Command And Effective Event Filtering

**Files:**
- Modify: `skills/coord/scripts/test_coord.py`
- Modify: `skills/coord/scripts/coord.py`

- [ ] **Step 1: Add the failing retract test**

Add this helper near `read_json` in `CoordCliTest`:

```python
    def read_jsonl(self, relative):
        records = []
        for line in (self.root / relative).read_text().splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records
```

Add this test after `test_handoff_updates_agent_summary_and_recent_events`:

```python
    def test_retract_hides_event_from_sync_brief_and_agent_summaries(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("note", "--group", "group-a", "--agent", "frontend", "错误结论")
        note_event = next(
            event
            for event in self.read_jsonl("groups/group-a/events.jsonl")
            if event.get("type") == "note"
        )

        retract = self.run_cli(
            "retract",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            note_event["id"],
            "记录有误，未被消费",
        )

        self.assertIn(f"retracted {note_event['id']}", retract.stdout)
        sync = self.run_cli("sync", "--group", "group-a", "--agent", "frontend")
        brief = self.run_cli("brief", "--group", "group-a")
        self.assertIn("## Recent Effective Events", sync.stdout)
        self.assertNotIn("错误结论", sync.stdout)
        self.assertNotIn("错误结论", brief.stdout)
        self.assertNotIn("retract @frontend", sync.stdout)
        self.assertNotIn("retract @frontend", brief.stdout)

        events = self.read_jsonl("groups/group-a/events.jsonl")
        self.assertTrue(any(event["id"] == note_event["id"] for event in events))
        self.assertTrue(
            any(
                event.get("type") == "retract"
                and event.get("target_event_id") == note_event["id"]
                for event in events
            )
        )
```

- [ ] **Step 2: Run the retract test and verify it fails**

Run:

```bash
python3 -m unittest skills.coord.scripts.test_coord.CoordCliTest.test_retract_hides_event_from_sync_brief_and_agent_summaries -v
```

Expected: FAIL because `retract` is not a known subcommand.

- [ ] **Step 3: Add event id validation and effective-event helpers**

In `skills/coord/scripts/coord.py`, add constants near `QUESTION_RE`:

```python
EVENT_RE = re.compile(r"^e-\d{4}$")
IMPACT_RE = re.compile(r"^i-\d{4}$")
CORRECTABLE_EVENT_TYPES = {"note", "decision", "handoff", "question", "answer"}
INTERNAL_EVENT_TYPES = {"retract", "impact", "resolve-impact"}
```

Add these helpers after `next_id`:

```python
def validate_event_id(value):
    if not EVENT_RE.match(value):
        raise CoordError(f"invalid event id: {value}")
    return value


def validate_impact_id(value):
    if not IMPACT_RE.match(value):
        raise CoordError(f"invalid impact id: {value}")
    return value


def event_by_id(events, event_id):
    for event in events:
        if event.get("id") == event_id:
            return event
    raise CoordError(f"event not found: {event_id}")


def effective_event_state(events):
    retracted = {
        event.get("target_event_id")
        for event in events
        if event.get("type") == "retract" and event.get("target_event_id")
    }
    superseded = {
        event.get("replaces_event_id")
        for event in events
        if event.get("replaces_event_id")
    }
    resolved_impacts = {
        event.get("impact_id")
        for event in events
        if event.get("type") == "resolve-impact" and event.get("impact_id")
    }
    open_impacts = [
        event
        for event in events
        if event.get("type") == "impact"
        and event.get("impact_id")
        and event.get("impact_id") not in resolved_impacts
    ]
    hidden_event_ids = {event_id for event_id in retracted | superseded if event_id}
    effective_events = [
        event
        for event in events
        if event.get("id") not in hidden_event_ids
        and event.get("type") not in INTERNAL_EVENT_TYPES
    ]
    return {
        "hidden_event_ids": hidden_event_ids,
        "effective_events": effective_events,
        "open_impacts": open_impacts,
        "resolved_impacts": resolved_impacts,
    }
```

Add this renderer after `render_event`:

```python
def render_effective_agent_summaries(events):
    summaries = {}
    for event in events:
        if event.get("type") not in {"note", "handoff"}:
            continue
        text = event.get("text") or event.get("summary") or ""
        if not text:
            continue
        label = "Note" if event.get("type") == "note" else "Handoff"
        summaries.setdefault(event.get("agent", "?"), []).append(f"## {label} {event['id']}\n\n{text}")
    return [(agent, "\n\n".join(items)) for agent, items in sorted(summaries.items())]
```

- [ ] **Step 4: Implement `cmd_retract` and wire it into argparse**

Add this command near `cmd_role`:

```python
def cmd_retract(args):
    root = root_dir()
    validate_event_id(args.event_id)
    with locked(root, args.group):
        paths = require_group(root, args.group)
        events = read_jsonl(paths["events"])
        target = event_by_id(events, args.event_id)
        if target.get("type") not in CORRECTABLE_EVENT_TYPES:
            raise CoordError(f"event cannot be retracted: {args.event_id}")
        reason = " ".join(args.reason).strip()
        append_event(
            root,
            args.group,
            "retract",
            args.agent,
            target_event_id=args.event_id,
            reason=reason,
        )
        print(f"retracted {args.event_id}")
```

Update `cmd_sync` and `cmd_brief` to use state:

```python
        events = read_jsonl(paths["events"])
        event_state = effective_event_state(events)
        questions = current_questions(paths, event_state)
        claims = active_claims(paths)
```

In `cmd_sync`, replace recent events rendering with:

```python
        print("\n## Recent Effective Events")
        recent_events = event_state["effective_events"][-10:]
        print("\n".join(render_event(e) for e in recent_events) if recent_events else "(none)")
```

In `cmd_brief`, replace `read_agent_summaries(paths)` with:

```python
        summaries = render_effective_agent_summaries(event_state["effective_events"])
```

Also replace its recent events block with:

```python
        print("\n## Recent Effective Events")
        recent_events = event_state["effective_events"][-15:]
        print("\n".join(render_event(e) for e in recent_events) if recent_events else "(none)")
```

Change the `current_questions` function signature now, even before it uses the state:

```python
def current_questions(paths, event_state=None):
```

Add the parser after `role`:

```python
    retract = subparsers.add_parser("retract")
    add_context_args(retract)
    retract.add_argument("event_id")
    retract.add_argument("reason", nargs="+")
    retract.set_defaults(func=cmd_retract)
```

- [ ] **Step 5: Run the retract test and verify it passes**

Run:

```bash
python3 -m unittest skills.coord.scripts.test_coord.CoordCliTest.test_retract_hides_event_from_sync_brief_and_agent_summaries -v
```

Expected: PASS.

- [ ] **Step 6: Run existing focused regressions**

Run:

```bash
python3 -m unittest \
  skills.coord.scripts.test_coord.CoordCliTest.test_handoff_updates_agent_summary_and_recent_events \
  skills.coord.scripts.test_coord.CoordCliTest.test_ask_answer_and_sync_are_scoped_to_group_and_agent \
  -v
```

Expected: PASS. If `test_handoff_updates_agent_summary_and_recent_events` fails only because the section title changed, update the test name in the same edit; do not reintroduce raw Markdown summaries.

- [ ] **Step 7: Commit Task 1**

```bash
git add skills/coord/scripts/coord.py skills/coord/scripts/test_coord.py
git commit -m "feat: add coord event retraction filtering"
```

## Task 2: Correct Command And Replacement Chains

**Files:**
- Modify: `skills/coord/scripts/test_coord.py`
- Modify: `skills/coord/scripts/coord.py`

- [ ] **Step 1: Add failing tests for note replacement and answer replacement**

Add these tests after the retract test:

```python
    def test_correct_replaces_note_in_sync_brief_and_agent_summaries(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "reviewer")
        self.run_cli("note", "--group", "group-a", "--agent", "reviewer", "旧结论")
        note_event = next(
            event
            for event in self.read_jsonl("groups/group-a/events.jsonl")
            if event.get("type") == "note"
        )

        correct = self.run_cli(
            "correct",
            "--group",
            "group-a",
            "--agent",
            "reviewer",
            note_event["id"],
            "最终结论",
        )

        self.assertIn(f"corrected {note_event['id']}", correct.stdout)
        sync = self.run_cli("sync", "--group", "group-a", "--agent", "reviewer")
        brief = self.run_cli("brief", "--group", "group-a")
        self.assertNotIn("旧结论", sync.stdout)
        self.assertNotIn("旧结论", brief.stdout)
        self.assertIn("最终结论", sync.stdout)
        self.assertIn("最终结论", brief.stdout)

    def test_correct_replaces_answer_in_recent_answers(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("join", "group-a", "backend")
        self.run_cli("ask", "--group", "group-a", "--agent", "frontend", "@backend", "接口怎么处理")
        self.run_cli("answer", "--group", "group-a", "--agent", "backend", "q-0001", "旧回答")
        answer_event = next(
            event
            for event in self.read_jsonl("groups/group-a/events.jsonl")
            if event.get("type") == "answer"
        )

        self.run_cli(
            "correct",
            "--group",
            "group-a",
            "--agent",
            "backend",
            answer_event["id"],
            "最终回答",
        )

        sync = self.run_cli("sync", "--group", "group-a", "--agent", "frontend")
        self.assertIn("q-0001 from frontend to @backend", sync.stdout)
        self.assertNotIn("旧回答", sync.stdout)
        self.assertIn("answer by backend", sync.stdout)
        self.assertIn("最终回答", sync.stdout)
```

- [ ] **Step 2: Run the correct tests and verify they fail**

Run:

```bash
python3 -m unittest \
  skills.coord.scripts.test_coord.CoordCliTest.test_correct_replaces_note_in_sync_brief_and_agent_summaries \
  skills.coord.scripts.test_coord.CoordCliTest.test_correct_replaces_answer_in_recent_answers \
  -v
```

Expected: FAIL because `correct` is not a known subcommand.

- [ ] **Step 3: Make questions records carry event ids**

Update `cmd_ask` so it appends the event first and stores the event id in `questions.jsonl`:

```python
        question_event = append_event(root, args.group, "question", args.agent, target=target, question_id=qid, text=text)
        question = {
            "id": qid,
            "from": args.agent,
            "to": target,
            "status": "open",
            "created_at": now_iso(),
            "text": text,
            "event_id": question_event["id"],
        }
        append_jsonl(root, paths["questions"], question)
```

Update `cmd_answer` similarly:

```python
        answer_event = append_event(root, args.group, "answer", args.agent, question_id=args.question_id, answer=answer)
        record = {
            "id": args.question_id,
            "from": args.agent,
            "status": "answered",
            "answered_at": now_iso(),
            "answer": answer,
            "event_id": answer_event["id"],
        }
        append_jsonl(root, paths["questions"], record)
```

Remove the old duplicate `append_event` calls in both commands.

- [ ] **Step 4: Filter hidden question records in `current_questions`**

Replace the start of `current_questions` with:

```python
def current_questions(paths, event_state=None):
    hidden_event_ids = set()
    if event_state:
        hidden_event_ids = set(event_state.get("hidden_event_ids", set()))
    states = {}
    order = []
    for record in read_jsonl(paths["questions"]):
        event_id = record.get("event_id")
        if event_id and event_id in hidden_event_ids:
            continue
        qid = record.get("id")
        if not qid:
            continue
```

At the end of `current_questions`, filter orphaned answer-only states:

```python
    return [states[qid] for qid in order if states[qid].get("text") and states[qid].get("to")]
```

- [ ] **Step 5: Add replacement helpers and `cmd_correct`**

Add this helper after `append_event`:

```python
def append_agent_markdown_entry(root, group, agent, kind, event_id, text):
    append_text(root, agent_file(root, group, agent), f"\n## {kind} {event_id} {now_iso()}\n\n{text}\n")
```

Update `cmd_note`:

```python
        event = append_event(root, args.group, "note", args.agent, text=text)
        append_agent_markdown_entry(root, args.group, args.agent, "Note", event["id"], text)
```

Update `cmd_handoff`:

```python
        event = append_event(root, args.group, "handoff", args.agent, summary=summary)
        append_agent_markdown_entry(root, args.group, args.agent, "Handoff", event["id"], summary)
```

Add this helper near `cmd_retract`:

```python
def append_replacement(root, group, agent, target, text):
    event_type = target.get("type")
    if event_type == "note":
        event = append_event(root, group, "note", agent, text=text, replaces_event_id=target["id"])
        append_agent_markdown_entry(root, group, agent, "Note", event["id"], text)
        return event
    if event_type == "handoff":
        event = append_event(root, group, "handoff", agent, summary=text, replaces_event_id=target["id"])
        append_agent_markdown_entry(root, group, agent, "Handoff", event["id"], text)
        return event
    if event_type == "decision":
        event = append_event(root, group, "decision", agent, text=text, replaces_event_id=target["id"])
        append_text(root, group_paths(root, group)["decisions"], f"- {now_iso()} @{agent}: {text} (replaces {target['id']})\n")
        return event
    if event_type == "question":
        question_id = target.get("question_id")
        route = target.get("target", "all")
        event = append_event(root, group, "question", agent, target=route, question_id=question_id, text=text, replaces_event_id=target["id"])
        append_jsonl(root, group_paths(root, group)["questions"], {
            "id": question_id,
            "from": target.get("agent", agent),
            "to": route,
            "text": text,
            "event_id": event["id"],
        })
        return event
    if event_type == "answer":
        question_id = target.get("question_id")
        event = append_event(root, group, "answer", agent, question_id=question_id, answer=text, replaces_event_id=target["id"])
        append_jsonl(root, group_paths(root, group)["questions"], {
            "id": question_id,
            "from": agent,
            "status": "answered",
            "answered_at": now_iso(),
            "answer": text,
            "event_id": event["id"],
        })
        return event
    raise CoordError(f"event cannot be corrected: {target['id']}")
```

Add `cmd_correct`:

```python
def cmd_correct(args):
    root = root_dir()
    validate_event_id(args.event_id)
    with locked(root, args.group):
        paths = require_group(root, args.group)
        events = read_jsonl(paths["events"])
        target = event_by_id(events, args.event_id)
        if target.get("type") not in CORRECTABLE_EVENT_TYPES:
            raise CoordError(f"event cannot be corrected: {args.event_id}")
        text = " ".join(args.text).strip()
        replacement = append_replacement(root, args.group, args.agent, target, text)
        print(f"corrected {args.event_id} with {replacement['id']}")
```

Wire parser after `retract`:

```python
    correct = subparsers.add_parser("correct")
    add_context_args(correct)
    correct.add_argument("event_id")
    correct.add_argument("text", nargs="+")
    correct.set_defaults(func=cmd_correct)
```

- [ ] **Step 6: Run the correct tests and verify they pass**

Run:

```bash
python3 -m unittest \
  skills.coord.scripts.test_coord.CoordCliTest.test_correct_replaces_note_in_sync_brief_and_agent_summaries \
  skills.coord.scripts.test_coord.CoordCliTest.test_correct_replaces_answer_in_recent_answers \
  -v
```

Expected: PASS.

- [ ] **Step 7: Run question/answer regression tests**

Run:

```bash
python3 -m unittest \
  skills.coord.scripts.test_coord.CoordCliTest.test_ask_answer_and_sync_are_scoped_to_group_and_agent \
  skills.coord.scripts.test_coord.CoordCliTest.test_answer_rejects_non_target_and_duplicate_answers \
  skills.coord.scripts.test_coord.CoordCliTest.test_answer_allows_any_agent_for_all_target_question \
  -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add skills/coord/scripts/coord.py skills/coord/scripts/test_coord.py
git commit -m "feat: add coord correction replacement flow"
```

## Task 3: Impact Lifecycle And Needs Attention

**Files:**
- Modify: `skills/coord/scripts/test_coord.py`
- Modify: `skills/coord/scripts/coord.py`

- [ ] **Step 1: Add failing impact lifecycle test**

Add this test after the correct tests:

```python
    def test_impact_targets_agent_until_resolved(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "reviewer")
        self.run_cli("join", "group-a", "executor")
        self.run_cli("decision", "--group", "group-a", "--agent", "reviewer", "旧决策")
        decision_event = next(
            event
            for event in self.read_jsonl("groups/group-a/events.jsonl")
            if event.get("type") == "decision"
        )

        impact = self.run_cli(
            "impact",
            "--group",
            "group-a",
            "--agent",
            "reviewer",
            decision_event["id"],
            "@executor",
            "旧决策已被执行，请重新检查相关改动",
        )

        self.assertIn("created impact i-0001", impact.stdout)
        executor_sync = self.run_cli("sync", "--group", "group-a", "--agent", "executor")
        reviewer_sync = self.run_cli("sync", "--group", "group-a", "--agent", "reviewer")
        brief = self.run_cli("brief", "--group", "group-a")
        self.assertIn("## Needs Attention", executor_sync.stdout)
        self.assertIn("i-0001", executor_sync.stdout)
        self.assertIn("旧决策已被执行，请重新检查相关改动", executor_sync.stdout)
        self.assertNotIn("i-0001", reviewer_sync.stdout.split("## Needs Attention", 1)[1].split("##", 1)[0])
        self.assertIn("i-0001", brief.stdout)

        resolved = self.run_cli(
            "resolve-impact",
            "--group",
            "group-a",
            "--agent",
            "executor",
            "i-0001",
            "已重查，无需改动",
        )

        self.assertIn("resolved impact i-0001", resolved.stdout)
        executor_sync_after = self.run_cli("sync", "--group", "group-a", "--agent", "executor")
        brief_after = self.run_cli("brief", "--group", "group-a")
        self.assertNotIn("i-0001", executor_sync_after.stdout)
        self.assertNotIn("i-0001", brief_after.stdout)
```

- [ ] **Step 2: Run the impact test and verify it fails**

Run:

```bash
python3 -m unittest skills.coord.scripts.test_coord.CoordCliTest.test_impact_targets_agent_until_resolved -v
```

Expected: FAIL because `impact` is not a known subcommand.

- [ ] **Step 3: Add impact id generation and renderer**

Add helper after `effective_event_state`:

```python
def next_impact_id(events):
    return next_id([event for event in events if event.get("impact_id")], "i")
```

Add renderer after `render_claim`:

```python
def render_impact(impact):
    target = impact.get("target", "all")
    return (
        f"- {impact['impact_id']} from @{impact.get('agent', '?')} "
        f"about {impact.get('target_event_id', '?')} to @{target}: {impact.get('text', '')}"
    )
```

- [ ] **Step 4: Add `cmd_impact` and `cmd_resolve_impact`**

Add commands after `cmd_correct`:

```python
def cmd_impact(args):
    root = root_dir()
    validate_event_id(args.event_id)
    target = args.target[1:] if args.target.startswith("@") else args.target
    if target != "all":
        validate_name("agent", target)
    with locked(root, args.group):
        paths = require_group(root, args.group)
        events = read_jsonl(paths["events"])
        event_by_id(events, args.event_id)
        impact_id = next_impact_id(events)
        text = " ".join(args.text).strip()
        append_event(
            root,
            args.group,
            "impact",
            args.agent,
            impact_id=impact_id,
            target_event_id=args.event_id,
            target=target,
            status="open",
            text=text,
        )
        print(f"created impact {impact_id}")


def cmd_resolve_impact(args):
    root = root_dir()
    validate_impact_id(args.impact_id)
    with locked(root, args.group):
        paths = require_group(root, args.group)
        events = read_jsonl(paths["events"])
        state = effective_event_state(events)
        impact = next((item for item in state["open_impacts"] if item.get("impact_id") == args.impact_id), None)
        if impact is None:
            raise CoordError(f"open impact not found: {args.impact_id}")
        text = " ".join(args.text).strip()
        append_event(
            root,
            args.group,
            "resolve-impact",
            args.agent,
            impact_id=args.impact_id,
            status="resolved",
            text=text,
        )
        print(f"resolved impact {args.impact_id}")
```

Wire parsers after `correct`:

```python
    impact = subparsers.add_parser("impact")
    add_context_args(impact)
    impact.add_argument("event_id")
    impact.add_argument("target")
    impact.add_argument("text", nargs="+")
    impact.set_defaults(func=cmd_impact)

    resolve_impact = subparsers.add_parser("resolve-impact")
    add_context_args(resolve_impact)
    resolve_impact.add_argument("impact_id")
    resolve_impact.add_argument("text", nargs="+")
    resolve_impact.set_defaults(func=cmd_resolve_impact)
```

- [ ] **Step 5: Render Needs Attention in `sync` and `brief`**

In `cmd_sync`, after Active Claims, add:

```python
        print("\n## Needs Attention")
        my_impacts = [
            impact
            for impact in event_state["open_impacts"]
            if impact.get("target") in {args.agent, "all"}
        ]
        print("\n".join(render_impact(impact) for impact in my_impacts) if my_impacts else "(none)")
```

In `cmd_brief`, after Active Claims, add:

```python
        print("\n## Needs Attention")
        print("\n".join(render_impact(impact) for impact in event_state["open_impacts"]) if event_state["open_impacts"] else "(none)")
```

- [ ] **Step 6: Run the impact lifecycle test and verify it passes**

Run:

```bash
python3 -m unittest skills.coord.scripts.test_coord.CoordCliTest.test_impact_targets_agent_until_resolved -v
```

Expected: PASS.

- [ ] **Step 7: Add missing-group coverage for new write commands**

Update `test_missing_group_write_commands_do_not_leave_residual_group_dirs` command list with:

```python
            ("retract", "--group", "typo", "--agent", "frontend", "e-0001", "撤回"),
            ("correct", "--group", "typo", "--agent", "frontend", "e-0001", "修正"),
            ("impact", "--group", "typo", "--agent", "frontend", "e-0001", "@backend", "影响"),
            ("resolve-impact", "--group", "typo", "--agent", "frontend", "i-0001", "解决"),
```

- [ ] **Step 8: Run missing-group regression**

Run:

```bash
python3 -m unittest skills.coord.scripts.test_coord.CoordCliTest.test_missing_group_write_commands_do_not_leave_residual_group_dirs -v
```

Expected: PASS with `group does not exist: typo` for the new commands.

- [ ] **Step 9: Commit Task 3**

```bash
git add skills/coord/scripts/coord.py skills/coord/scripts/test_coord.py
git commit -m "feat: add coord impact attention lifecycle"
```

## Task 4: Boundary Behavior For Structural State

**Files:**
- Modify: `skills/coord/scripts/test_coord.py`
- Modify: `skills/coord/scripts/coord.py`

- [ ] **Step 1: Add failing boundary test for unsupported event types**

Add this test after impact lifecycle:

```python
    def test_retract_and_correct_reject_structural_events(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("claim", "--group", "group-a", "--agent", "frontend", "--files", "src/**", "任务")
        events = self.read_jsonl("groups/group-a/events.jsonl")
        join_event = next(event for event in events if event.get("type") == "join")
        claim_event = next(event for event in events if event.get("type") == "claim")

        retract_join = self.run_cli(
            "retract",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            join_event["id"],
            "撤回 join",
            ok=False,
        )
        correct_claim = self.run_cli(
            "correct",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            claim_event["id"],
            "修正 claim",
            ok=False,
        )

        self.assertIn("event cannot be retracted", retract_join.stderr)
        self.assertIn("event cannot be corrected", correct_claim.stderr)
```

- [ ] **Step 2: Run the boundary test and verify it passes**

Run:

```bash
python3 -m unittest skills.coord.scripts.test_coord.CoordCliTest.test_retract_and_correct_reject_structural_events -v
```

Expected: PASS if Task 1 and Task 2 used `CORRECTABLE_EVENT_TYPES`; if it fails, update `cmd_retract` and `cmd_correct` to reject event types outside `{"note", "decision", "handoff", "question", "answer"}`.

- [ ] **Step 3: Add replacement-chain test**

Add this test after the boundary test:

```python
    def test_correct_replacement_chain_only_shows_latest_version(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "reviewer")
        self.run_cli("note", "--group", "group-a", "--agent", "reviewer", "第一版")
        first = next(
            event
            for event in self.read_jsonl("groups/group-a/events.jsonl")
            if event.get("type") == "note"
        )
        self.run_cli("correct", "--group", "group-a", "--agent", "reviewer", first["id"], "第二版")
        second = [
            event
            for event in self.read_jsonl("groups/group-a/events.jsonl")
            if event.get("type") == "note"
        ][-1]
        self.run_cli("correct", "--group", "group-a", "--agent", "reviewer", second["id"], "第三版")

        brief = self.run_cli("brief", "--group", "group-a")
        self.assertNotIn("第一版", brief.stdout)
        self.assertNotIn("第二版", brief.stdout)
        self.assertIn("第三版", brief.stdout)
```

- [ ] **Step 4: Run the replacement-chain test and verify it passes**

Run:

```bash
python3 -m unittest skills.coord.scripts.test_coord.CoordCliTest.test_correct_replacement_chain_only_shows_latest_version -v
```

Expected: PASS because `effective_event_state` hides every event referenced by `replaces_event_id`.

- [ ] **Step 5: Commit Task 4**

```bash
git add skills/coord/scripts/coord.py skills/coord/scripts/test_coord.py
git commit -m "test: cover coord correction boundaries"
```

## Task 5: Documentation And Standalone Skill Entries

**Files:**
- Modify: `skills/coord/SKILL.md`
- Modify: `README.md`
- Create: `skills/coord-retract/SKILL.md`
- Create: `skills/coord-correct/SKILL.md`
- Create: `skills/coord-impact/SKILL.md`
- Create: `skills/coord-resolve-impact/SKILL.md`

- [ ] **Step 1: Update main coord command table**

In `skills/coord/SKILL.md`, add rows after `role`:

```markdown
| `$coord retract e-0003 "reason"` | `python3 <coord-skill-dir>/scripts/coord.py retract --group group-a --agent frontend e-0003 "reason"` |
| `$coord correct e-0003 "final text"` | `python3 <coord-skill-dir>/scripts/coord.py correct --group group-a --agent frontend e-0003 "final text"` |
| `$coord impact e-0003 @backend "action needed"` | `python3 <coord-skill-dir>/scripts/coord.py impact --group group-a --agent frontend e-0003 @backend "action needed"` |
| `$coord resolve-impact i-0001 "result"` | `python3 <coord-skill-dir>/scripts/coord.py resolve-impact --group group-a --agent frontend i-0001 "result"` |
```

Add standalone rows:

```markdown
| `$coord-retract <event-id> <reason>` | `$coord retract <event-id> <reason>` |
| `$coord-correct <event-id> <final text>` | `$coord correct <event-id> <final text>` |
| `$coord-impact <event-id> @agent <action needed>` | `$coord impact <event-id> @agent <action needed>` |
| `$coord-resolve-impact <impact-id> <result>` | `$coord resolve-impact <impact-id> <result>` |
```

- [ ] **Step 2: Add correction protocol rules**

In `skills/coord/SKILL.md`, add a short section after `Record Final State`:

```markdown
## Corrections And Effective View

Use `retract` only when an incorrect event has not been consumed and the correction process does not need to be visible to other agents.

Use `correct` when an event should be replaced by a final effective version. Normal `sync` and `brief` output hide the superseded event and show the replacement.

Use `impact` when the incorrect event has already been executed, referenced, or may have affected another agent. Do not silently retract these cases. `sync` and `brief` show open impacts under `Needs Attention`.

Use `resolve-impact` after the target agent has handled the impact. If consumption is unclear, ask one concise question; if still unclear, prefer `impact`.
```

- [ ] **Step 3: Create standalone command skill files**

Create `skills/coord-retract/SKILL.md`:

```markdown
---
name: coord-retract
description: 当用户输入 $coord-retract，或想撤回一条未被消费的错误 coord 事件时使用。
---

# Coord 撤回事件

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-retract <event-id> <reason>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py retract --group <group> --agent <agent> <event-id> "<reason>"
```

仅用于未被消费、无需其他 agent 知道纠错过程的错误记录。已经被执行或可能影响别人时使用 `impact`。
```

Create `skills/coord-correct/SKILL.md`:

```markdown
---
name: coord-correct
description: 当用户输入 $coord-correct，或想用最终正确版本替换一条 coord 事件时使用。
---

# Coord 修正事件

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-correct <event-id> <final text>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py correct --group <group> --agent <agent> <event-id> "<final text>"
```

普通 `sync` 和 `brief` 会隐藏旧事件，只显示最终有效版本。若旧事件已经被执行或可能影响别人，先用 `impact` 暴露待处理动作。
```

Create `skills/coord-impact/SKILL.md`:

```markdown
---
name: coord-impact
description: 当用户输入 $coord-impact，或错误 coord 事件已经被执行、被引用、可能影响其他 agent，需要创建待处理影响项时使用。
---

# Coord 记录影响项

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-impact <event-id> @agent <action needed>
$coord-impact <event-id> @all <action needed>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py impact --group <group> --agent <agent> <event-id> @<agent|all> "<action needed>"
```

用于不能静默隐藏的错误：旧记录已经被执行、被引用，或是否已被消费不确定。目标 agent 会在 `sync` 的 `Needs Attention` 中看到该影响项。
```

Create `skills/coord-resolve-impact/SKILL.md`:

```markdown
---
name: coord-resolve-impact
description: 当用户输入 $coord-resolve-impact，或想关闭一个已处理的 coord impact 待处理项时使用。
---

# Coord 解决影响项

这是主 coord 协议的轻量子命令入口。先遵守同一 skills 根目录下 `coord/SKILL.md` 的主协议。

适用于：

```text
$coord-resolve-impact <impact-id> <result>
```

需要当前已有 `group=<group>` 和 `agent=<agent>`。如果缺失，先询问。

执行：

```bash
python3 <coord-skill-dir>/scripts/coord.py resolve-impact --group <group> --agent <agent> <impact-id> "<result>"
```

影响项处理完成后使用。关闭后普通 `sync` 和 `brief` 不再展示该 impact。
```

- [ ] **Step 4: Update README command list and scenario**

In `README.md`, add command rows for:

```markdown
| `$coord-retract <event-id> <reason>` | `$coord retract <event-id> <reason>` | 撤回未被消费的错误记录 |
| `$coord-correct <event-id> <final text>` | `$coord correct <event-id> <final text>` | 用最终正确版本替换旧记录 |
| `$coord-impact <event-id> @agent <action needed>` | `$coord impact <event-id> @agent <action needed>` | 标记已影响执行链路的错误 |
| `$coord-resolve-impact <impact-id> <result>` | `$coord resolve-impact <impact-id> <result>` | 关闭已处理的影响项 |
```

Add a short example under scenarios:

```markdown
纠错但不污染普通视图：

```text
$coord correct e-0011 "最终正确结论"
```

如果旧记录已经被执行：

```text
$coord impact e-0011 @executor "旧结论已被执行，请重新检查相关改动"
$coord resolve-impact i-0001 "已重查，无需改动"
```
```

- [ ] **Step 5: Run install test**

Run:

```bash
python3 -m unittest test_install.InstallScriptTest.test_install_syncs_owned_coord_skills_and_preserves_others -v
```

Expected: PASS. The install test should automatically include the new `coord-*` skill directories.

- [ ] **Step 6: Commit Task 5**

```bash
git add README.md skills/coord/SKILL.md skills/coord-retract/SKILL.md skills/coord-correct/SKILL.md skills/coord-impact/SKILL.md skills/coord-resolve-impact/SKILL.md
git commit -m "docs: document coord effective correction commands"
```

## Task 6: Full Verification

**Files:**
- No production edits expected.

- [ ] **Step 1: Run all coord script tests**

Run:

```bash
python3 -m unittest skills.coord.scripts.test_coord -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run install tests**

Run:

```bash
python3 -m unittest test_install -v
```

Expected: all tests PASS.

- [ ] **Step 3: Manually exercise a compact happy path**

Run:

```bash
tmp_root="$(mktemp -d)"
COORD_ROOT="$tmp_root" python3 skills/coord/scripts/coord.py join demo reviewer
COORD_ROOT="$tmp_root" python3 skills/coord/scripts/coord.py note --group demo --agent reviewer "旧结论"
COORD_ROOT="$tmp_root" python3 skills/coord/scripts/coord.py correct --group demo --agent reviewer e-0002 "最终结论"
COORD_ROOT="$tmp_root" python3 skills/coord/scripts/coord.py sync --group demo --agent reviewer
```

Expected sync output contains `最终结论` and does not contain `旧结论`.

- [ ] **Step 4: Check final git status**

Run:

```bash
git status --short
```

Expected: clean working tree after all commits.
