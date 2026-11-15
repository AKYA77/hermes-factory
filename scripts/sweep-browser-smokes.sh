#!/usr/bin/env bash
# Run every browser smoke in sequence and report one line each.
#
# Exit status is the contract: a smoke exits 0 on success and non-zero on failure.
# Do NOT grep for a "status" field -- some smokes print a JSON summary without one
# (discovery, screen-cohort and their siblings), so parsing for that string labels
# passing runs as failures. This wrapper was written after exactly that mistake
# produced five bogus FAILs during a full sweep.
#
# Smokes are run strictly serially: they start a real Chromium plus a dashboard
# server, and concurrent runs contend for CPU, memory and sockets.
#
# Usage: scripts/sweep-browser-smokes.sh [state-parent-dir]
#
# FACTORY_SMOKE_EXCLUDE is an extended regex matched against the smoke name; matches
# are reported SKIPPED, not run. It defaults to the three smokes whose fixtures need
# data that exists only on the acquisition host -- source-registry imports eight
# retained provider archives, and source-coverage/source-quality read the real
# observation database, catalog and partition receipts. Running them on a fresh
# checkout would fail for reasons unrelated to the dashboard, which is exactly how
# CI stops being trusted. Those three stay verified here against real acquired data.
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
parent="${1:-/var/lib}"

overall=0
pass=0
fail=0
skip=0
exclude="${FACTORY_SMOKE_EXCLUDE-source-registry-browser|source-coverage-browser|source-quality-browser}"

for smoke in scripts/*-browser-smoke.cjs; do
  base="$(basename "${smoke%-smoke.cjs}")"
  fixture="scripts/${base}-fixture.py"
  if [[ "$base" =~ $exclude ]]; then
    printf '%-34s SKIP  excluded by FACTORY_SMOKE_EXCLUDE\n' "$base"
    skip=$((skip + 1))
    continue
  fi
  if [ ! -f "$fixture" ]; then
    printf '%-34s NO_FIXTURE\n' "$base"
    overall=1
    continue
  fi
  state="$parent/smoke-sweep-${base}-$(date +%s)"
  log="$(mktemp)"
  timeout 1800 bash scripts/run-browser-smoke.sh "$base-fixture.py" "$base-smoke.cjs" \
    "$state" >"$log" 2>&1
  rc=$?
  errors="$(grep -oE '"page_errors":\[[^]]*\]' "$log" | tail -1)"
  overflow="$(grep -oE '"mobile_overflow":[a-z]+' "$log" | tail -1)"
  if [ "$rc" -eq 0 ]; then
    printf '%-34s PASS  %s %s\n' "$base" "${overflow:-}" "${errors:-}"
    pass=$((pass + 1))
    rm -f "$log"
  else
    # Keep the log and show its tail: a bare "FAIL rc=1" with nothing else is what
    # makes a red CI job useless.
    echo "--- $base output tail ---" >&2
    tail -15 "$log" >&2
    echo "--- end $base (full log: $log) ---" >&2
    printf '%-34s FAIL  rc=%s  log: %s\n' "$base" "$rc" "$log"
    fail=$((fail + 1))
    overall=1
  fi
done

printf '\n%d passed, %d failed, %d skipped\n' "$pass" "$fail" "$skip"
exit "$overall"
