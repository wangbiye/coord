#!/usr/bin/env python3
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INSTALL = ROOT / "install.sh"
SOURCE_SKILLS = ROOT / "skills"


def is_owned_coord_skill(path):
    return path.name == "coord" or path.name.startswith("coord-")


class InstallScriptTest(unittest.TestCase):
    def test_install_syncs_owned_coord_skills_and_preserves_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skills"
            target.mkdir()
            (target / "coord-stale").mkdir()
            (target / "coord-stale" / "SKILL.md").write_text("stale\n")
            (target / "coord-old-command").mkdir()
            (target / "coord-old-command" / "SKILL.md").write_text("stale\n")
            (target / "lark-doc").mkdir()
            (target / "lark-doc" / "SKILL.md").write_text("keep\n")
            (target / "coordinate-helper").mkdir()
            (target / "coordinate-helper" / "SKILL.md").write_text("also keep\n")

            result = subprocess.run(
                [str(INSTALL), str(target)],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((target / "coord-stale").exists())
            self.assertFalse((target / "coord-old-command").exists())
            self.assertEqual("keep\n", (target / "lark-doc" / "SKILL.md").read_text())
            self.assertEqual("also keep\n", (target / "coordinate-helper" / "SKILL.md").read_text())

            expected = sorted(path.name for path in SOURCE_SKILLS.iterdir() if path.is_dir() and is_owned_coord_skill(path))
            installed = sorted(path.name for path in target.iterdir() if path.is_dir() and is_owned_coord_skill(path))
            self.assertEqual(expected, installed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
