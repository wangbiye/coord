#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("coord.py")


class CoordCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "coord-root"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, ok=True):
        env = os.environ.copy()
        env["COORD_ROOT"] = str(self.root)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            env=env,
        )
        if ok and result.returncode != 0:
            self.fail(
                f"coord.py {' '.join(args)} failed\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        if not ok and result.returncode == 0:
            self.fail(f"coord.py {' '.join(args)} unexpectedly passed\n{result.stdout}")
        return result

    def read_json(self, relative):
        return json.loads((self.root / relative).read_text())

    def test_init_and_join_create_group_and_agent_manifest(self):
        init = self.run_cli("init", "group-a")
        self.assertIn("created group group-a", init.stdout)

        join = self.run_cli("join", "group-a", "frontend")
        self.assertIn("joined group-a as frontend", join.stdout)

        manifest = self.read_json("groups/group-a/manifest.json")
        self.assertEqual(manifest["group"], "group-a")
        self.assertIn("frontend", manifest["agents"])
        self.assertTrue((self.root / "groups/group-a/agents/frontend.md").exists())

    def test_only_coord_root_env_var_controls_default_root(self):
        default_home = Path(self.tmp.name) / "home"
        unrelated_root = Path(self.tmp.name) / "unrelated-root"
        env = os.environ.copy()
        env.pop("COORD_ROOT", None)
        env["HOME"] = str(default_home)
        env["OTHER_COORD_ROOT"] = str(unrelated_root)

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "init", "group-a"],
            text=True,
            capture_output=True,
            env=env,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((default_home / ".coord/groups/group-a/manifest.json").exists())
        self.assertFalse((unrelated_root / "groups/group-a/manifest.json").exists())

    def test_join_missing_group_fails_without_create_flag(self):
        result = self.run_cli("join", "group-a", "frontend", ok=False)
        self.assertIn("group does not exist: group-a", result.stderr)
        self.assertFalse((self.root / "groups/group-a").exists())

    def test_join_missing_group_with_create_flag_initializes_group_and_joins(self):
        join = self.run_cli("join", "group-a", "frontend", "--create")
        self.assertIn("created group group-a", join.stdout)
        self.assertIn("joined group-a as frontend", join.stdout)

        manifest = self.read_json("groups/group-a/manifest.json")
        self.assertEqual(manifest["group"], "group-a")
        self.assertIn("frontend", manifest["agents"])

    def test_join_builtin_role_records_profile_and_prints_role_card(self):
        self.run_cli("init", "group-a")

        join = self.run_cli("join", "group-a", "reviewer")

        self.assertIn("matched built-in role: reviewer", join.stdout)
        self.assertIn("Role Instructions", join.stdout)
        self.assertIn("reviews spec, plan, code, tests, and delivery results", join.stdout)
        self.assertIn("If this role is not right for the current task", join.stdout)
        manifest = self.read_json("groups/group-a/manifest.json")
        reviewer = manifest["agents"]["reviewer"]
        self.assertEqual("reviewer", reviewer["role"])
        self.assertEqual("builtin", reviewer["role_source"])
        self.assertIn("reviews spec, plan, code, tests, and delivery results", reviewer["role_profile"])
        summary = (self.root / "groups/group-a/agents/reviewer.md").read_text()
        self.assertIn("## Role Profile", summary)
        self.assertIn("Role: reviewer", summary)

    def test_join_rejects_executer_and_points_to_executor(self):
        self.run_cli("init", "group-a")

        result = self.run_cli("join", "group-a", "executer", ok=False)

        self.assertIn("unsupported agent name: executer; use executor", result.stderr)
        manifest = self.read_json("groups/group-a/manifest.json")
        self.assertNotIn("executer", manifest["agents"])

    def test_role_command_records_custom_profile_for_current_agent(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "reviewer")

        role = self.run_cli(
            "role",
            "--group",
            "group-a",
            "--agent",
            "reviewer",
            "只审查 spec/plan，不审查代码；发现需求歧义时先提问。",
        )

        self.assertIn("recorded role profile for group-a/reviewer", role.stdout)
        manifest = self.read_json("groups/group-a/manifest.json")
        reviewer = manifest["agents"]["reviewer"]
        self.assertEqual("reviewer", reviewer["role"])
        self.assertEqual("custom", reviewer["role_source"])
        self.assertIn("只审查 spec/plan", reviewer["role_profile"])
        summary = (self.root / "groups/group-a/agents/reviewer.md").read_text()
        self.assertIn("Source: custom", summary)
        self.assertIn("只审查 spec/plan", summary)

    def test_sync_prints_current_agent_role_profile(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "executor")

        sync = self.run_cli("sync", "--group", "group-a", "--agent", "executor")

        self.assertIn("## Current Agent Profile", sync.stdout)
        self.assertIn("Role: executor", sync.stdout)
        self.assertIn("Source: builtin", sync.stdout)
        self.assertIn("executes changes from confirmed specs, plans, user requests, or reviewer feedback", sync.stdout)

    def test_ask_answer_and_sync_are_scoped_to_group_and_agent(self):
        self.run_cli("init", "group-a")
        self.run_cli("init", "group-b")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("join", "group-a", "backend")
        self.run_cli("join", "group-b", "backend")

        ask = self.run_cli(
            "ask",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            "@backend",
            "接口错误码最终按哪套处理",
        )
        self.assertIn("q-0001", ask.stdout)

        backend_sync = self.run_cli("sync", "--group", "group-a", "--agent", "backend")
        self.assertIn("q-0001", backend_sync.stdout)
        self.assertIn("接口错误码最终按哪套处理", backend_sync.stdout)

        other_group_sync = self.run_cli("sync", "--group", "group-b", "--agent", "backend")
        self.assertNotIn("q-0001", other_group_sync.stdout)

        answer = self.run_cli(
            "answer",
            "--group",
            "group-a",
            "--agent",
            "backend",
            "q-0001",
            "按 ApiErrorCode 统一处理",
        )
        self.assertIn("answered q-0001", answer.stdout)

        frontend_sync = self.run_cli("sync", "--group", "group-a", "--agent", "frontend")
        self.assertIn("q-0001 from frontend to @backend", frontend_sync.stdout)
        self.assertIn("answer by backend", frontend_sync.stdout)
        self.assertIn("按 ApiErrorCode 统一处理", frontend_sync.stdout)

    def test_claim_rejects_overlapping_active_file_claim(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("join", "group-a", "backend")

        claim = self.run_cli(
            "claim",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            "--files",
            "src/login/**",
            "登录页 UI 调整",
        )
        self.assertIn("c-0001", claim.stdout)

        conflict = self.run_cli(
            "claim",
            "--group",
            "group-a",
            "--agent",
            "backend",
            "--files",
            "src/login/form.ts",
            "登录接口适配",
            ok=False,
        )
        self.assertIn("conflicts with active claim c-0001", conflict.stderr)

    def test_handoff_updates_agent_summary_and_recent_events(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")

        self.run_cli(
            "handoff",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            "完成登录页入口分析，下一步检查表单校验。",
        )

        summary = (self.root / "groups/group-a/agents/frontend.md").read_text()
        self.assertIn("完成登录页入口分析", summary)

        brief = self.run_cli("brief", "--group", "group-a")
        self.assertIn("完成登录页入口分析", brief.stdout)

    def test_archive_moves_group_out_of_active_groups_and_preserves_files(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("note", "--group", "group-a", "--agent", "frontend", "准备归档")

        archive = self.run_cli("archive", "group-a")
        self.assertIn("archived group-a to", archive.stdout)

        active_group = self.root / "groups/group-a"
        self.assertFalse(active_group.exists())

        archive_root = self.root / "archive"
        archived_dirs = list(archive_root.glob("group-a-*"))
        self.assertEqual(len(archived_dirs), 1)
        archived = archived_dirs[0]
        self.assertTrue((archived / "manifest.json").exists())
        self.assertTrue((archived / "events.jsonl").exists())
        self.assertTrue((archived / "agents/frontend.md").exists())

        groups = self.run_cli("list", "groups")
        self.assertNotIn("group-a", groups.stdout)

    def test_group_lock_is_stored_outside_movable_group_directory(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("note", "--group", "group-a", "--agent", "frontend", "记录")

        self.assertTrue((self.root / "locks/group-a.lock").exists())
        self.assertFalse((self.root / "groups/group-a/.coord.lock").exists())

        self.run_cli("archive", "group-a")
        archived = next((self.root / "archive").glob("group-a-*"))
        self.assertFalse((archived / ".coord.lock").exists())
        self.assertTrue((self.root / "locks/group-a.lock").exists())

    def test_group_can_be_recreated_after_archive_without_touching_archive(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("archive", "group-a")
        archived = next((self.root / "archive").glob("group-a-*"))

        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "backend")

        active_manifest = self.read_json("groups/group-a/manifest.json")
        archived_manifest = json.loads((archived / "manifest.json").read_text())
        self.assertIn("backend", active_manifest["agents"])
        self.assertIn("frontend", archived_manifest["agents"])

    def test_archive_missing_group_fails_without_creating_archive(self):
        result = self.run_cli("archive", "missing-group", ok=False)
        self.assertIn("group does not exist: missing-group", result.stderr)
        self.assertFalse((self.root / "archive").exists())

    def test_archive_all_moves_all_active_groups_and_ignores_non_groups(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("note", "--group", "group-a", "--agent", "frontend", "准备归档 A")
        self.run_cli("init", "group-b")
        self.run_cli("join", "group-b", "backend")
        self.run_cli("note", "--group", "group-b", "--agent", "backend", "准备归档 B")
        (self.root / "groups/broken").mkdir(parents=True)

        archive = self.run_cli("archive-all")

        self.assertIn("archived group-a to", archive.stdout)
        self.assertIn("archived group-b to", archive.stdout)
        self.assertNotIn("broken", archive.stdout)
        self.assertFalse((self.root / "groups/group-a").exists())
        self.assertFalse((self.root / "groups/group-b").exists())
        self.assertTrue((self.root / "groups/broken").exists())

        archive_root = self.root / "archive"
        archived_a = list(archive_root.glob("group-a-*"))
        archived_b = list(archive_root.glob("group-b-*"))
        self.assertEqual(len(archived_a), 1)
        self.assertEqual(len(archived_b), 1)
        self.assertTrue((archived_a[0] / "manifest.json").exists())
        self.assertTrue((archived_a[0] / "events.jsonl").exists())
        self.assertTrue((archived_a[0] / "agents/frontend.md").exists())
        self.assertTrue((archived_b[0] / "manifest.json").exists())
        self.assertTrue((archived_b[0] / "events.jsonl").exists())
        self.assertTrue((archived_b[0] / "agents/backend.md").exists())

        groups = self.run_cli("list", "groups")
        self.assertEqual("(none)", groups.stdout.strip())

    def test_archive_all_reports_when_no_active_groups_exist(self):
        archive = self.run_cli("archive-all")

        self.assertEqual("no active groups to archive", archive.stdout.strip())
        self.assertFalse((self.root / "archive").exists())

    def test_missing_group_write_commands_do_not_leave_residual_group_dirs(self):
        commands = [
            ("note", "--group", "typo", "--agent", "frontend", "记录"),
            ("ask", "--group", "typo", "--agent", "frontend", "@backend", "问题"),
            ("answer", "--group", "typo", "--agent", "backend", "q-0001", "答案"),
            ("decision", "--group", "typo", "--agent", "frontend", "决策"),
            ("claim", "--group", "typo", "--agent", "frontend", "--files", "src/login/**", "任务"),
            ("release", "--group", "typo", "--agent", "frontend", "c-0001"),
            ("handoff", "--group", "typo", "--agent", "frontend", "交接"),
        ]
        for command in commands:
            with self.subTest(command=command[0]):
                result = self.run_cli(*command, ok=False)
                self.assertIn("group does not exist: typo", result.stderr)
                self.assertFalse((self.root / "groups/typo").exists())

    def test_list_groups_ignores_directories_without_manifest(self):
        (self.root / "groups/broken").mkdir(parents=True)
        self.run_cli("init", "group-a")

        groups = self.run_cli("list", "groups")

        self.assertIn("group-a", groups.stdout)
        self.assertNotIn("broken", groups.stdout)

    def test_list_agents_requires_group(self):
        result = self.run_cli("list", "agents", ok=False)

        self.assertIn("--group is required for list agents", result.stderr)

    def test_claim_normalizes_relative_paths_and_rejects_unsafe_paths(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")

        self.run_cli(
            "claim",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            "--files",
            "./src/login/**",
            "登录页 UI 调整",
        )
        claims = self.read_json("groups/group-a/claims.json")
        self.assertEqual(claims["claims"][0]["files"], ["src/login/**"])

        parent = self.run_cli(
            "claim",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            "--files",
            "../secret",
            "越界",
            ok=False,
        )
        self.assertIn("invalid claim path", parent.stderr)

        absolute = self.run_cli(
            "claim",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            "--files",
            "/tmp/secret",
            "绝对路径",
            ok=False,
        )
        self.assertIn("invalid claim path", absolute.stderr)

    def test_claim_rejects_directory_and_conservative_glob_conflicts(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("join", "group-a", "backend")

        self.run_cli(
            "claim",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            "--files",
            "src/login",
            "登录目录",
        )
        directory_conflict = self.run_cli(
            "claim",
            "--group",
            "group-a",
            "--agent",
            "backend",
            "--files",
            "src/login/form.ts",
            "登录表单",
            ok=False,
        )
        self.assertIn("conflicts with active claim c-0001", directory_conflict.stderr)

        self.run_cli(
            "claim",
            "--group",
            "group-a",
            "--agent",
            "backend",
            "--files",
            "src/api/form.ts",
            "接口表单",
        )

        self.run_cli("init", "group-b")
        self.run_cli("join", "group-b", "frontend")
        self.run_cli("join", "group-b", "backend")
        self.run_cli(
            "claim",
            "--group",
            "group-b",
            "--agent",
            "frontend",
            "--files",
            "src/*.ts",
            "src ts",
        )
        glob_conflict = self.run_cli(
            "claim",
            "--group",
            "group-b",
            "--agent",
            "backend",
            "--files",
            "src/app.ts",
            "app ts",
            ok=False,
        )
        self.assertIn("conflicts with active claim c-0001", glob_conflict.stderr)

    def test_answer_rejects_non_target_and_duplicate_answers(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("join", "group-a", "backend")
        self.run_cli("join", "group-a", "reviewer")
        self.run_cli(
            "ask",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            "@backend",
            "接口错误码最终按哪套处理",
        )

        non_target = self.run_cli(
            "answer",
            "--group",
            "group-a",
            "--agent",
            "reviewer",
            "q-0001",
            "我来回答",
            ok=False,
        )
        self.assertIn("question q-0001 is targeted to @backend", non_target.stderr)

        self.run_cli(
            "answer",
            "--group",
            "group-a",
            "--agent",
            "backend",
            "q-0001",
            "按 ApiErrorCode 统一处理",
        )

        duplicate = self.run_cli(
            "answer",
            "--group",
            "group-a",
            "--agent",
            "backend",
            "q-0001",
            "重复回答",
            ok=False,
        )
        self.assertIn("question already answered: q-0001", duplicate.stderr)

    def test_answer_allows_any_agent_for_all_target_question(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        self.run_cli("join", "group-a", "reviewer")
        self.run_cli(
            "ask",
            "--group",
            "group-a",
            "--agent",
            "frontend",
            "@all",
            "谁可以 review?",
        )

        answer = self.run_cli(
            "answer",
            "--group",
            "group-a",
            "--agent",
            "reviewer",
            "q-0001",
            "我可以",
        )
        self.assertIn("answered q-0001", answer.stdout)

    def test_group_scoped_read_commands_use_group_lock(self):
        self.run_cli("init", "group-a")
        self.run_cli("join", "group-a", "frontend")
        lock = self.root / "locks/group-a.lock"

        for command in [
            ("sync", "--group", "group-a", "--agent", "frontend"),
            ("brief", "--group", "group-a"),
            ("status", "--group", "group-a"),
            ("list", "agents", "--group", "group-a"),
        ]:
            with self.subTest(command=command[0]):
                lock.unlink(missing_ok=True)
                self.run_cli(*command)
                self.assertTrue(lock.exists())

    def test_write_json_rejects_target_symlink(self):
        group_dir = self.root / "groups/group-a"
        group_dir.mkdir(parents=True)
        outside = Path(self.tmp.name) / "outside-manifest.json"
        manifest = group_dir / "manifest.json"
        os.symlink(outside, manifest)

        result = self.run_cli("init", "group-a", ok=False)

        self.assertIn("refusing to write symlink", result.stderr)
        self.assertTrue(manifest.is_symlink())
        self.assertFalse(outside.exists())

    def test_write_json_rejects_tmp_symlink(self):
        group_dir = self.root / "groups/group-a"
        group_dir.mkdir(parents=True)
        outside = Path(self.tmp.name) / "outside-tmp.json"
        outside.write_text("unchanged")
        os.symlink(outside, group_dir / "manifest.json.tmp")

        result = self.run_cli("init", "group-a", ok=False)

        self.assertIn("refusing to write symlink", result.stderr)
        self.assertEqual("unchanged", outside.read_text())
        self.assertFalse((group_dir / "manifest.json").exists())

    def test_invalid_names_cannot_escape_coord_root(self):
        result = self.run_cli("init", "../evil", ok=False)
        self.assertIn("invalid group", result.stderr)
        self.assertFalse((self.root.parent / "evil").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
