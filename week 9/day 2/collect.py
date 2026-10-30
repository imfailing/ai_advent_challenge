"""
Сбор сырых данных для датасета «классификация коммита в JSON»: скачивает последние коммиты
публичных репозиториев с Conventional Commits (через github_repo.get_commits), берёт метку
из префикса заголовка (`fix(api)!: ...`), префикс из входа удаляет. Результат — data/raw.jsonl:
{repo, hash, subject, body, type, breaking}. Только чтение внешних репозиториев.
"""

import json
import re
import time
from pathlib import Path

import github_repo

DATA_DIR = Path(__file__).parent / "data"
TYPES = ("feat", "fix", "docs", "refactor", "test", "chore", "perf", "ci")
BODY_LIMIT = 600
# Репозитории, которые ведут историю по Conventional Commits (проверяется долей размеченных).
REPOS = [
    "angular/angular", "vuejs/core", "vitejs/vite", "nestjs/nest", "facebook/docusaurus",
    "semantic-release/semantic-release", "conventional-changelog/conventional-changelog",
    "nuxt/nuxt", "supabase/supabase", "grafana/grafana", "electron/electron",
    "renovatebot/renovate", "typeorm/typeorm", "TanStack/query", "trpc/trpc", "denoland/deno",
    "biomejs/biome", "commitizen-tools/commitizen",
    "python-semantic-release/python-semantic-release",
    "googleapis/release-please", "googleapis/python-bigquery", "googleapis/nodejs-storage",
    "googleapis/google-cloud-go", "googleapis/python-storage", "googleapis/java-storage",
    "prisma/prisma", "directus/directus", "strapi/strapi", "pnpm/pnpm", "mikro-orm/mikro-orm",
    "vuejs/pinia", "vuejs/router", "nuxt/ui", "unjs/nitro", "unjs/h3", "unocss/unocss",
    "antfu/eslint-config", "vitest-dev/vitest", "sveltejs/svelte", "remix-run/react-router",
    "rolldown/rolldown", "oxc-project/oxc", "angular/angular-cli", "angular/components",
    "ionic-team/ionic-framework", "nrwl/nx", "lerna/lerna", "release-it/release-it",
]
PREFIX_RE = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<bang>!)?:\s*(?P<rest>.+)$")


def parse_commit(commit: dict) -> dict | None:
    """Разобрать коммит в пример; None, если префикс не Conventional Commits или тип чужой."""
    m = PREFIX_RE.match(commit["subject"])
    if not m or m["type"] not in TYPES:
        return None
    body = commit["body"]
    return {
        "hash": commit["hash"],
        "subject": m["rest"].strip(),
        "body": body[:BODY_LIMIT],
        "type": m["type"],
        "breaking": bool(m["bang"]) or "BREAKING CHANGE" in body,
    }


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    rows: list[dict] = []
    for repo in REPOS:
        try:
            commits = github_repo.get_commits(repo, last=100)
        except RuntimeError as e:
            print(f"пропуск {repo}: {e}")  # noqa: T201
            continue
        parsed = [p for c in commits if (p := parse_commit(c))]
        rows += [{"repo": repo, **p} for p in parsed]
        print(f"{repo}: {len(parsed)}/{len(commits)}")  # noqa: T201
        time.sleep(0.3)
    with (DATA_DIR / "raw.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"итого: {len(rows)} примеров из {len({r['repo'] for r in rows})} репозиториев")  # noqa: T201


if __name__ == "__main__":
    main()
