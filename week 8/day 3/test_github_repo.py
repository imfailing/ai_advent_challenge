"""Проверка github_repo: parse_repo, get_commits, маппинг HTTP-ошибок (без сети)."""
import io
import json
import urllib.error
from unittest import mock

import github_repo

RAW = [
    {"sha": "abcdef1234567", "commit": {
        "message": "feat: заголовок\n\nтело коммита\nвторая строка",
        "author": {"name": "Ann", "date": "2024-01-02T10:00:00Z"}}},
    {"sha": "1234567890", "commit": {"message": "  fix  ", "author": {}}},
    {"commit": {"message": None}},
]


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("u", code, "Reason", {}, None)


def main() -> None:
    for v in ("https://github.com/o/r", "https://github.com/o/r/", "https://github.com/o/r.git",
              "git@github.com:o/r.git", "o/r", "  o/r  ", "my-org/re.po_1"):
        assert github_repo.parse_repo(v) in ("o/r", "my-org/re.po_1"), v
    assert github_repo.repo_label("https://github.com/o/r.git") == "o/r"
    print("✅ parse_repo: URL, .git, ssh, owner/repo, пробелы")

    for bad in ("", "abc", "a/b/c", "a b/c"):
        try:
            github_repo.parse_repo(bad)
        except ValueError as e:
            assert "owner/repo" in str(e)
        else:
            raise AssertionError(f"ожидался ValueError для {bad!r}")
    print("✅ parse_repo: мусор -> ValueError")

    with mock.patch("urllib.request.urlopen",
                    return_value=_Resp(json.dumps(RAW).encode())) as m:
        commits = github_repo.get_commits("o/r", last=500, token="  tok  ")
    req = m.call_args.args[0]
    assert req.full_url.endswith("/repos/o/r/commits?per_page=100"), req.full_url
    assert req.get_header("Authorization") == "Bearer tok"
    print("✅ get_commits: last клампится до 100, токен в заголовке Bearer")

    assert commits[0] == {"hash": "abcdef1", "date": "2024-01-02", "author": "Ann",
                          "subject": "feat: заголовок", "body": "тело коммита\nвторая строка"}
    assert commits[1] == {"hash": "1234567", "date": "", "author": "?",
                          "subject": "fix", "body": ""}
    assert commits[2]["hash"] == "" and commits[2]["subject"] == ""
    print("✅ get_commits: маппинг hash/date/author/subject/body и дефолты")

    with mock.patch("urllib.request.urlopen", return_value=_Resp(b"[]")) as m:
        github_repo.get_commits("o/r", last=0)
    assert "per_page=1" in m.call_args.args[0].full_url
    assert m.call_args.args[0].get_header("Authorization") is None
    print("✅ get_commits: last=0 -> 1, без токена нет Authorization")

    for code, text in ((404, "не найден или приватный"), (403, "Лимит GitHub API"),
                       (500, "GitHub API: 500 Reason")):
        with mock.patch("urllib.request.urlopen", side_effect=_http_error(code)):
            try:
                github_repo.get_commits("o/r")
            except RuntimeError as e:
                assert text in str(e), str(e)
                assert isinstance(e.__cause__, urllib.error.HTTPError)
            else:
                raise AssertionError(code)
    print("✅ get_commits: 404/403/прочие HTTP-ошибки -> RuntimeError по-русски")

    try:
        github_repo.get_commits("плохо")
    except ValueError:
        pass
    else:
        raise AssertionError("ожидался ValueError")
    print("✅ get_commits: неверный repo -> ValueError до сетевого вызова")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — github_repo (парсинг, маппинг, ошибки)")


if __name__ == "__main__":
    main()
