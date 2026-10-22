#!/usr/bin/env bash
# Уровень 1: ruff + все офлайн-тесты дня. Использование: ./run_tests.sh   (из любого каталога)
# PYTHON/RUFF можно переопределить переменными окружения.
set -u
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
RUFF="${RUFF:-ruff}"
fail=0
echo "== ruff =="
if command -v "$RUFF" >/dev/null 2>&1; then
  (cd ../.. && "$RUFF" check "week 8/day 3") || fail=1   # из корня: там ruff.toml
else
  echo "ruff не найден — пропущено"
fi
echo "== тесты (офлайн) =="
# test_digest.py — интеграционный (сеть + ключ DeepSeek), запускается отдельно
for t in test_github_repo test_notify test_digest_unit test_app_routes test_stats; do
  if "$PYTHON" "$t.py" >/tmp/"$t".log 2>&1; then
    echo "PASS $t ($(grep -c '✅' /tmp/"$t".log) проверок)"
  else
    echo "FAIL $t"; tail -15 /tmp/"$t".log; fail=1
  fi
done
exit $fail
