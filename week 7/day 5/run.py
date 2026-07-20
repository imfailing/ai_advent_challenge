"""
Сервис «AI-дайджест изменений репозитория».

Задача: превратить сырые git-коммиты в понятный дайджест (release notes) и
опубликовать его — без ручного написания.

Пайплайн:
  git log → DeepSeek (группировка + переписывание) → digest.md → Telegram (опц.)

Запуск:
  python run.py --last 20
  python run.py --since "1 week ago"
  python run.py --range af1211e..HEAD
  python run.py --last 20 --out digest.md --notify
"""

import argparse
from pathlib import Path

import digest
import github_repo
import gitlog
from notify import send_telegram


def main() -> None:
    ap = argparse.ArgumentParser(description="AI-дайджест / роаст изменений репозитория")
    ap.add_argument("--repo", help="внешний GitHub-репозиторий (owner/repo или ссылка)")
    ap.add_argument("--last", type=int, help="последние N коммитов")
    ap.add_argument("--since", help="за период, напр. '1 week ago' (только локальный репо)")
    ap.add_argument("--range", dest="range", help="диапазон base..head (только локальный)")
    ap.add_argument("--toxic", action="store_true", help="🔥 токсичный роаст вместо дайджеста")
    ap.add_argument("--out", default="digest.md", help="файл результата")
    ap.add_argument("--notify", action="store_true", help="опубликовать в свой Telegram")
    ap.add_argument("--title", default="")
    args = ap.parse_args()

    tone = "toxic" if args.toxic else "neutral"

    if args.repo:
        commits = github_repo.get_commits(args.repo, last=args.last or 15)
        label = github_repo.repo_label(args.repo)
    else:
        if not any([args.last, args.since, args.range]):
            args.last = 15
        commits = gitlog.get_commits(last=args.last, since=args.since, rev_range=args.range)
        label = gitlog.current_branch()

    if not commits:
        print("Коммитов не найдено — нечего обобщать.")
        return
    what = "роаст" if tone == "toxic" else "дайджест"
    print(f"Источник: {label}, коммитов: {len(commits)} — генерирую {what}…")

    title = args.title or (f"Роаст коммитов {label}" if tone == "toxic"
                           else f"Дайджест изменений {label}")
    md = digest.generate(commits, title=title, tone=tone)

    out = Path(args.out)
    out.write_text(md, encoding="utf-8")
    print(f"✓ Дайджест сохранён: {out}\n")
    print(md)

    if args.notify:
        res = send_telegram(md)
        print(f"\nПубликация в Telegram: {res['status']}"
              + (f" — {res.get('reason','')}" if res.get("reason") else ""))


if __name__ == "__main__":
    main()
