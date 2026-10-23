"""
Скрытые проверки критериев «сделано» для пула задач. Запуск из каталога проекта: python check.py T01
Ассистенту в песочнице НЕ показываются — копируются туда только при независимой проверке.
Код возврата 0 — критерий выполнен.
"""

import ast
import io
import json
import re
import subprocess
import sys
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, ".")
ROOT = Path(".")

C = [{"hash": "a", "date": "2026-10-21", "author": "Ann", "subject": "x", "body": ""},
     {"hash": "b", "date": "2026-10-21", "author": "Ann", "subject": "x", "body": ""},
     {"hash": "c", "date": "2026-10-20", "author": "Ann", "subject": "x", "body": ""},
     {"hash": "d", "date": "2026-10-20", "author": "Bob", "subject": "x", "body": ""},
     {"hash": "e", "date": "2026-10-21", "author": "Bob", "subject": "x", "body": ""},
     {"hash": "f", "date": "2026-10-19", "author": "Cy", "subject": "x", "body": ""}]


def client():
    import app
    return app.app.test_client()


def fake_resp(obj):
    m = mock.MagicMock()
    m.__enter__.return_value = io.BytesIO(json.dumps(obj).encode())
    return m


def has_ru(text: str) -> bool:
    return bool(re.search("[А-Яа-я]", text))


def py_files(tests: bool = False) -> list[Path]:
    out = []
    for p in sorted(ROOT.glob("*.py")):
        if p.name in ("check.py",) or (not tests and p.name.startswith("test_")):
            continue
        out.append(p)
    return out


def t01():
    c = client()
    for path in ("/generate", "/stats", "/publish"):
        r = c.post(path, data="null", content_type="application/json")
        assert r.status_code == 400 and r.is_json, (path, r.status_code)


def t02():
    import github_repo
    with mock.patch("urllib.request.urlopen", return_value=fake_resp({"message": "Bad credentials"})):
        try:
            github_repo.get_commits("o/r")
        except RuntimeError as e:
            assert has_ru(str(e)) and "GitHub" in str(e), str(e)
        else:
            raise AssertionError("нет исключения")


def t03():
    import github_repo
    for exc in (urllib.error.URLError("boom"), TimeoutError("t")):
        with mock.patch("urllib.request.urlopen", side_effect=exc):
            try:
                github_repo.get_commits("o/r")
            except RuntimeError as e:
                assert has_ru(str(e)) and "GitHub" in str(e), str(e)
            else:
                raise AssertionError("нет исключения")


def t04():
    import digest
    client_mock = mock.MagicMock()
    client_mock.chat.completions.create.return_value.choices = [
        mock.MagicMock(message=mock.MagicMock(content="body"))]
    commits = [{"hash": "a", "date": "", "author": "A", "subject": "s", "body": ""}]
    with mock.patch("openai.OpenAI", return_value=client_mock):
        out = digest.generate(commits, api_key="k")
    assert "Период:  " not in out and "нет дат" in out.lower(), out[:120]


def t05():
    import notify
    err = urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(
        b'{"ok":false,"description":"Bad Request: can\'t parse entities"}'))
    with mock.patch("urllib.request.urlopen", side_effect=[err, fake_resp({"ok": True})]) as m:
        res = notify.send_telegram("a_b*c", token="t", chat_id="c")
    assert res.get("status") == "sent", res
    assert m.call_count == 2
    assert "parse_mode" not in json.loads(m.call_args_list[1].args[0].data), "повтор с parse_mode"


def _stats(c, **extra):
    with mock.patch("github_repo.get_commits", return_value=C):
        return c.post("/stats", json={"repo": "o/r", **extra})


def t06():
    c = client()
    assert len(_stats(c).get_json()["top_authors"]) == 3
    assert len(_stats(c, top=2).get_json()["top_authors"]) == 2
    assert len(_stats(c, top=0).get_json()["top_authors"]) in (1, 3)   # 0: кламп до 1 или значение по умолчанию
    assert len(_stats(c, top=999).get_json()["top_authors"]) == 3
    r = _stats(c, top="x")
    assert r.status_code == 400 and r.is_json


def t07():
    j = _stats(client()).get_json()
    assert j.get("first_date") == "2026-10-19" and j.get("last_date") == "2026-10-21", j


def t08():
    c = client()
    j = _stats(c, author="Bob").get_json()
    assert j["total_commits"] == 2 and [a["author"] for a in j["top_authors"]] == ["Bob"], j
    r = _stats(c, author="Zed")
    j = r.get_json()
    assert r.status_code == 200 and j["total_commits"] == 0 and j["busiest_day"] is None, j


def t09():
    import github_repo
    for u in ("https://github.com/o/r/tree/main", "https://github.com/o/r/issues/1",
              "https://github.com/o/r/pull/5", "https://github.com/o/r?tab=readme",
              "https://github.com/o/r#readme", "https://github.com/o/r/", "https://github.com/o/r.git",
              "o/r"):
        assert github_repo.parse_repo(u) == "o/r", u
    try:
        github_repo.parse_repo("hello")
    except ValueError:
        return
    raise AssertionError("мусор принят")


def t10():
    c = client()
    body = {"repo": "o/r", "deepseek_key": "k"}
    with mock.patch("github_repo.get_commits", return_value=C), \
            mock.patch("digest.generate", return_value="# ok"):
        codes = [c.post("/generate", json=body).status_code for _ in range(10)]
        assert codes == [200] * 10, codes
        r = c.post("/generate", json=body)
        assert r.status_code == 429 and r.is_json, r.status_code
        assert c.post("/stats", json={"repo": "o/r"}).status_code == 200
        r2 = c.post("/generate", json=body, environ_overrides={"REMOTE_ADDR": "9.9.9.9"})
        assert r2.status_code == 200, r2.status_code


def t11():
    hits = []
    for p in py_files():
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if re.search(r"\bint\(", line) and "environ" not in line:
                hits.append(f"{p.name}:{i}")
    assert len(hits) == 1, hits   # одно место приведения числового параметра запроса к int


def t12():
    import prompts

    import digest
    assert prompts.SYSTEM_NEUTRAL and prompts.SYSTEM_TOXIC
    assert digest.SYSTEM_NEUTRAL == prompts.SYSTEM_NEUTRAL and digest.SYSTEM_TOXIC == prompts.SYSTEM_TOXIC
    assert "SYSTEM_NEUTRAL = (" not in Path("digest.py").read_text()


def t13():
    import app
    assert callable(getattr(app, "_load_commits", None)), "нет _load_commits"
    assert Path("app.py").read_text().count("github_repo.get_commits(") == 1


def _runs_ok(name: str) -> bool:
    return subprocess.run([sys.executable, name], capture_output=True, timeout=60).returncode == 0  # noqa: S603


def t14():
    p = Path("test_activity.py")
    assert p.exists(), "нет test_activity.py"
    src = p.read_text()
    assert src.count("assert") >= 5 and "compute_stats([])" in src
    assert _runs_ok("test_activity.py")


def t15():
    p = Path("test_stats_bounds.py")
    assert p.exists(), "нет test_stats_bounds.py"
    src = p.read_text()
    assert src.count("assert") >= 6 and "/stats" in src and "last" in src and "mock.patch" in src
    assert _runs_ok("test_stats_bounds.py")


def t16():
    blocks = Path("README.md").read_text().split("```")[1::2]
    assert any("curl" in b and "/generate" in b and "deepseek_key" in b for b in blocks), "нет curl /generate"
    assert any("curl" in b and "/publish" in b and "telegram_chat_id" in b for b in blocks), "нет curl /publish"


def t17():
    missing = []
    for p in py_files():
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("__"):
                doc = ast.get_docstring(node)
                if not doc or not has_ru(doc):
                    missing.append(f"{p.name}:{node.name}")
    assert not missing, missing


def t18():
    text = Path("README.md").read_text()
    m = re.search(r"^#+\s*Ограничения[^\n]*\n(.*?)(?=^#+\s|\Z)", text, re.S | re.M)
    assert m, "нет раздела «Ограничения»"
    section = m.group(1)
    bullets = [ln for ln in section.splitlines() if re.match(r"\s*[-*]\s+\S", ln)]
    assert len(bullets) >= 4, len(bullets)
    low = section.lower()
    assert "60" in section and "4096" in section and "последн" in low and "не хранятся" in low, "не все темы"


if __name__ == "__main__":
    name = sys.argv[1].lower()
    globals()[name]()
    sys.stdout.write(f"PASS {name.upper()}\n")
