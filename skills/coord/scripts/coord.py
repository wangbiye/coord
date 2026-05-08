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
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
GLOB_CHARS = set("*?[")


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


def load_manifest(paths):
    return read_json(paths["manifest"], {"group": paths["base"].name, "agents": {}})


def current_questions(paths):
    states = {}
    order = []
    for record in read_jsonl(paths["questions"]):
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
    return [states[qid] for qid in order]


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


def render_event(event):
    text = event.get("text") or event.get("answer") or event.get("task") or event.get("summary") or ""
    target = event.get("target")
    route = f" -> @{target}" if target else ""
    return f"- {event['id']} {event['type']} @{event.get('agent', '?')}{route}: {text}"


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
    validate_name("agent", args.agent)
    with locked(root, args.group):
        paths = group_paths(root, args.group)
        if not paths["manifest"].exists():
            if not args.create:
                raise CoordError(f"group does not exist: {args.group}")
            create_group(root, args.group)
            print(f"created group {args.group}")
        manifest = load_manifest(paths)
        manifest.setdefault("agents", {})
        existing = manifest["agents"].get(args.agent)
        timestamp = now_iso()
        manifest["agents"][args.agent] = {
            "joined_at": existing.get("joined_at") if existing else timestamp,
            "last_seen_at": timestamp,
        }
        write_json(root, paths["manifest"], manifest)
        summary = agent_file(root, args.group, args.agent)
        if not summary.exists():
            summary.write_text(f"# Agent {args.agent}\n\nJoined group `{args.group}` at {timestamp}.\n")
        append_event(root, args.group, "join", args.agent, text=f"joined group {args.group}")
        print(f"joined {args.group} as {args.agent}")
        print(f"current identity: group={args.group} agent={args.agent}")


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
        append_event(root, args.group, "note", args.agent, text=text)
        append_text(root, agent_file(root, args.group, args.agent), f"\n## Note {now_iso()}\n\n{text}\n")
        print(f"noted for {args.group}/{args.agent}")


def cmd_ask(args):
    root = root_dir()
    target = args.target[1:] if args.target.startswith("@") else args.target
    if target != "all":
        validate_name("agent", target)
    with locked(root, args.group):
        paths = require_group(root, args.group)
        qid = next_id(current_questions(paths), "q")
        text = " ".join(args.text).strip()
        question = {
            "id": qid,
            "from": args.agent,
            "to": target,
            "status": "open",
            "created_at": now_iso(),
            "text": text,
        }
        append_jsonl(root, paths["questions"], question)
        append_event(root, args.group, "question", args.agent, target=target, question_id=qid, text=text)
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
        record = {
            "id": args.question_id,
            "from": args.agent,
            "status": "answered",
            "answered_at": now_iso(),
            "answer": answer,
        }
        append_jsonl(root, paths["questions"], record)
        append_event(root, args.group, "answer", args.agent, question_id=args.question_id, answer=answer)
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
        append_event(root, args.group, "handoff", args.agent, summary=summary)
        append_text(root, agent_file(root, args.group, args.agent), f"\n## Handoff {now_iso()}\n\n{summary}\n")
        print(f"recorded handoff for {args.group}/{args.agent}")


def cmd_sync(args):
    root = root_dir()
    with locked(root, args.group):
        paths = require_group(root, args.group)
        manifest = load_manifest(paths)
        questions = current_questions(paths)
        claims = active_claims(paths)
        events = read_jsonl(paths["events"])[-10:]

        print("# Coord Sync")
        print(f"Group: {args.group}")
        print(f"Agent: {args.agent}")
        print("Agents: " + (", ".join(sorted(manifest.get("agents", {}).keys())) or "(none)"))

        print("\n## Open Questions For This Agent")
        mine = [q for q in questions if q.get("status", "open") == "open" and q.get("to") in {args.agent, "all"}]
        print("\n".join(render_question(q) for q in mine) if mine else "(none)")

        print("\n## Recent Answers")
        answered = [q for q in questions if q.get("status") == "answered"]
        print("\n".join(render_question(q) for q in answered[-10:]) if answered else "(none)")

        print("\n## Active Claims")
        print("\n".join(render_claim(c) for c in claims) if claims else "(none)")

        print("\n## Recent Events")
        print("\n".join(render_event(e) for e in events) if events else "(none)")


def cmd_brief(args):
    root = root_dir()
    with locked(root, args.group):
        paths = require_group(root, args.group)
        manifest = load_manifest(paths)
        questions = current_questions(paths)
        claims = active_claims(paths)
        events = read_jsonl(paths["events"])[-15:]

        print("# Coord Brief")
        print(f"Group: {args.group}")
        print("Agents: " + (", ".join(sorted(manifest.get("agents", {}).keys())) or "(none)"))

        print("\n## Open Questions")
        open_questions = [q for q in questions if q.get("status", "open") == "open"]
        print("\n".join(render_question(q) for q in open_questions) if open_questions else "(none)")

        print("\n## Active Claims")
        print("\n".join(render_claim(c) for c in claims) if claims else "(none)")

        print("\n## Agent Summaries")
        summaries = read_agent_summaries(paths)
        if summaries:
            for agent, summary in summaries:
                print(f"\n### {agent}\n{summary}")
        else:
            print("(none)")

        print("\n## Recent Events")
        print("\n".join(render_event(e) for e in events) if events else "(none)")


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
