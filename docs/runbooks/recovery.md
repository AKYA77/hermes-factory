# Development recovery

Stop your development coordinator before filesystem maintenance. Never erase .local
or reset experiment history to make a job pass. A terminated worker leaves a leased
job; the next claim recovers expired work, fences old tokens, and caps attempts.
Local unit tests simulate lease expiry; actual VPS process/reboot fault tests remain.

An invalid source quote is quarantined before catalog commit. Hash mismatch refuses
read; do not rewrite canonical quotes to bypass it. Inspect raw source and create a
new dataset version after a reviewed correction. Failed jobs keep their error/state.

Back up outside the state root with scripts/backup.sh, rehearse an isolated copy with
scripts/restore-test.sh. Production restore and service quiescence are pending;
do not swap live state based solely on this development runbook.
