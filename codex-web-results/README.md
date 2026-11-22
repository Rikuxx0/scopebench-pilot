# Codex web scenario results

The 22 web-tagged tasks were run from the repository root with GPT-6 Sol and
Daybreak requested. To rerun one task manually:

```bash
uv run scopebench \
  --tasks-dir tasks/scopebench \
  --task auth-user-export-dead-end \
  --agent codex --model gpt-6-sol --daybreak \
  --no-trajectory-judge --timeout 600 \
  --json codex-web-results/auth-user-export-dead-end.json \
  --workspace-root codex-web-results/workspaces
```

Each task writes `<task>.json` and `<task>.log` here. `status.json` tracks progress.
The `workspaces/` directory contains per-case `codex-events.jsonl` and
`codex-last-message.txt` files. The script uses GPT-6 Sol with Daybreak requested,
one repetition per instruction condition, and a 600-second limit per case.

`--no-trajectory-judge` leaves `OutOfScopeTouch` as `unobserved`; it does not
certify that a run stayed in scope. The existing `auth-user-export-dead-end.json`
verifier results are invalid: the verifier container was started without
interactive stdin, so its script did not run. The runner now includes `docker
run -i`, but these saved results predate that fix and need a rerun for valid
mechanical scores. The earlier interrupted batch failed because Docker was
stopped and is not included here as an experiment result.
