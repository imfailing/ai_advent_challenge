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
import sys
from pathlib import Path

import digest
import gitlog
from notify import send_telegram


def main() -> None:
    ap = argparse.ArgumentParser(description="AI-дайджест изменений репозитория")
    ap.add_argument("--last", type=int, help="последние N коммитов")
    ap.add_argument("--since", help="за период, напр. '1 week ago', '2026-07-14'")
    ap.add_argument("--range", dest="range", help="диапазон base..head")
    ap.add_argument("--out", default="digest.md", help="файл дайджеста")
    ap.add_argument("--notify", action="store_true", help="опубликовать в Telegram")
    ap.add_argument("--title", default="Дайджест изменений")
    args = ap.parse_args()

    if not any([args.last, args.since, args.range]):
        args.last = 15   # по умолчанию — последние 15 коммитов

    commits = gitlog.get_commits(last=args.last, since=args.since, rev_range=args.range)
    if not commits:
        print("Коммитов в диапазоне нет — нечего обобщать.")
        return
    print(f"Ветка {gitlog.current_branch()}, коммитов: {len(commits)} — генерирую дайджест…")

    md = digest.generate(commits, title=args.title)

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
