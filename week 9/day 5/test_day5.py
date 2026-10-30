"""Проверка реестра моделей, переключения/отката, проверки перед выкаткой и маршрутов дня 10 (без сети и моделей)."""
import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import app as app_module
import classifier
import commit_types
import model_registry
import verification

REGISTRY_SRC = Path(__file__).parent / "registry" / "models.json"


def chat_reply(text: str) -> dict:
    """Фальшивый ответ llm_client.chat."""
    return {"content": text, "completion_tokens": 7, "prompt_tokens": 20, "seconds": 0.1}


def main() -> None:
    assert commit_types.parse_type('{"type": "fix"}') == ("fix", True)
    assert commit_types.parse_type('Sure: {"type": "feat"}') == ("feat", False)
    assert commit_types.parse_type("no idea") == (None, False)
    assert len(commit_types.build_messages("x", "prompt")) == 2 and len(commit_types.build_messages("x", "plain")) == 1
    print("✅ commit_types: разбор ответа (строгий/нестрогий/мусор) и режимы промпта")

    ok, why = verification.verdict({"accuracy": 0.70, "strict_format": 1.0})
    assert ok and not why
    assert not verification.verdict({"accuracy": 0.5, "strict_format": 1.0})[0]
    assert not verification.verdict({"accuracy": 0.7, "strict_format": 0.9})[0]
    assert not verification.verdict({"accuracy": 0.65, "strict_format": 1.0}, baseline_accuracy=0.70)[0]
    print("✅ verdict: пороги точности, формата и просадки относительно активной модели")

    tmp = Path(tempfile.mkdtemp())
    try:
        shutil.copy(REGISTRY_SRC, tmp / "models.json")
        with mock.patch.object(model_registry, "REGISTRY_DIR", tmp), \
                mock.patch("llm_client.is_healthy", return_value=True):
            assert model_registry.active_id() == "deepseek-v4-flash"
            try:
                model_registry.activate("tuned-v1")
                raise AssertionError("активация без проверки должна быть отклонена")
            except ValueError as e:
                assert "не прошла проверку" in str(e)
            model_registry.record_verification("tuned-v1", {"passed": True, "accuracy": 0.70})
            assert model_registry.activate("tuned-v1")["active"] == "tuned-v1"
            assert model_registry.state()["history"] == ["deepseek-v4-flash"]
            with mock.patch("llm_client.is_healthy", return_value=False):
                try:
                    model_registry.activate("tuned-v1-q4", force=False)
                    raise AssertionError("непроверенная модель не должна включаться")
                except ValueError:
                    pass
                assert model_registry.activate("tuned-v1-q4", force=True)["active"] == "tuned-v1-q4"
            assert model_registry.rollback() == {"active": "tuned-v1", "history": ["deepseek-v4-flash"]}
            assert model_registry.rollback()["active"] == "deepseek-v4-flash"
            try:
                model_registry.rollback()
                raise AssertionError("откатываться некуда")
            except ValueError:
                pass
            print("✅ реестр: активация только после проверки, force, стек истории, откат до пустого стека")

            client = app_module.app.test_client()
            model_registry.record_verification("base-qwen-q8", {"passed": True})
            assert client.post("/models/activate", json={"id": "base-qwen-q8"}).get_json()["active"] == "base-qwen-q8"
            with mock.patch("llm_client.chat", return_value=chat_reply('{"type": "fix"}')) as chat:
                r = client.post("/classify", json={"message": "fix crash on empty config"})
                assert r.status_code == 200 and r.get_json()["type"] == "fix" and r.get_json()["model"] == "base-qwen-q8"
                assert chat.call_args.args[0] == "http://127.0.0.1:8081/v1"
                client.post("/models/activate", json={"id": "tuned-v1"})
                client.post("/classify", json={"message": "x"})
                assert chat.call_args.args[0] == "http://127.0.0.1:8082/v1"  # подмена без перезапуска
                assert client.post("/models/rollback").get_json()["active"] == "base-qwen-q8"
            print("✅ маршруты: /classify идёт в активную модель, переключение и откат без перезапуска")

            commits = [{"hash": "a", "subject": "add x", "body": ""}, {"hash": "b", "subject": "fix y", "body": "b"}]
            with mock.patch("github_repo.get_commits", return_value=commits), \
                    mock.patch("github_repo.repo_label", return_value="o/r"), \
                    mock.patch("llm_client.chat", side_effect=[chat_reply('{"type": "feat"}'), chat_reply("???")]):
                r = client.post("/classify", json={"repo": "o/r", "last": 2})
            body = r.get_json()
            assert r.status_code == 200 and body["source"] == "o/r" and body["by_type"] == {"feat": 1, "unknown": 1}
            print("✅ /classify по репозиторию: типы, распределение, unknown для непонятных ответов")

            for payload, path in (({}, "/classify"), ({"repo": "o/r", "last": "abc"}, "/classify"),
                                  ({"message": "x", "model": "нет-такой"}, "/classify"),
                                  ({}, "/models/activate"), ({"id": "нет-такой"}, "/models/activate")):
                r = client.post(path, json=payload)
                assert r.status_code == 400 and "error" in r.get_json(), (path, payload)
            r = client.post("/classify", json={"message": "x", "model": "deepseek-v4-flash"})
            assert r.status_code == 400 and "deepseek_key" in r.get_json()["error"]
            print("✅ ошибки: JSON {error} и код 400 для пустого ввода, last, неизвестной модели, DeepSeek без ключа")

            perfect = [{"messages": [{"content": f"Commit message:\ntext {i}"}], "type": "fix"} for i in range(4)]
            with mock.patch.object(verification, "EVAL_PATH", tmp / "eval.jsonl"):
                (tmp / "eval.jsonl").write_text("".join(json.dumps(r) + "\n" for r in perfect), encoding="utf-8")
                with mock.patch.object(classifier, "classify_one",
                                       return_value={"type": "fix", "strict": True, "reply": "", "seconds": 0.1}):
                    res = verification.run(model_registry.get("tuned-v1"))
            assert res["passed"] and res["accuracy"] == 1.0 and res["n"] == 4
            print("✅ verification.run: прогон набора и вердикт")
    finally:
        shutil.rmtree(tmp)
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — реестр, переключение, откат, проверка и маршруты дня 10 корректны")


if __name__ == "__main__":
    main()
