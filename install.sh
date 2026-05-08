#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-"${AGENT_SKILLS_DIR:-"$HOME/.agents/skills"}"}"
SOURCE_SKILLS_DIR="$SOURCE_DIR/skills"

mkdir -p "$TARGET_DIR"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd -P)"

if [ "$TARGET_DIR" = "/" ] || [ "$TARGET_DIR" = "$HOME" ]; then
  echo "Refusing to install into unsafe target directory: $TARGET_DIR" >&2
  exit 1
fi

for installed_dir in "$TARGET_DIR"/coord "$TARGET_DIR"/coord-*; do
  [ -e "$installed_dir" ] || [ -L "$installed_dir" ] || continue
  if [ ! -d "$installed_dir" ]; then
    echo "Refusing to replace non-directory skill path: $installed_dir" >&2
    exit 1
  fi
  rm -rf "$installed_dir"
done

installed_count=0
for skill_dir in "$SOURCE_SKILLS_DIR"/coord "$SOURCE_SKILLS_DIR"/coord-*; do
  [ -d "$skill_dir" ] || continue
  name="$(basename "$skill_dir")"
  cp -R "$skill_dir" "$TARGET_DIR/$name"
  installed_count=$((installed_count + 1))
done

if [ "$installed_count" -eq 0 ]; then
  echo "No coord skills found under: $SOURCE_SKILLS_DIR" >&2
  exit 1
fi

echo "Installed $installed_count coord skills to: $TARGET_DIR"
echo "Reload your agent environment so it can discover the updated skills."
