#!/usr/bin/env bash
# ruff + все офлайн-тесты проекта (test_*.py). Код возврата 0 — всё зелёное.
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"; RUFF="${RUFF:-ruff}"; fail=0
echo "== ruff =="; "$RUFF" check . || fail=1
echo "== тесты =="
for t in test_*.py; do
  if "$PYTHON" "$t" >/tmp/loop_"$t".log 2>&1; then echo "PASS $t"; else echo "FAIL $t"; tail -12 /tmp/loop_"$t".log; fail=1; fi
done
exit $fail
