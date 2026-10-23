#!/usr/bin/env bash
# Создаёт песочницу execution loop: копия проекта + правила/профили + пул задач, отдельный git-репозиторий.
# Использование: make_sandbox.sh <каталог> [каталог-с-правилами]   (по умолчанию правила берутся из корня репозитория)
set -e
DST="$1"; HERE="$(cd "$(dirname "$0")/.." && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
RULES="${2:-$REPO}"
mkdir -p "$DST"
cp -R "$HERE/fixtures/base/." "$DST/"
cp "$HERE/TASKS.md" "$DST/TASKS.md"
cp "$HERE/harness/LOOP.md" "$DST/LOOP.md"
cp "$HERE/harness/sandbox_run_tests.sh" "$DST/run_tests.sh"; chmod +x "$DST/run_tests.sh"
cp "$RULES/CLAUDE.md" "$DST/CLAUDE.md"
mkdir -p "$DST/.claude/agents"; cp "$RULES"/.claude/agents/*.md "$DST/.claude/agents/"
sed 's#src = \[.*\]#src = ["."]#' "$REPO/ruff.toml" | grep -v 'week 8/day 4' > "$DST/ruff.toml"
cp "$HERE/harness/sandbox_CLAUDE.local.md" "$DST/CLAUDE.local.md"
printf '__pycache__/\n.ruff_cache/\n*.pyc\n' > "$DST/.gitignore"
cd "$DST" && git init -q && git add -A && git -c user.email=loop@x -c user.name=loop commit -qm "base: исходное состояние проекта и пул задач"
