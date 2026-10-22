"""Проверка notify.send_telegram: деградация, обрезка, статусы (без сети)."""
import io
import json
from unittest import mock

from notify import send_telegram


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def main() -> None:
    with mock.patch("urllib.request.urlopen") as m:
        for kw in ({}, {"token": "t"}, {"chat_id": "c"}, {"token": "  ", "chat_id": "c"},
                   {"token": None, "chat_id": None}):
            res = send_telegram("x", **kw)
            assert res["status"] == "skipped" and "chat_id" in res["reason"], kw
        m.assert_not_called()
    print("✅ без токена/chat_id -> skipped, сеть не вызывается")

    with mock.patch("urllib.request.urlopen",
                    return_value=_Resp(json.dumps({"ok": True, "result": {}}).encode())) as m:
        res = send_telegram("я" * 5000, token=" TOK ", chat_id=" 42 ")
    req = m.call_args.args[0]
    payload = json.loads(req.data)
    assert req.full_url == "https://api.telegram.org/botTOK/sendMessage"
    assert payload["chat_id"] == "42" and len(payload["text"]) == 4096
    assert payload["parse_mode"] == "Markdown" and payload["disable_web_page_preview"] is True
    assert res["status"] == "sent" and res["response"]["ok"] is True
    print("✅ успех: URL, обрезка до 4096, пробелы, статус sent")

    with mock.patch("urllib.request.urlopen",
                    return_value=_Resp(json.dumps({"ok": False, "description": "bad"}).encode())):
        res = send_telegram("x", token="t", chat_id="c")
    assert res["status"] == "error" and res["response"]["description"] == "bad"
    print("✅ ok=false от Telegram -> status error")

    with mock.patch("urllib.request.urlopen", side_effect=OSError("сеть упала")):
        res = send_telegram("x", token="t", chat_id="c")
    assert res == {"status": "error", "reason": "сеть упала"}
    print("✅ исключение сети -> status error, без падения")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — notify (деградация, обрезка, ошибки)")


if __name__ == "__main__":
    main()
