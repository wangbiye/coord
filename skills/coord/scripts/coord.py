#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-Unix fallback
    fcntl = None


DEFAULT_ROOT = Path("~/.coord")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
QUESTION_RE = re.compile(r"^q-\d{4}$")
EVENT_RE = re.compile(r"^e-\d{4}$")
IMPACT_RE = re.compile(r"^i-\d{4}$")
CORRECTABLE_EVENT_TYPES = {"note", "decision", "handoff", "question", "answer"}
INTERNAL_EVENT_TYPES = {"retract", "impact", "resolve-impact"}
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
GLOB_CHARS = set("*?[")

BUILTIN_ROLE_PROFILES = {
    "reviewer": "\n".join(
        [
            "- reviews spec, plan, code, tests, and delivery results.",
            "- In spec/plan phases, checks requirement completeness, internal consistency, edge cases, risks, acceptance criteria, and execution clarity.",
            "- In code phases, checks bugs, regressions, API contracts, test gaps, maintainability, and whether user requirements are met.",
            "- Uses applicable gstack review skills when available for spec/plan, UI/interaction, product-scope, engineering-direction, devex, or PR-like reviews: plan-ceo-review, plan-design-review, plan-eng-review, plan-devex-review, design-review, devex-review, or review.",
            "- If applicable gstack skills are unavailable or undiscoverable for a review that would benefit from them, states the limitation and records residual review risk.",
            "- Records gate verdicts for every review, including no-issue reviews: verdict=approved or verdict=changes_requested, reviewed artifacts, blocking issues, residual risk, and allowed next stage.",
            "- For UI/interaction implementation reviews, checks actual rendered behavior against the UI/交互需求说明 using browser, screenshot, or manual evidence where possible.",
            "- Does not edit files by default unless the user explicitly asks.",
            "- Treats review verdicts as independent gates; inspects referenced artifacts directly instead of relying only on planner summaries.",
            "- Leads with blocking findings and suggestions ordered by severity, and records a coord note even when there are no blocking issues.",
        ]
    ),
    "executor": "\n".join(
        [
            "- implements approved plans, reviewer-approved fixes, or direct user requests when no separate plan is needed.",
            "- Does not write or redesign the spec/plan by default; asks planner or the user when the approved plan is missing, stale, or contradicted by new requirements.",
            "- Implements, fixes, tests, and verifies the requested changes while staying aligned with the latest approved spec/plan and reviewer gate verdict.",
            "- Starts by syncing coordination state and claims file ranges before edits when needed.",
            "- When delegated by a planner or root planner, joins with the assigned unique agent name, syncs, and reads the referenced spec/plan before editing.",
            "- Stops for confirmation when requirements change, plans conflict, cross-agent dependencies appear, or a risky operation is needed.",
            "- Records implementation handoff before review: spec/plan paths, changed files, implementation summary, verification run, verification not run with reasons, deviations, UI/interaction evidence, and remaining risk.",
        ]
    ),
    "frontend": "\n".join(
        [
            "- Executes frontend work with focus on UI, interaction flow, state changes, responsive behavior, accessibility, and visual consistency.",
            "- In spec/plan phases, defines user-visible behavior, feedback states, page states, edge cases, and acceptance criteria.",
            "- In code phases, implements frontend changes and verifies the real interface behavior where possible.",
            "- Syncs before starting and records progress, verification, blockers, and remaining risks in coord.",
        ]
    ),
    "backend": "\n".join(
        [
            "- Executes backend work with focus on API contracts, data models, permissions, error handling, idempotency, compatibility, migrations, and test coverage.",
            "- In spec/plan phases, defines interface boundaries, data flow, failure cases, and validation strategy.",
            "- In code phases, implements backend changes, tests them, and verifies contract consistency.",
            "- Syncs before starting and records progress, verification, blockers, and remaining risks in coord.",
        ]
    ),
    "planner": "\n".join(
        [
            "- Plans solution, experience, and engineering direction before implementation.",
            "- MUST use applicable gstack skills when available: office-hours for problem framing, plan-ceo-review for scope and product direction, design-consultation or plan-design-review for UI/experience, plan-eng-review for architecture and test strategy, and plan-devex-review for developer-facing workflows.",
            "- If applicable gstack skills are unavailable or undiscoverable, states that limitation before planning and records the gap in coord.",
            "- writes or updates superpowers specs and implementation plans from confirmed user requirements, reviewer feedback, or approved planning conclusions.",
            "- Uses superpowers:brainstorming when creating or revising design specs; for UI or interaction work, includes a UI/交互需求说明 section before technical design.",
            "- Uses superpowers:writing-plans after spec approval, or when the user explicitly wants spec and plan drafted together.",
            "- Does not implement code by default; hands approved plans to executor.",
            "- When coordinating sub-agents, assigns unique agent names and requires each sub-agent to join and sync itself; does not impersonate another agent's join, handoff, note, or review verdict.",
            "- For large requirements, keeps Phase Definitions and acceptance contracts in the spec; records only concise Phase Kickoff Notes in coord with spec pointers, current status, deltas, dependencies, escalation rules, and expected handoff.",
            "- In large-requirement mode, the user starts each phase root planner by default; confirms phase results with the user before preparing the next phase kickoff.",
            "- Records artifact paths and ready_for_review status after writing or updating specs/plans; reviewer records the phase gate verdict.",
        ]
    ),
    "stabilizer": "\n".join(
        [
            "- Stabilizes work after implementation review and before final delivery.",
            "- Helps the user test, reproduces issues, investigates root cause, fixes bugs, and re-runs verification until the work is ready to ship or a blocker needs user decision.",
            "- Starts from coord brief/sync plus the actual spec, plan, code, tests, and latest reviewer gate verdict; does not rely only on the latest handoff.",
            "- Uses systematic debugging for bugs and keeps fixes aligned with the latest approved spec/plan and UI/交互需求说明.",
            "- For phase work, verifies against the source Phase Definition and latest approved gates instead of relying only on kickoff notes or handoffs.",
            "- Records final deliverable status: tests performed, bugs fixed, verification evidence, known residual risk, and any unresolved follow-up.",
        ]
    ),
}


class CoordError(Exception):
    pass


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def timestamp_slug():
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def root_dir():
    configured = os.environ.get("COORD_ROOT")
    return Path(configured or DEFAULT_ROOT).expanduser().resolve()


def validate_name(kind, value):
    if not NAME_RE.match(value):
        raise CoordError(f"invalid {kind}: {value}")
    return value


def ensure_inside(root, path):
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise CoordError(f"refusing to write outside coordination root: {resolved_path}")
    return resolved_path


def group_dir(root, group):
    validate_name("group", group)
    return ensure_inside(root, root / "groups" / group)


def agent_file(root, group, agent):
    validate_name("agent", agent)
    return ensure_inside(root, group_dir(root, group) / "agents" / f"{agent}.md")


@contextmanager
def locked(root, group=None):
    root.mkdir(parents=True, exist_ok=True)
    if group is None:
        lock_name = ".root.lock"
    else:
        validate_name("group", group)
        lock_name = f"{group}.lock"
    locks_dir = ensure_inside(root, root / "locks")
    lock_path = ensure_inside(root, locks_dir / lock_name)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def read_json(path, default):
    if not path.exists():
        return default
    with path.open() as fh:
        return json.load(fh)


def write_json(root, path, data):
    path = Path(path)
    if path.is_symlink():
        raise CoordError(f"refusing to write symlink: {path}")
    path = ensure_inside(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy_tmp_candidate = path.with_name(f"{path.name}.tmp")
    if legacy_tmp_candidate.is_symlink():
        raise CoordError(f"refusing to write symlink: {legacy_tmp_candidate}")
    ensure_inside(root, legacy_tmp_candidate)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            if tmp_path.is_symlink():
                raise CoordError(f"refusing to write symlink: {tmp_path}")
            ensure_inside(root, tmp_path)
            tmp.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def read_jsonl(path):
    if not path.exists():
        return []
    records = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def append_jsonl(root, path, record):
    path = ensure_inside(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def append_text(root, path, text):
    path = ensure_inside(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(text)


def group_paths(root, group):
    base = group_dir(root, group)
    return {
        "base": base,
        "manifest": base / "manifest.json",
        "events": base / "events.jsonl",
        "questions": base / "questions.jsonl",
        "claims": base / "claims.json",
        "shared": base / "shared.md",
        "decisions": base / "decisions.md",
        "agents": base / "agents",
    }


def require_group(root, group):
    paths = group_paths(root, group)
    if not paths["manifest"].exists():
        raise CoordError(f"group does not exist: {group}")
    return paths


def next_id(records, prefix):
    max_id = 0
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d{{4}})$")
    for record in records:
        raw = record.get("id")
        match = pattern.match(raw or "")
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"{prefix}-{max_id + 1:04d}"


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


def next_impact_id(events):
    return next_id([event for event in events if event.get("impact_id")], "i")


def append_event(root, group, event_type, agent, **fields):
    paths = group_paths(root, group)
    event_id = next_id(read_jsonl(paths["events"]), "e")
    record = {
        "id": event_id,
        "type": event_type,
        "agent": agent,
        "created_at": now_iso(),
        **fields,
    }
    append_jsonl(root, paths["events"], record)
    return record


def append_agent_markdown_entry(root, group, agent, kind, event_id, text):
    append_text(root, agent_file(root, group, agent), f"\n## {kind} {event_id} {now_iso()}\n\n{text}\n")


def load_manifest(paths):
    return read_json(paths["manifest"], {"group": paths["base"].name, "agents": {}})


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
        if qid not in states:
            order.append(qid)
        prior = states.get(qid, {})
        if record.get("status") == "answered" and "answer" in record:
            states[qid] = {
                **prior,
                "status": "answered",
                "answered_at": record.get("answered_at"),
                "answer": record.get("answer", ""),
                "answer_by": record.get("from"),
            }
        else:
            states[qid] = {**prior, **record}
    return [states[qid] for qid in order if states[qid].get("text") and states[qid].get("to")]


def active_claims(paths):
    data = read_json(paths["claims"], {"claims": []})
    return [claim for claim in data.get("claims", []) if claim.get("status") == "active"]


def parse_files(raw):
    if not raw:
        return []
    files = []
    for item in raw.split(","):
        item = item.strip()
        if item:
            files.append(normalize_claim_path(item))
    return files


def normalize_claim_path(raw):
    path = raw.strip().replace("\\", "/")
    if not path:
        raise CoordError("invalid claim path: empty")
    if path.startswith("/") or WINDOWS_DRIVE_RE.match(path):
        raise CoordError(f"invalid claim path: {raw}")

    parts = []
    for part in path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise CoordError(f"invalid claim path: {raw}")
        parts.append(part)
    if not parts:
        raise CoordError(f"invalid claim path: {raw}")
    return "/".join(parts)


def has_glob(pattern):
    return any(char in pattern for char in GLOB_CHARS)


def static_prefix(pattern):
    parts = []
    for part in pattern.split("/"):
        if any(char in part for char in GLOB_CHARS):
            break
        parts.append(part)
    return "/".join(parts)


def prefixes_overlap(left, right):
    if not left or not right:
        return True
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def patterns_overlap(left, right):
    if left == right:
        return True
    if has_glob(left) or has_glob(right):
        return prefixes_overlap(static_prefix(left), static_prefix(right))
    return left.startswith(right + "/") or right.startswith(left + "/")


def render_question(question):
    target = question.get("to", "all")
    status = question.get("status", "open")
    line = f"- {question['id']} from {question.get('from', '?')} to @{target}: {question.get('text', '')}"
    if status == "answered":
        line += f"\n  answer by {question.get('answer_by', '?')}: {question.get('answer', '')}"
    return line


def render_claim(claim):
    files = ", ".join(claim.get("files", [])) or "(no files)"
    return f"- {claim['id']} @{claim['agent']}: {claim.get('task', '')} [{files}]"


def render_impact(impact):
    target = impact.get("target", "all")
    return (
        f"- {impact['impact_id']} from @{impact.get('agent', '?')} "
        f"about {impact.get('target_event_id', '?')} to @{target}: {impact.get('text', '')}"
    )


def render_event(event):
    text = event.get("text") or event.get("answer") or event.get("task") or event.get("summary") or ""
    target = event.get("target")
    route = f" -> @{target}" if target else ""
    return f"- {event['id']} {event['type']} @{event.get('agent', '?')}{route}: {text}"


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


def read_agent_summaries(paths):
    summaries = []
    agents_dir = paths["agents"]
    if not agents_dir.exists():
        return summaries
    for path in sorted(agents_dir.glob("*.md")):
        content = path.read_text().strip()
        if content:
            summaries.append((path.stem, content))
    return summaries


def builtin_role_for_agent(agent):
    if agent == "executer" or agent.startswith("executer-") or agent.startswith("executer_"):
        raise CoordError("unsupported agent name: executer; use executor")
    if agent in BUILTIN_ROLE_PROFILES:
        return agent
    for role in BUILTIN_ROLE_PROFILES:
        if agent.startswith(f"{role}-") and len(agent) > len(role) + 1:
            return role
        if agent.startswith(f"{role}_") and len(agent) > len(role) + 1:
            return role
    return None


def print_existing_agent_warning(group, agent, role):
    print(f"warning: agent {agent} already exists in group {group}.")
    print("建议为新会话改用唯一 agent 名；只有明确要恢复同一会话身份时才复用当前名称。")
    if role:
        print(
            f"{role}-* 自动继承 {role} 内置角色；{role}_* 也支持，"
            f"连接符支持中划线和下划线，例如 {role}-2 或 {role}_2。"
        )
        return
    print(
        "reviewer-* / reviewer_*、executor-* / executor_*、frontend-* / frontend_*、"
        "backend-* / backend_*、planner-* / planner_*、stabilizer-* / stabilizer_* "
        "自动继承对应内置角色；连接符支持中划线和下划线。"
    )


def role_data_for_join(agent, existing, timestamp):
    role = builtin_role_for_agent(agent)
    if existing and existing.get("role_source") == "custom":
        return {
            "role": existing.get("role", role or agent),
            "role_source": "custom",
            "role_profile": existing.get("role_profile", ""),
            "role_updated_at": existing.get("role_updated_at", timestamp),
        }
    if role:
        return {
            "role": role,
            "role_source": "builtin",
            "role_profile": BUILTIN_ROLE_PROFILES[role],
            "role_updated_at": existing.get("role_updated_at") if existing else timestamp,
        }
    return {
        "role": existing.get("role") if existing else None,
        "role_source": existing.get("role_source") if existing else None,
        "role_profile": existing.get("role_profile", "") if existing else "",
        "role_updated_at": existing.get("role_updated_at") if existing else None,
    }


def compact_role_data(data):
    return {key: value for key, value in data.items() if value not in {None, ""}}


def render_role_profile(agent, data):
    role = data.get("role")
    source = data.get("role_source")
    profile = data.get("role_profile")
    if not profile:
        return (
            f"Agent: {agent}\n"
            "Role: (none)\n"
            "Source: none\n"
            "Role Instructions:\n"
            "(none recorded)"
        )
    return (
        f"Agent: {agent}\n"
        f"Role: {role or '(none)'}\n"
        f"Source: {source or 'custom'}\n"
        "Role Instructions:\n"
        f"{profile}"
    )


def role_section(agent, data):
    return "\n## Role Profile\n\n" + render_role_profile(agent, data) + "\n"


def upsert_agent_role_section(root, group, agent, data, joined_at=None):
    summary = agent_file(root, group, agent)
    if summary.exists():
        content = summary.read_text()
    else:
        joined_line = f"Joined group `{group}`"
        if joined_at:
            joined_line += f" at {joined_at}"
        content = f"# Agent {agent}\n\n{joined_line}.\n"

    section = role_section(agent, data).rstrip() + "\n"
    if "\n## Role Profile\n" in content:
        content = re.sub(r"\n## Role Profile\n\n.*?(?=\n## |\Z)", "\n" + section, content, flags=re.S)
    else:
        if not content.endswith("\n"):
            content += "\n"
        content += section
    summary.write_text(content)


def print_join_role_card(agent, role_data):
    source = role_data.get("role_source")
    profile = role_data.get("role_profile")
    if source == "builtin":
        print(f"matched built-in role: {role_data.get('role')}")
    elif source == "custom":
        print(f"using custom role: {role_data.get('role')}")
    else:
        print("no built-in role matched")
    print()
    print(render_role_profile(agent, role_data))
    print()
    print("If this role is not right for the current task, describe the adjustment; after checking it against coord safety boundaries and current group decisions, record it with the role command.")


def cmd_init(args):
    root = root_dir()
    validate_name("group", args.group)
    with locked(root, args.group):
        created = create_group(root, args.group)
        print(f"created group {args.group}" if created else f"group {args.group} already exists")


def create_group(root, group):
    paths = group_paths(root, group)
    paths["agents"].mkdir(parents=True, exist_ok=True)
    manifest = {
        "group": group,
        "created_at": now_iso(),
        "agents": {},
    }
    if not paths["manifest"].exists():
        write_json(root, paths["manifest"], manifest)
        write_json(root, paths["claims"], {"claims": []})
        paths["events"].touch()
        paths["questions"].touch()
        paths["shared"].write_text(f"# {group} Shared State\n\n")
        paths["decisions"].write_text(f"# {group} Decisions\n\n")
        return True
    return False


def active_group_names(root):
    groups_dir = root / "groups"
    if not groups_dir.exists():
        return []
    return sorted(path.name for path in groups_dir.iterdir() if path.is_dir() and (path / "manifest.json").exists())


def archive_group(root, group):
    paths = require_group(root, group)
    archive_root = ensure_inside(root, root / "archive")
    archive_root.mkdir(parents=True, exist_ok=True)
    base_name = f"{group}-{timestamp_slug()}"
    target = ensure_inside(root, archive_root / base_name)
    suffix = 1
    while target.exists():
        target = ensure_inside(root, archive_root / f"{base_name}-{suffix}")
        suffix += 1
    shutil.move(str(paths["base"]), str(target))
    return target


def cmd_join(args):
    root = root_dir()
    role = builtin_role_for_agent(args.agent)
    validate_name("agent", args.agent)
    with locked(root, args.group):
        paths = group_paths(root, args.group)
        if not paths["manifest"].exists():
            create_group(root, args.group)
            print(f"created group {args.group}")
        manifest = load_manifest(paths)
        manifest.setdefault("agents", {})
        existing = manifest["agents"].get(args.agent)
        if existing:
            print_existing_agent_warning(args.group, args.agent, role)
        timestamp = now_iso()
        role_data = role_data_for_join(args.agent, existing, timestamp)
        manifest["agents"][args.agent] = {
            "joined_at": existing.get("joined_at") if existing else timestamp,
            "last_seen_at": timestamp,
            **compact_role_data(role_data),
        }
        write_json(root, paths["manifest"], manifest)
        summary = agent_file(root, args.group, args.agent)
        if not summary.exists():
            summary.write_text(f"# Agent {args.agent}\n\nJoined group `{args.group}` at {timestamp}.\n")
        upsert_agent_role_section(root, args.group, args.agent, role_data, joined_at=timestamp)
        append_event(root, args.group, "join", args.agent, text=f"joined group {args.group}")
        print(f"joined {args.group} as {args.agent}")
        print(f"current identity: group={args.group} agent={args.agent}")
        print_join_role_card(args.agent, role_data)


def cmd_archive(args):
    root = root_dir()
    validate_name("group", args.group)
    with locked(root, args.group):
        target = archive_group(root, args.group)
        print(f"archived {args.group} to {target}")


def cmd_archive_all(args):
    root = root_dir()
    groups = active_group_names(root)
    if not groups:
        print("no active groups to archive")
        return
    for group in groups:
        with locked(root, group):
            paths = group_paths(root, group)
            if not paths["manifest"].exists():
                continue
            target = archive_group(root, group)
            print(f"archived {group} to {target}")


def cmd_note(args):
    root = root_dir()
    with locked(root, args.group):
        require_group(root, args.group)
        text = " ".join(args.text).strip()
        event = append_event(root, args.group, "note", args.agent, text=text)
        append_agent_markdown_entry(root, args.group, args.agent, "Note", event["id"], text)
        print(f"noted for {args.group}/{args.agent}")


def cmd_role(args):
    root = root_dir()
    builtin_role_for_agent(args.agent)
    with locked(root, args.group):
        paths = require_group(root, args.group)
        manifest = load_manifest(paths)
        agents = manifest.setdefault("agents", {})
        existing = agents.get(args.agent)
        if existing is None:
            raise CoordError(f"agent not joined: {args.agent}")
        profile = " ".join(args.text).strip()
        if not profile:
            raise CoordError("role profile is required")
        timestamp = now_iso()
        role_data = {
            "role": existing.get("role") or builtin_role_for_agent(args.agent) or args.agent,
            "role_source": "custom",
            "role_profile": profile,
            "role_updated_at": timestamp,
        }
        agents[args.agent] = {
            **existing,
            "last_seen_at": timestamp,
            **role_data,
        }
        write_json(root, paths["manifest"], manifest)
        upsert_agent_role_section(root, args.group, args.agent, role_data, joined_at=existing.get("joined_at"))
        append_event(root, args.group, "role", args.agent, text=f"updated role profile for {args.agent}")
        print(f"recorded role profile for {args.group}/{args.agent}")


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


def cmd_ask(args):
    root = root_dir()
    target = args.target[1:] if args.target.startswith("@") else args.target
    if target != "all":
        validate_name("agent", target)
    with locked(root, args.group):
        paths = require_group(root, args.group)
        qid = next_id(current_questions(paths), "q")
        text = " ".join(args.text).strip()
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
        print(f"created {qid} to @{target}")


def cmd_answer(args):
    root = root_dir()
    if not QUESTION_RE.match(args.question_id):
        raise CoordError(f"invalid question id: {args.question_id}")
    with locked(root, args.group):
        paths = require_group(root, args.group)
        questions = current_questions(paths)
        question = next((question for question in questions if question.get("id") == args.question_id), None)
        if question is None:
            raise CoordError(f"question not found: {args.question_id}")
        if question.get("status") == "answered":
            raise CoordError(f"question already answered: {args.question_id}")
        target = question.get("to", "all")
        if target not in {"all", args.agent}:
            raise CoordError(f"question {args.question_id} is targeted to @{target}; @{args.agent} cannot answer")
        answer = " ".join(args.text).strip()
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
        print(f"answered {args.question_id}")


def cmd_decision(args):
    root = root_dir()
    with locked(root, args.group):
        require_group(root, args.group)
        text = " ".join(args.text).strip()
        append_event(root, args.group, "decision", args.agent, text=text)
        append_text(root, group_paths(root, args.group)["decisions"], f"- {now_iso()} @{args.agent}: {text}\n")
        print(f"recorded decision for {args.group}")


def cmd_claim(args):
    root = root_dir()
    with locked(root, args.group):
        paths = require_group(root, args.group)
        claims_data = read_json(paths["claims"], {"claims": []})
        files = parse_files(args.files)
        for claim in claims_data.get("claims", []):
            if claim.get("status") != "active":
                continue
            if claim.get("agent") == args.agent:
                continue
            for existing in claim.get("files", []):
                for requested in files:
                    if patterns_overlap(existing, requested):
                        raise CoordError(f"claim conflicts with active claim {claim['id']}: {existing}")
        claim_id = next_id(claims_data.get("claims", []), "c")
        claim = {
            "id": claim_id,
            "agent": args.agent,
            "task": " ".join(args.task).strip(),
            "files": files,
            "status": "active",
            "created_at": now_iso(),
        }
        claims_data.setdefault("claims", []).append(claim)
        write_json(root, paths["claims"], claims_data)
        append_event(root, args.group, "claim", args.agent, task=claim["task"], claim_id=claim_id, files=files)
        print(f"created claim {claim_id}")


def cmd_release(args):
    root = root_dir()
    with locked(root, args.group):
        paths = require_group(root, args.group)
        claims_data = read_json(paths["claims"], {"claims": []})
        for claim in claims_data.get("claims", []):
            if claim.get("id") == args.claim_id:
                claim["status"] = "released"
                claim["released_at"] = now_iso()
                claim["released_by"] = args.agent
                write_json(root, paths["claims"], claims_data)
                append_event(root, args.group, "release", args.agent, claim_id=args.claim_id, text=f"released {args.claim_id}")
                print(f"released {args.claim_id}")
                return
        raise CoordError(f"claim not found: {args.claim_id}")


def cmd_handoff(args):
    root = root_dir()
    with locked(root, args.group):
        require_group(root, args.group)
        summary = " ".join(args.summary).strip()
        event = append_event(root, args.group, "handoff", args.agent, summary=summary)
        append_agent_markdown_entry(root, args.group, args.agent, "Handoff", event["id"], summary)
        print(f"recorded handoff for {args.group}/{args.agent}")


def cmd_sync(args):
    root = root_dir()
    with locked(root, args.group):
        paths = require_group(root, args.group)
        manifest = load_manifest(paths)
        events = read_jsonl(paths["events"])
        event_state = effective_event_state(events)
        questions = current_questions(paths, event_state)
        claims = active_claims(paths)

        print("# Coord Sync")
        print(f"Group: {args.group}")
        print(f"Agent: {args.agent}")
        print("Agents: " + (", ".join(sorted(manifest.get("agents", {}).keys())) or "(none)"))

        print("\n## Current Agent Profile")
        agent_data = manifest.get("agents", {}).get(args.agent, {})
        print(render_role_profile(args.agent, agent_data))

        print("\n## Open Questions For This Agent")
        mine = [q for q in questions if q.get("status", "open") == "open" and q.get("to") in {args.agent, "all"}]
        print("\n".join(render_question(q) for q in mine) if mine else "(none)")

        print("\n## Recent Answers")
        answered = [q for q in questions if q.get("status") == "answered"]
        print("\n".join(render_question(q) for q in answered[-10:]) if answered else "(none)")

        print("\n## Active Claims")
        print("\n".join(render_claim(c) for c in claims) if claims else "(none)")

        print("\n## Needs Attention")
        my_impacts = [
            impact
            for impact in event_state["open_impacts"]
            if impact.get("target") in {args.agent, "all"}
        ]
        print("\n".join(render_impact(impact) for impact in my_impacts) if my_impacts else "(none)")

        print("\n## Recent Effective Events")
        recent_events = event_state["effective_events"][-10:]
        print("\n".join(render_event(e) for e in recent_events) if recent_events else "(none)")


def cmd_brief(args):
    root = root_dir()
    with locked(root, args.group):
        paths = require_group(root, args.group)
        manifest = load_manifest(paths)
        events = read_jsonl(paths["events"])
        event_state = effective_event_state(events)
        questions = current_questions(paths, event_state)
        claims = active_claims(paths)

        print("# Coord Brief")
        print(f"Group: {args.group}")
        print("Agents: " + (", ".join(sorted(manifest.get("agents", {}).keys())) or "(none)"))

        print("\n## Agent Profiles")
        agents = manifest.get("agents", {})
        if agents:
            for agent in sorted(agents):
                data = agents[agent]
                role = data.get("role") or "(none)"
                source = data.get("role_source") or "none"
                print(f"- @{agent}: role={role} source={source}")
        else:
            print("(none)")

        print("\n## Open Questions")
        open_questions = [q for q in questions if q.get("status", "open") == "open"]
        print("\n".join(render_question(q) for q in open_questions) if open_questions else "(none)")

        print("\n## Active Claims")
        print("\n".join(render_claim(c) for c in claims) if claims else "(none)")

        print("\n## Needs Attention")
        print("\n".join(render_impact(impact) for impact in event_state["open_impacts"]) if event_state["open_impacts"] else "(none)")

        print("\n## Agent Summaries")
        summaries = render_effective_agent_summaries(event_state["effective_events"])
        if summaries:
            for agent, summary in summaries:
                print(f"\n### {agent}\n{summary}")
        else:
            print("(none)")

        print("\n## Recent Effective Events")
        recent_events = event_state["effective_events"][-15:]
        print("\n".join(render_event(e) for e in recent_events) if recent_events else "(none)")


def cmd_status(args):
    root = root_dir()
    with locked(root, args.group):
        paths = require_group(root, args.group)
        manifest = load_manifest(paths)
        questions = current_questions(paths)
        open_count = len([q for q in questions if q.get("status", "open") == "open"])
        answered_count = len([q for q in questions if q.get("status") == "answered"])
        print(f"group={args.group}")
        print(f"agents={len(manifest.get('agents', {}))}")
        print(f"open_questions={open_count}")
        print(f"answered_questions={answered_count}")
        print(f"active_claims={len(active_claims(paths))}")


def cmd_list(args):
    root = root_dir()
    mode = args.what or "groups"
    if mode == "groups":
        groups_dir = root / "groups"
        groups = (
            sorted(path.name for path in groups_dir.iterdir() if path.is_dir() and (path / "manifest.json").exists())
            if groups_dir.exists()
            else []
        )
        print("\n".join(groups) if groups else "(none)")
        return
    if not args.group:
        raise CoordError("--group is required for list agents")
    with locked(root, args.group):
        paths = require_group(root, args.group)
        manifest = load_manifest(paths)
        agents = sorted(manifest.get("agents", {}).keys())
        print("\n".join(agents) if agents else "(none)")


def add_context_args(parser):
    parser.add_argument("--group", required=True)
    parser.add_argument("--agent", required=True)


def build_parser():
    parser = argparse.ArgumentParser(description="Local coordination helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("group")
    init.set_defaults(func=cmd_init)

    join = subparsers.add_parser("join")
    join.add_argument("group")
    join.add_argument("agent")
    join.add_argument("--create", action="store_true")
    join.set_defaults(func=cmd_join)

    archive = subparsers.add_parser("archive")
    archive.add_argument("group")
    archive.set_defaults(func=cmd_archive)

    archive_all = subparsers.add_parser("archive-all")
    archive_all.set_defaults(func=cmd_archive_all)

    sync = subparsers.add_parser("sync")
    add_context_args(sync)
    sync.set_defaults(func=cmd_sync)

    brief = subparsers.add_parser("brief")
    brief.add_argument("--group", required=True)
    brief.set_defaults(func=cmd_brief)

    status = subparsers.add_parser("status")
    status.add_argument("--group", required=True)
    status.set_defaults(func=cmd_status)

    list_cmd = subparsers.add_parser("list")
    list_cmd.add_argument("what", nargs="?", choices=["groups", "agents"])
    list_cmd.add_argument("--group")
    list_cmd.set_defaults(func=cmd_list)

    note = subparsers.add_parser("note")
    add_context_args(note)
    note.add_argument("text", nargs="+")
    note.set_defaults(func=cmd_note)

    role = subparsers.add_parser("role")
    add_context_args(role)
    role.add_argument("text", nargs="+")
    role.set_defaults(func=cmd_role)

    retract = subparsers.add_parser("retract")
    add_context_args(retract)
    retract.add_argument("event_id")
    retract.add_argument("reason", nargs="+")
    retract.set_defaults(func=cmd_retract)

    correct = subparsers.add_parser("correct")
    add_context_args(correct)
    correct.add_argument("event_id")
    correct.add_argument("text", nargs="+")
    correct.set_defaults(func=cmd_correct)

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

    ask = subparsers.add_parser("ask")
    add_context_args(ask)
    ask.add_argument("target")
    ask.add_argument("text", nargs="+")
    ask.set_defaults(func=cmd_ask)

    answer = subparsers.add_parser("answer")
    add_context_args(answer)
    answer.add_argument("question_id")
    answer.add_argument("text", nargs="+")
    answer.set_defaults(func=cmd_answer)

    decision = subparsers.add_parser("decision")
    add_context_args(decision)
    decision.add_argument("text", nargs="+")
    decision.set_defaults(func=cmd_decision)

    claim = subparsers.add_parser("claim")
    add_context_args(claim)
    claim.add_argument("--files", default="")
    claim.add_argument("task", nargs="+")
    claim.set_defaults(func=cmd_claim)

    release = subparsers.add_parser("release")
    add_context_args(release)
    release.add_argument("claim_id")
    release.set_defaults(func=cmd_release)

    handoff = subparsers.add_parser("handoff")
    add_context_args(handoff)
    handoff.add_argument("summary", nargs="+")
    handoff.set_defaults(func=cmd_handoff)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except CoordError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
