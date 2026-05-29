#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SKILLS_DIR="$SOURCE_DIR/skills"
MODE="codex"
TARGET_ARG=""

usage() {
  echo "Usage: $0 [codex|claude] [target_dir]"
  echo "       $0 [target_dir]"
}

if [ "$#" -gt 0 ]; then
  case "$1" in
    codex|--codex)
      MODE="codex"
      shift
      ;;
    claude|--claude)
      MODE="claude"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      MODE="custom"
      TARGET_ARG="$1"
      shift
      ;;
  esac
fi

if [ "$#" -gt 0 ]; then
  TARGET_ARG="$1"
  shift
fi

if [ "$#" -gt 0 ]; then
  usage >&2
  exit 2
fi

case "$MODE" in
  codex)
    TARGET_DIR="${TARGET_ARG:-"${AGENT_SKILLS_DIR:-"$HOME/.agents/skills"}"}"
    TARGET_LABEL="Codex skills directory"
    RELOAD_MESSAGE="Restart or reload Codex so it can discover the updated skills."
    ;;
  claude)
    TARGET_DIR="${TARGET_ARG:-"${CLAUDE_SKILLS_DIR:-"$HOME/.claude/skills"}"}"
    TARGET_LABEL="Claude Code skills directory"
    RELOAD_MESSAGE="Restart Claude Code so it can discover the updated skills."
    ;;
  custom)
    TARGET_DIR="$TARGET_ARG"
    TARGET_LABEL="skills directory"
    RELOAD_MESSAGE="Reload your agent environment so it can discover the updated skills."
    ;;
esac

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

echo "Installed $installed_count coord skills to $TARGET_LABEL: $TARGET_DIR"
echo "$RELOAD_MESSAGE"
