#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-"${AGENT_SKILLS_DIR:-"$HOME/.agents/skills"}"}"

mkdir -p "$TARGET_DIR"

for skill_dir in "$SOURCE_DIR"/skills/coord*; do
  [ -d "$skill_dir" ] || continue
  name="$(basename "$skill_dir")"
  rm -rf "$TARGET_DIR/$name"
  cp -R "$skill_dir" "$TARGET_DIR/$name"
done

echo "Installed coord skills to: $TARGET_DIR"
echo "Reload your agent environment so it can discover the updated skills."
