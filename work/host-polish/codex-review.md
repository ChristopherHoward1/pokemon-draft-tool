**MEDIUM — An explicitly empty `PORT` bypasses validation.** In `host.sh`, `PORT="${PORT:-8000}"` turns `PORT=''` into `8000` before the new regex check. The plan says an invalid `PORT` must be refused, so this case starts on the default port instead of printing the required error. Preserve the default when `PORT` is unset while validating an explicitly empty value.

The other changes match the stated criteria. The recorded live host scenarios passed, including shutdown, restart, server death, and the orphan check. This finding does not block approval under the review’s severity rules.

Codex verdict: APPROVE
